"""Durable job snapshots with FIFO orchestration over the existing long-text core.

Only final validated artifacts are published. A reservation pins the exact
profile from acceptance until terminal status, including queue/cancel races.
"""
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import queue
import shutil
import threading
import time
import uuid

import numpy as np
import soundfile as sf

from backend.errors import ApplicationError, ErrorCode
from backend.errors.handlers import MESSAGES
from backend.schemas.common import ErrorBody
from backend.schemas.long_form import LongFormRequest, LongFormStatus
from backend.core.languages import VERIFIED, language_status
from core.tts_manager import TTSManager
from core.long_text import ChunkingConfig, build_chunks
from backend.persistence import Repository

logger = logging.getLogger("backend.long_form")
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}

# Task 3.5 (TTS performance): benchmark-proven long-form chunk sizing.
# Fewer, larger chunks cut fixed per-chunk overhead (CUDA sync barriers, a
# full-file WAV re-validation per chunk, an extra disk copy, three DB writes)
# without touching inference itself: num_step, the model and the provider are
# all unchanged. Measured on the fixed long-form Vietnamese corpus against the
# production provider path (not just the vendored
# package): 15 chunks / 26.613s / RTF 0.2895 (old default 100/160/1) versus
# 7 chunks / 16.727s / RTF 0.1822 (this config) -- ~37% faster wall time,
# text integrity PASS, valid WAV/MP3, model_load_count stayed 1, peak VRAM
# +~3.3%. Single source of truth: both the preflight build_chunks() call and
# the synthesize_long_text() call in _run() below must reference this exact
# object, never a re-declared literal, so they can never silently chunk
# differently from each other (see test_long_form.py::
# test_preflight_and_synthesis_use_identical_chunk_config).
LONG_FORM_CHUNK_CONFIG = ChunkingConfig(target_chars=240, max_chars=320, max_sentences_per_chunk=3)


def validate_wav(path: Path) -> dict:
    """Decode all samples, including float WAVs and truncated PCM payloads."""
    try:
        with sf.SoundFile(path) as source:
            if source.format != "WAV" or source.samplerate != 24000 or source.channels != 1:
                raise ValueError()
            frames = 0
            for block in source.blocks(blocksize=65536, dtype="float32", always_2d=True):
                if not np.isfinite(block).all():
                    raise ValueError()
                frames += len(block)
            if frames <= 0 or frames != source.frames:
                raise ValueError()
            return {"sample_rate": 24000, "channels": 1, "duration": frames / 24000,
                    "finite": True, "decodable": True, "non_empty": True}
    except Exception:
        raise ApplicationError(ErrorCode.GENERATION_FAILED) from None


@dataclass
class _Job:
    snapshot: LongFormStatus
    request: LongFormRequest | None
    record: object | None
    cancel: threading.Event = field(default_factory=threading.Event)
    diagnostics: dict = field(default_factory=dict)


class LongFormTTSService:
    def __init__(self, settings, providers, profiles, app_settings_service=None):
        self._settings = settings
        self._providers = providers
        self._profiles = profiles
        # Optional, defaults to None so existing callers/tests that construct
        # this service directly keep today's exact behavior (max_retries=0,
        # provider's own default num_step - see _run() below). When present
        # (real backend startup via main.py), Settings > Performance's Retry
        # Count and Advanced's num_step become live inputs to every long-form
        # job's per-chunk synthesis, matching TTSService's Short TTS wiring.
        self._app_settings = app_settings_service
        self._output = Path(settings.output_dir)
        self._staging = self._output / "long_form_private"
        self._staging.mkdir(parents=True, exist_ok=True)
        self._jobs = {}
        self._db = Repository(settings)
        self._db.recover()
        for snapshot, diagnostics in self._db.history():
            restored = LongFormStatus(**snapshot)
            self._jobs[restored.job_id] = _Job(restored, None, None, diagnostics=diagnostics)
        self._lock = threading.RLock()
        self._queue = queue.Queue()
        self._closed = False
        self._thread = threading.Thread(target=self._worker, name="long-form-tts", daemon=True)
        self._thread.start()

    def submit(self, request: LongFormRequest) -> LongFormStatus:
        if language_status(request.language) != VERIFIED:
            raise ApplicationError(ErrorCode.LANGUAGE_NOT_SUPPORTED)
        with self._lock:
            if self._closed:
                raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)
            record = self._profiles.reserve_profile(request.profile_id)
            job_id = str(uuid.uuid4())
            snapshot = LongFormStatus(job_id=job_id, status="QUEUED")
            try:
                self._db.create_job(snapshot, {
                    'request': request.model_dump(), 'provider_id': record.provider_id,
                    'profile_revision': record.created_at, 'provider_version': None,
                    'model_revision': None, 'normalizer_version': 'core-whitespace-v1',
                    'chunker_version': 'core-long-text-v1', 'seed': None,
                    'audio': {'sample_rate': 24000, 'channels': 1, 'format': request.format}}, request.profile_id)
            except Exception:
                self._profiles.release_profile(record)
                raise
            self._jobs[job_id] = _Job(snapshot, request, record)
            self._queue.put(job_id)
            return snapshot

    def _get(self, job_id):
        job = self._jobs.get(job_id)
        if job is None:
            db_job = self._db.get_job(job_id)
            if db_job and db_job.get("kind") == "long_form":
                snapshot = LongFormStatus(**json.loads(db_job["snapshot"]))
                diagnostics = json.loads(db_job.get("diagnostics") or "{}")
                job = _Job(snapshot, None, None, diagnostics=diagnostics)
                self._jobs[job_id] = job
                return job
            raise ApplicationError(ErrorCode.JOB_NOT_FOUND)
        return job

    def status(self, job_id):
        with self._lock:
            return self._get(job_id).snapshot

    def diagnostics(self, job_id):
        """Internal evidence only; no HTTP route exposes this metadata."""
        with self._lock:
            return dict(self._get(job_id).diagnostics)

    def _finish(self, job, status, *, audio_url=None, error=None, outputs=()):
        # Caller holds registry lock. Release BEFORE making terminal observable.
        snapshot = job.snapshot.model_copy(update={
            'status': status, 'audio_url': audio_url, 'error': error,
            'progress_percent': 100 if status == 'COMPLETED' else job.snapshot.progress_percent})
        self._db.save_job(snapshot, job.diagnostics, outputs)
        if job.record is not None:
            self._profiles.release_profile(job.record)
            job.record = None
        job.request = None
        job.snapshot = snapshot

    def cancel(self, job_id):
        with self._lock:
            job = self._get(job_id)
            if job.snapshot.status not in TERMINAL:
                job.cancel.set()
                if job.snapshot.status == "QUEUED":
                    self._finish(job, "CANCELLED")
            return job.snapshot

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                for job_id in self._jobs:
                    self.cancel(job_id)
                self._queue.put(None)
        self._thread.join()  # Native inference finishes its current chunk safely.

    def _worker(self):
        while True:
            job_id = self._queue.get()
            if job_id is None:
                return
            # Shared with short TTS and profile creation/test. Status stays queued
            # while another application inference owns the device.
            with self._providers.inference_lock:
                with self._lock:
                    job = self._jobs[job_id]
                    if job.snapshot.status != "QUEUED":
                        continue
                    job.snapshot = job.snapshot.model_copy(update={"status": "RUNNING"})
                    self._db.save_job(job.snapshot, job.diagnostics)
                self._run(job)

    def _cleanup_job_dirs(self, job_id, work):
        """Remove every per-job on-disk scratch/retention artifact for job_id.

        Called explicitly BEFORE each of _run()'s three _finish() calls below
        (not only from `finally`) - a caller polling status() must never be
        able to observe a terminal status while this cleanup is still
        pending. `finally` still calls this too, as a safety net for any exit
        path that somehow bypasses all three explicit call sites (e.g. an
        unexpected error inside _finish() itself); rmtree(ignore_errors=True)
        on an already-removed directory is a harmless no-op, so calling this
        twice in the normal case costs nothing.
        """
        # work is built solely from an internal UUID beneath private staging.
        if work.resolve().is_relative_to(self._staging.resolve()):
            shutil.rmtree(work, ignore_errors=True)
        # persisted_chunks/{job_id}/ (phan-tich-bao-mat-du-an-17-09.md finding
        # #1): synthesize() below copies every valid chunk here (originally a
        # debugging aid) but nothing ever read it back or cleaned it up -
        # left alone, every long-form job leaves its per-chunk speech audio
        # (can be a cloned voice) on disk forever. job_id is always a bare
        # UUID (see submit()), so this can never escape persisted_chunks/ -
        # the containment check is kept anyway, purely for defense in depth.
        persisted_chunks_dir = self._output / 'persisted_chunks' / job_id
        if persisted_chunks_dir.resolve().is_relative_to((self._output / 'persisted_chunks').resolve()):
            shutil.rmtree(persisted_chunks_dir, ignore_errors=True)

    def _run(self, job):
        job_id = job.snapshot.job_id
        request, record = job.request, job.record
        work = self._staging / job_id
        published = []
        started = time.perf_counter()
        # Settings > Performance > Retry Count is expressed there as "N total
        # attempts" (see TTSService._run()'s identical mapping for Short TTS);
        # TTSManager's own max_retries means "extra attempts after the first"
        # (see prototype/core/tts_manager.py, `range(1, max_retries + 2)`), so
        # max_retries = retry_count - 1. 0 (today's exact hardcoded value, no
        # retry) when no AppSettingsService is wired in.
        max_retries = max(0, self._app_settings.resolve_retry_count() - 1) if self._app_settings is not None else 0
        num_step = self._app_settings.resolve_num_steps() if self._app_settings is not None else None
        # Long-form is unsupported until CP2 supplies an engine with cloning.
        silence_trim = self._app_settings.resolve_silence_trim() if self._app_settings is not None else False
        try:
            self._profiles.restore_profile(record)
            provider = self._providers.get_provider(record.provider_id)
            # Profiles depend on the already loaded model. Never reload and
            # silently replace conditioning if an internal unload invalidated it.
            if not provider.is_loaded():
                raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_READY)
            manager = TTSManager(work, output_dir=work, temp_dir=work / "chunks")
            manager.register_provider(provider)
            generation_indices = []
            profile_ids = set()
            model = getattr(provider, "_model", None)
            load_count = getattr(provider, "_load_count", None)
            # The unchanged core uses these same defaults. Map normalized content
            # to original Unicode code-point offsets, excluding boundary whitespace.
            positions = [i for i, char in enumerate(request.text) if not char.isspace()]
            source = ''.join(request.text[i] for i in positions)
            cursor = 0
            for chunk in build_chunks(request.text, LONG_FORM_CHUNK_CONFIG):
                content = ''.join(chunk.text.split())
                end = cursor + len(content)
                if source[cursor:end] != content:
                    raise ApplicationError(ErrorCode.GENERATION_FAILED)
                self._db.chunk(job_id, chunk.index, chunk.text, 'PENDING',
                    source_range=(positions[cursor], positions[end - 1] + 1))
                cursor = end
            if cursor != len(positions):
                raise ApplicationError(ErrorCode.GENERATION_FAILED)

            def synthesize(text, language, voice, output_path, **options):
                index = int(Path(output_path).stem.split('_')[-1])
                self._db.chunk(job_id, index, text, 'GENERATING')
                try:
                    if getattr(provider, "_model", None) is not model:
                        raise ValueError()
                    result = provider.synthesize_cloned(text=text, language=language,
                                                       profile=record.provider_profile,
                                                       output_path=output_path, num_step=num_step,
                                                       trim_silence=silence_trim)
                    if (result.status != "PASS" or not result.wav_path
                            or Path(result.wav_path).resolve() != Path(output_path).resolve()
                            or getattr(provider, "_model", None) is not model
                            or getattr(provider, "_load_count", None) != load_count):
                        raise ValueError()
                    validate_wav(Path(output_path))
                    retained = self._output / 'persisted_chunks' / job_id / Path(output_path).name
                    retained.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(output_path, retained)
                    self._db.chunk(job_id, index, text, 'COMPLETED', retained)
                    generation_indices.append(int(Path(output_path).stem.split("_")[-1]))
                    profile_ids.add(id(record.provider_profile))
                    return result
                except Exception:
                    self._db.chunk(job_id, index, text, 'FAILED', error='GENERATION_FAILED')
                    # Never forward provider exception strings/customer data to core logs.
                    raise ApplicationError(ErrorCode.GENERATION_FAILED) from None

            def progress(event):
                with self._lock:
                    job.snapshot = job.snapshot.model_copy(update={"progress_percent": max(
                        job.snapshot.progress_percent, min(95, float(event["progress"]) * 95))})
                    self._db.save_job(job.snapshot, job.diagnostics)

            result = manager.synthesize_long_text(
                request.text, request.language, "",
                filename="final.wav", chunk_config=LONG_FORM_CHUNK_CONFIG,
                max_retries=max_retries, chunk_synthesizer=synthesize,
                audio_validator=validate_wav, export_mp3_enabled=request.format == "mp3",
                on_progress=progress, is_cancelled=job.cancel.is_set)
            # The voice_id above only selects the registered provider in legacy
            # core. Generation exclusively invokes the bound clone callback.
            count = result["chunk_count"]
            job.diagnostics = {"chunk_count": count, "generation_indices": generation_indices,
                               "unique_profiles_used": len(profile_ids),
                               "model_load_count": getattr(provider, "_load_count", None),
                               "completed_chunks": result["completed_chunks"]}
            with self._lock:
                if result["status"] == "FAILED":
                    raise ApplicationError(ErrorCode.GENERATION_FAILED)
                if job.cancel.is_set() or result["status"] == "CANCELLED":
                    self._cleanup_job_dirs(job_id, work)
                    self._finish(job, "CANCELLED")
                    return
                if result["status"] != "COMPLETED" or generation_indices != list(range(count)):
                    raise ApplicationError(ErrorCode.GENERATION_FAILED)
                audio = validate_wav(Path(result["wav_path"]))
                artifact_id = str(uuid.uuid4())
                target = self._output / f"{artifact_id}.wav"
                Path(result["wav_path"]).replace(target)
                published.append(target)
                fmt = "wav"
                if request.format == "mp3" and result["mp3_path"]:
                    mp3 = Path(result["mp3_path"])
                    if mp3.is_file() and mp3.stat().st_size:
                        target = self._output / f"{artifact_id}.mp3"
                        mp3.replace(target)
                        published.append(target)
                        fmt = "mp3"
                job.diagnostics.update(audio=audio, elapsed_seconds=time.perf_counter() - started,
                                       mp3_export_failed=request.format == "mp3" and fmt == "wav")
                # Published artifacts (target/mp3 above) are already moved out
                # of `work` by this point, so cleaning it up now - before the
                # job becomes observably COMPLETED - is safe.
                self._cleanup_job_dirs(job_id, work)
                self._finish(job, "COMPLETED", audio_url=f"{self._settings.api_prefix}/audio/{artifact_id}.{fmt}", outputs=published)
        except Exception as exc:
            for path in published:
                path.unlink(missing_ok=True)
            code = exc.code if isinstance(exc, ApplicationError) else ErrorCode.GENERATION_FAILED
            logger.error("long_form_failed job_id=%s error_code=%s", job_id, code.value)
            self._cleanup_job_dirs(job_id, work)
            with self._lock:
                self._finish(job, "FAILED", error=ErrorBody(code=code.value, message=MESSAGES[code]))
        finally:
            self._cleanup_job_dirs(job_id, work)
