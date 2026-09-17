"""Application TTS service: validate -> persisted job -> synthesize -> validate/store audio -> final status.

Short TTS jobs share the same durable job model as long-form/clone jobs
(backend.persistence.Repository, kind='short'): QUEUED -> RUNNING ->
COMPLETED/FAILED, recovered to FAILED/INTERRUPTED on restart (no resume).
A single background worker thread serializes actual synthesis through the
shared application inference lock, mirroring LongFormTTSService. The legacy
synchronous `synthesize()`/`POST /api/tts` contract is preserved by
submitting a job and polling it to a terminal state before returning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import logging
from pathlib import Path
import queue
import threading
import time
import uuid
import wave

from backend.config import Settings
from backend.errors import ApplicationError, ErrorCode
from backend.errors.handlers import MESSAGES
from backend.schemas.common import ErrorBody
from backend.schemas.tts import TTSData, TTSRequest, TTSResponse, TTSStatus
from backend.services.provider_service import ProviderService
from core.audio_utils import export_mp3
from core.languages import VERIFIED, language_status
from backend.persistence import Repository
from providers.piper import PiperProvider

logger = logging.getLogger("backend.tts")
MAX_TEXT_LENGTH = 2000
JOB_KIND = "short"
TERMINAL = {"COMPLETED", "FAILED"}
POLL_INTERVAL_SECONDS = 0.01
# Safety net only: short-TTS generation is expected to finish in well under a
# second against a real provider. This bounds the legacy synchronous wrapper
# so a stuck worker cannot hang an HTTP request forever.
LEGACY_WAIT_TIMEOUT_SECONDS = 60.0


def _idempotency_fingerprint(text: str, language: str, voice_id: str, speed: float, fmt: str) -> str:
    """Fingerprint of the request fields that determine the synthesis result
    (post-validation/normalization values, not the raw request body). Reusing
    an idempotency_key is only a safe replay when this fingerprint also
    matches; a matching key with a different fingerprint is a conflicting
    reuse of the key and must be rejected rather than silently returning the
    unrelated prior job (see ErrorCode.IDEMPOTENCY_KEY_CONFLICT).
    """
    payload = json.dumps(
        {"text": text, "language": language, "voice_id": voice_id, "speed": speed, "format": fmt},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class _Job:
    snapshot: TTSStatus
    # In-memory-only synthesis parameters for THIS process's worker to consume.
    # Never persisted directly (execution_snapshot already carries the raw
    # request for audit purposes); cleared once the job reaches a terminal
    # state so raw customer text is not retained longer than necessary.
    params: dict | None = None
    # Safe, small, persisted metadata only (no raw text) - written to the
    # database's diagnostics column on every transition.
    diagnostics: dict = field(default_factory=dict)


class TTSService:
    def __init__(self, settings: Settings, provider_service: ProviderService, translation_service,
                 voice_profile_service, app_settings_service=None):
        self._settings = settings
        self._provider_service = provider_service
        self._translation = translation_service
        # Lets a Short TTS job's voice_id also name a cloned voice profile
        # (backend/services/voice_profile_service.py) instead of only one of
        # the provider's fixed built-in voices - see validate_request() and
        # _run() below. Constructed before this service in main.py's lifespan
        # specifically so it can be injected here.
        self._voice_profiles = voice_profile_service
        # Optional (defaults to None so every existing caller/test that builds
        # a TTSService without it keeps today's exact single-fixed-directory,
        # single-attempt, provider-default-num_step behavior). When present
        # (real backend startup via main.py), Settings > Audio/Performance/
        # Advanced's Output Directory/Retry Count/num_step become live, per-job
        # inputs instead of dead UI - see _run() below.
        self._app_settings = app_settings_service
        self._output_dir = Path(settings.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._db = Repository(settings)
        # Explicit allowlist: do not serialize environment, credentials or auth configuration.
        self._db.put('settings', 'runtime', {
            'primary_tts_provider': settings.primary_tts_provider,
            'omnivoice_device': settings.omnivoice_device, 'app_version': settings.app_version})

        # Global recovery: any job (short/clone/long_form) left QUEUED/RUNNING
        # by a previous process is marked FAILED/INTERRUPTED here, ahead of
        # any service rehydrating job state from history. Idempotent: a
        # later Repository.recover() call (e.g. from LongFormTTSService)
        # simply finds nothing left to recover. (This service is no longer
        # the first constructed in main.py's lifespan - translation_service
        # and voice_profile_service now come first, see TTSService.__init__'s
        # new voice_profile_service param - but neither of those touches job
        # recovery, so running it here remains correct.)
        self._db.recover()

        self._jobs: dict[str, _Job] = {}
        for snapshot, diagnostics in self._db.history(JOB_KIND):
            restored = TTSStatus(**snapshot)
            self._jobs[restored.job_id] = _Job(restored, diagnostics=diagnostics)

        self._lock = threading.RLock()
        self._queue: queue.Queue = queue.Queue()
        self._closed = False
        self._thread = threading.Thread(target=self._worker, name="short-tts", daemon=True)
        self._thread.start()

    @property
    def output_dir(self) -> Path:
        """Current default output directory - dynamic when Settings > Audio's
        Output Directory is configured (see resolve_audio_path() below for
        where a *specific, already-generated* artifact actually lives, which
        is what GET /api/audio/{artifact_id} uses instead of this property).
        """
        if self._app_settings is not None:
            return self._app_settings.resolve_output_dir()
        return self._output_dir

    def resolve_audio_path(self, artifact_id: str) -> Path:
        """Where a specific artifact actually lives on disk. Customers can
        change Settings > Audio's Output Directory after already generating
        files, so "the current output_dir" and "where job X's audio actually
        is" are not always the same directory - each completed job records
        the directory it was written to (see _run() below) and this looks
        that up first, falling back to the current directory only for jobs
        that predate this field (or were never found), reproducing the old
        single-fixed-directory behavior for them.
        """
        generation_id = Path(artifact_id).stem
        stored_dir = None
        try:
            job = self._get(generation_id)
            stored_dir = (job.diagnostics or {}).get('result', {}).get('output_dir')
        except ApplicationError:
            stored_dir = None
        base_dir = Path(stored_dir) if stored_dir else self.output_dir
        return base_dir / artifact_id

    def _select_provider(self, language: str):
        """Route by language: Piper's six dedicated languages go to the Piper
        provider; everything else (Vietnamese, and any language Piper does not
        cover) keeps using the primary provider exactly as before this
        routing existed. Cloning is unaffected - it never calls this method.
        """
        if language in PiperProvider.LANGUAGES:
            return self._provider_service.get_provider(PiperProvider.PROVIDER_ID)
        return self._provider_service.get_primary_provider()

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._queue.put(None)
        self._thread.join()  # Native inference finishes its current call safely.

    def validate_request(self, request: TTSRequest) -> tuple[str, str, str, float, str, str | None, str | None]:
        # Text validation: reject None, non-string, empty, whitespace-only
        text = request.text
        if text is None or not isinstance(text, str) or not text.strip():
            raise ApplicationError(ErrorCode.INVALID_TEXT)
        cleaned_text = text.strip()
        if len(cleaned_text) > MAX_TEXT_LENGTH:
            raise ApplicationError(ErrorCode.TEXT_TOO_LONG)

        # Language validation: only canonical verified languages
        language = request.language
        if not isinstance(language, str) or language_status(language) != VERIFIED:
            raise ApplicationError(ErrorCode.LANGUAGE_NOT_SUPPORTED)

        # Non-Vietnamese output requires a translation step (see
        # backend/services/translation_service.py) - checked here, before a
        # job is even queued, so a customer without a configured key gets an
        # immediate, clear error instead of a job that fails later in _run().
        # Vietnamese never reaches this branch - Short TTS/Clone are
        # unaffected whether or not a key is configured.
        if language != "vi" and not self._translation.is_configured():
            raise ApplicationError(ErrorCode.TRANSLATION_KEY_REQUIRED)

        # Voice validation against provider without triggering model load. A
        # voice_id may also name a previously-created cloned voice profile
        # (backend/services/voice_profile_service.py) instead of one of the
        # provider's fixed built-in voices. Cloning is exclusively an
        # OmniVoice capability (OmniVoiceProvider.capabilities()['voice_cloning']
        # is True; Piper has none), so a profile id is only ever accepted for
        # a language that is not routed to Piper.
        provider = self._select_provider(language)
        voices = provider.list_voices(language)
        valid_voices = {v.id for v in voices}
        for voice in voices:
            self._db.put('voices', voice.id, {'id': voice.id, 'provider_id': provider.provider_name()})
        voice_id = request.voice_id
        cloned_profile_id: str | None = None
        if not voice_id:
            voice_id = PiperProvider.AUTO_VOICE_ID if language in PiperProvider.LANGUAGES else "omnivoice_auto"
        elif not isinstance(voice_id, str):
            raise ApplicationError(ErrorCode.VOICE_NOT_FOUND)
        elif voice_id not in valid_voices:
            if language in PiperProvider.LANGUAGES:
                raise ApplicationError(ErrorCode.VOICE_NOT_FOUND)
            try:
                self._voice_profiles.get_profile_record(voice_id)
            except ApplicationError:
                raise ApplicationError(ErrorCode.VOICE_NOT_FOUND) from None
            cloned_profile_id = voice_id

        # Speed validation: must be a number, 0.5 <= speed <= 2.0 and speed == 1.0
        speed = request.speed
        if speed is None or isinstance(speed, bool) or not isinstance(speed, (int, float)):
            raise ApplicationError(ErrorCode.INVALID_SPEED)
        if not (0.5 <= speed <= 2.0) or float(speed) != 1.0:
            raise ApplicationError(ErrorCode.INVALID_SPEED)
        speed = float(speed)

        # Format validation: wav or mp3
        fmt = request.format
        if not isinstance(fmt, str) or fmt.lower() not in ("wav", "mp3"):
            raise ApplicationError(ErrorCode.INVALID_FORMAT)
        fmt = fmt.lower()

        # Idempotency key: optional, but if present must be a non-blank string.
        idempotency_key = request.idempotency_key
        if idempotency_key is not None:
            if not isinstance(idempotency_key, str) or not idempotency_key.strip():
                raise ApplicationError(ErrorCode.INVALID_REQUEST)
            idempotency_key = idempotency_key.strip()

        return cleaned_text, language, voice_id, speed, fmt, idempotency_key, cloned_profile_id

    # ------------------------------------------------------------------
    # Async job API
    # ------------------------------------------------------------------

    def submit(self, request: TTSRequest) -> TTSStatus:
        text, language, voice_id, speed, fmt, idempotency_key, cloned_profile_id = self.validate_request(request)
        fingerprint = (
            _idempotency_fingerprint(text, language, voice_id, speed, fmt)
            if idempotency_key is not None else None
        )

        execution = {
            'request': request.model_dump(), 'provider_id': self._settings.primary_tts_provider,
            'provider_version': None, 'model_revision': None, 'voice_revision': None, 'seed': None,
            'normalizer_version': 'strip-v1', 'chunker_version': None,
            'audio': {'sample_rate': 24000, 'channels': 1, 'format': fmt},
            'idempotency_key': idempotency_key,
            'idempotency_fingerprint': fingerprint,
        }

        with self._lock:
            if self._closed:
                raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)

            if idempotency_key is not None:
                existing = self._db.find_job_by_idempotency_key(JOB_KIND, idempotency_key)
                if existing is not None:
                    existing_id, existing_fingerprint = existing
                    if existing_fingerprint != fingerprint:
                        # Same key, different request: reject deterministically
                        # instead of silently returning an unrelated job.
                        raise ApplicationError(ErrorCode.IDEMPOTENCY_KEY_CONFLICT)
                    return self._get(existing_id).snapshot

            job_id = str(uuid.uuid4())
            snapshot = TTSStatus(job_id=job_id, status="QUEUED")
            self._db.create_job(snapshot, execution, kind=JOB_KIND)
            job = _Job(snapshot, params={
                'text': text, 'language': language, 'voice_id': voice_id, 'speed': speed, 'format': fmt,
                'cloned_profile_id': cloned_profile_id,
            })
            self._jobs[job_id] = job
            self._queue.put(job_id)
            return snapshot

    def _get(self, job_id) -> _Job:
        job = self._jobs.get(job_id)
        if job is None:
            db_job = self._db.get_job(job_id)
            if db_job and db_job.get("kind") == JOB_KIND:
                snapshot = TTSStatus(**json.loads(db_job["snapshot"]))
                diagnostics = json.loads(db_job.get("diagnostics") or "{}")
                job = _Job(snapshot, diagnostics=diagnostics)
                self._jobs[job_id] = job
                return job
            raise ApplicationError(ErrorCode.JOB_NOT_FOUND)
        return job

    def status(self, job_id: str) -> TTSStatus:
        with self._lock:
            return self._get(job_id).snapshot

    def history(self) -> list[TTSStatus]:
        """Persisted job history for this kind, oldest first."""
        return [TTSStatus(**snapshot) for snapshot, _ in self._db.history(JOB_KIND)]

    def _finish(self, job: _Job, status: str, *, audio_url=None, error=None, outputs=()):
        # Caller holds self._lock.
        snapshot = job.snapshot.model_copy(update={'status': status, 'audio_url': audio_url, 'error': error})
        self._db.save_job(snapshot, job.diagnostics, outputs)
        job.snapshot = snapshot
        job.params = None  # Terminal jobs release their source text reference.

    def _worker(self):
        while True:
            job_id = self._queue.get()
            if job_id is None:
                return
            # Shared with long-form and profile creation/test. Status stays
            # queued while another application inference owns the device.
            with self._provider_service.inference_lock:
                with self._lock:
                    job = self._jobs[job_id]
                    if job.snapshot.status != "QUEUED":
                        continue
                    job.snapshot = job.snapshot.model_copy(update={"status": "RUNNING"})
                    self._db.save_job(job.snapshot, job.diagnostics)
                self._run(job)

    def _run(self, job: _Job):
        params = job.params or {}
        text = params.get('text')
        language = params.get('language')
        voice_id = params.get('voice_id')
        speed = params.get('speed')
        fmt = params.get('format')
        cloned_profile_id = params.get('cloned_profile_id')

        generation_id = job.snapshot.job_id
        # Resolved fresh per job (not cached from __init__) so a customer's
        # Settings > Audio > Output Directory change takes effect on the very
        # next job, with no backend restart - see the output_dir property.
        output_dir = self.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        wav_path = output_dir / f"{generation_id}.wav"
        # 1 = today's exact behavior (a single attempt, no retry) when no
        # AppSettingsService is wired in (e.g. most unit tests). Otherwise
        # Settings > Performance > Retry Count: N means up to N-1 extra
        # attempts after the first failure, matching
        # LongFormTTSService's max_retries semantics for the same setting.
        retry_count = self._app_settings.resolve_retry_count() if self._app_settings is not None else 1
        # None lets the provider pick its own per-mode default (16 normal /
        # 24 cloned - see prototype/providers/omnivoice.py), identical to
        # never having passed num_step at all.
        num_step = self._app_settings.resolve_num_steps() if self._app_settings is not None else None
        was_translated = False
        # Set only once reserve_profile() below succeeds - guards the release
        # in the finally block from firing for a profile that was never
        # actually reserved (e.g. it was deleted between submit() validating
        # it and this worker picking the job up).
        cloned_record = None

        try:
            # Translate first, before spending time loading a TTS model: the
            # provider must read out the translated text, not the original
            # (see backend/services/translation_service.py). validate_request
            # already refused the job if no key was configured, but the key
            # can still fail at call time (revoked, rate-limited, network) -
            # that failure ends the job here, as GENERATION_FAILED-adjacent
            # TRANSLATION_FAILED, same as any other synthesis failure below.
            if language != "vi":
                text = self._translation.translate(text, language)
                was_translated = True

            # Ensure the routed provider is loaded (lazy model load). Piper's
            # six dedicated languages route to the Piper provider; a cloned
            # voice profile (OmniVoice-only capability - validate_request()
            # already refused pairing one with a Piper language) and
            # everything else keep loading the primary provider exactly as
            # before this routing existed.
            is_piper = language in PiperProvider.LANGUAGES
            if is_piper:
                provider = self._provider_service.ensure_loaded(PiperProvider.PROVIDER_ID)
            else:
                provider = self._provider_service.ensure_primary_provider_loaded()

            if cloned_profile_id is not None:
                # reserve_profile() also re-confirms the profile still
                # exists (raises VOICE_PROFILE_NOT_FOUND otherwise) - it may
                # have been deleted between validate_request() accepting it
                # and this worker picking the job up. restore_profile()
                # lazily rebuilds the provider-side conditioning if this is
                # the first use since a backend restart (see
                # VoiceProfileService.restore_profile).
                cloned_record = self._voice_profiles.reserve_profile(cloned_profile_id)
                self._voice_profiles.restore_profile(cloned_record)

            # Settings > Audio > "Cắt khoảng lặng" (silence_trim) - trims only
            # confidently-silent leading/trailing samples. Only OmniVoice
            # accepts these two extra keyword options; PiperProvider's own
            # _synthesize() explicitly rejects ANY unrecognized option
            # (`if options or speed != 1.0: raise ... INVALID_OPTIONS`, see
            # prototype/providers/piper.py) - passing num_step/trim_silence
            # to it unconditionally would crash every job in Piper's six
            # dedicated languages, so they're only added for the primary
            # (OmniVoice) provider. Voice cloning has no such split: it's an
            # OmniVoice-only capability (validate_request already refuses
            # pairing a cloned profile with a Piper language), so
            # synthesize_cloned() always gets both options unconditionally.
            silence_trim = self._app_settings.resolve_silence_trim() if self._app_settings is not None else False
            primary_only_options = {} if is_piper else {"num_step": num_step, "trim_silence": silence_trim}

            result = None
            last_exc = None
            for attempt in range(1, retry_count + 1):
                last_exc = None
                try:
                    if cloned_record is not None:
                        result = provider.synthesize_cloned(
                            text=text, language=language, profile=cloned_record.provider_profile,
                            output_path=wav_path, num_step=num_step, trim_silence=silence_trim,
                        )
                    else:
                        result = provider.synthesize(
                            text=text, language=language, voice=voice_id, output_path=wav_path,
                            speed=speed, **primary_only_options,
                        )
                except Exception as exc:
                    last_exc = exc
                    result = None
                if result is not None and result.status == "PASS" and wav_path.is_file():
                    break
                if wav_path.is_file():
                    try:
                        wav_path.unlink()
                    except Exception:
                        pass
                if attempt < retry_count:
                    logger.warning("tts_synthesis_retry generation_id=%s attempt=%d/%d",
                                    generation_id, attempt, retry_count)

            if last_exc is not None:
                logger.error("tts_synthesis_exception generation_id=%s error=%s", generation_id, last_exc)
                raise ApplicationError(ErrorCode.GENERATION_FAILED) from None

            if result is None or result.status != "PASS" or not wav_path.is_file():
                logger.error("tts_generation_failed generation_id=%s provider=%s language=%s error=%s",
                             generation_id, provider.provider_name(), language,
                             result.error if result is not None else None)
                raise ApplicationError(ErrorCode.GENERATION_FAILED)

            # Validate generated audio
            try:
                with wave.open(str(wav_path), "rb") as wf:
                    channels = wf.getnchannels()
                    sample_rate = wf.getframerate()
                    n_frames = wf.getnframes()
                    duration = n_frames / sample_rate if sample_rate > 0 else 0.0
                if channels != 1 or sample_rate != 24000 or duration <= 0.0:
                    raise ValueError("Invalid audio properties")
            except Exception as exc:
                logger.error("audio_validation_failed generation_id=%s error=%s", generation_id, exc)
                if wav_path.is_file():
                    try:
                        wav_path.unlink()
                    except Exception:
                        pass
                raise ApplicationError(ErrorCode.GENERATION_FAILED) from None

            # Optional MP3 export. On failure the WAV is deliberately retained
            # for diagnostics (existing, tested contract).
            mp3_path = None
            if fmt == "mp3":
                mp3_path = output_dir / f"{generation_id}.mp3"
                exported = export_mp3(wav_path, mp3_path)
                if exported is None or not mp3_path.is_file() or mp3_path.stat().st_size == 0:
                    logger.error("audio_export_failed generation_id=%s wav_retained=true", generation_id)
                    raise ApplicationError(ErrorCode.AUDIO_EXPORT_FAILED)

            logger.info(
                "tts_completed generation_id=%s provider=%s language=%s voice_id=%s format=%s "
                "duration=%.2f text_length=%d gen_time=%.2f",
                generation_id, result.provider_id, language, voice_id, fmt, duration, len(text), result.gen_time,
            )

            job.diagnostics = {
                **job.diagnostics,
                'result': {
                    'duration_seconds': duration, 'provider_id': result.provider_id,
                    'sample_rate': sample_rate, 'channels': 1, 'format': fmt,
                    'language': language, 'voice_id': voice_id, 'translated': was_translated,
                    'cloned': cloned_profile_id is not None,
                    # Where this specific artifact actually landed - see
                    # resolve_audio_path() above. Recorded per-job because
                    # Settings > Audio > Output Directory can change between
                    # one job and the next.
                    'output_dir': str(output_dir),
                },
            }
            outputs = [wav_path] + ([mp3_path] if fmt == 'mp3' else [])
            with self._lock:
                self._finish(job, "COMPLETED", audio_url=f"/api/audio/{generation_id}.{fmt}", outputs=outputs)
        except Exception as exc:
            code = exc.code if isinstance(exc, ApplicationError) else ErrorCode.GENERATION_FAILED
            with self._lock:
                self._finish(job, "FAILED", error=ErrorBody(code=code.value, message=MESSAGES[code]))
        finally:
            # Mirrors VoiceProfileService.synthesize_clone()'s own
            # reserve/release pairing around its provider call - only runs
            # when reserve_profile() above actually succeeded.
            if cloned_record is not None:
                self._voice_profiles.release_profile(cloned_record)

    # ------------------------------------------------------------------
    # Legacy synchronous contract: POST /api/tts still returns 200 with a
    # completed TTSResponse. Implemented as submit() + poll so there is a
    # single job pipeline behind both the old and new API surfaces.
    # ------------------------------------------------------------------

    def synthesize(self, request: TTSRequest) -> TTSResponse:
        snapshot = self.submit(request)
        deadline = time.monotonic() + LEGACY_WAIT_TIMEOUT_SECONDS
        while snapshot.status not in TERMINAL:
            if time.monotonic() > deadline:
                raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)
            time.sleep(POLL_INTERVAL_SECONDS)
            snapshot = self.status(snapshot.job_id)

        if snapshot.status == "FAILED":
            code = ErrorCode(snapshot.error.code) if snapshot.error else ErrorCode.GENERATION_FAILED
            raise ApplicationError(code)

        with self._lock:
            result = self._get(snapshot.job_id).diagnostics.get('result', {})
        return TTSResponse(
            ok=True,
            data=TTSData(
                generation_id=snapshot.job_id,
                status="completed",
                provider=result.get('provider_id', self._settings.primary_tts_provider),
                language=result.get('language'),
                voice_id=result.get('voice_id'),
                duration_seconds=round(result.get('duration_seconds', 0.0), 3),
                sample_rate=result.get('sample_rate', 24000),
                channels=result.get('channels', 1),
                format=result.get('format', 'wav'),
                audio_url=snapshot.audio_url,
            ),
        )
