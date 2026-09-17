"""Durable profile metadata and references with lazy provider conditioning."""
from __future__ import annotations

from dataclasses import dataclass
import io
import logging
from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Any
import uuid
import wave

import numpy as np
import soundfile as sf

from backend.config import Settings
from backend.errors import ApplicationError, ErrorCode
from backend.schemas.voices import (
    CloneTestRequest,
    CloneTTSData,
    CloneTTSResponse,
    ReferenceAudioInfo,
    VoiceProfileData,
    VoiceProfileListResponse,
    VoiceProfileResponse,
)
from backend.services.provider_service import ProviderService
from backend.services.execution import serialized_inference
from core.audio_utils import export_mp3
from core.languages import VERIFIED, language_status
from backend.persistence import Repository, checksum

logger = logging.getLogger("backend.voices")

MAX_REFERENCE_SIZE = 15 * 1024 * 1024  # 15 MB
MIN_REFERENCE_DURATION = 3.0  # seconds
MAX_REFERENCE_DURATION = 60.0  # seconds
MAX_TRANSCRIPT_LENGTH = 2000
MAX_TEXT_LENGTH = 2000
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@dataclass
class VoiceProfileRecord:
    profile_id: str
    name: str
    provider_id: str
    provider_profile: Any  # Opaque VoiceProfile object from OmniVoiceProvider
    duration_seconds: float
    sample_rate: int
    channels: int
    created_at: float
    creation_count: int = 1
    use_count: int = 0
    active_jobs: int = 0
    reference_path: str | None = None
    reference_checksum: str | None = None
    transcript: str | None = None


class VoiceProfileService:
    def __init__(self, settings: Settings, provider_service: ProviderService):
        self._settings = settings
        self._provider_service = provider_service
        self._output_dir = Path(settings.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir = self._output_dir / "temp_profiles"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, VoiceProfileRecord] = {}
        self._lock = threading.Lock()
        self._db = Repository(settings)
        for metadata in self._db.profiles():
            self._records[metadata['profile_id']] = VoiceProfileRecord(**metadata)

    def _persist(self, record):
        metadata = {key: value for key, value in vars(record).items() if key != 'provider_profile'}
        metadata.update(provider_profile=None, active_jobs=0)
        self._db.put('voice_profiles', record.profile_id, metadata)

    def restore_profile(self, record):
        """Rebuild opaque provider conditioning lazily; never deserialize executable objects."""
        if record.provider_profile is not None:
            return
        with self._provider_service.inference_lock:
            if record.provider_profile is not None:
                return
            root = (self._output_dir / 'references').resolve()
            path = Path(record.reference_path).resolve() if record.reference_path else root
            if not path.is_relative_to(root) or not path.is_file() or checksum(path) != record.reference_checksum:
                raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_READY)
            provider = self._provider_service.ensure_primary_provider_loaded()
            if provider.provider_name() != record.provider_id:
                raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_READY)
            try:
                record.provider_profile = provider.create_voice_profile(path, record.transcript)
            except Exception:
                logger.error('voice_profile_restore_failed profile_id=%s', record.profile_id)
                raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_READY) from None
            if record.provider_profile is None:
                raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_READY)

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    def _validate_reference_audio(self, temp_path: Path) -> tuple[float, int, int]:
        """Validate audio decodability, duration, finite samples, and metrics.

        Decodes in exactly the same order as OmniVoiceProvider._decode_reference
        (prototype/providers/omnivoice.py) - the primary provider's own,
        already-tested reference-audio decoder (see
        prototype/tests/test_omnivoice_cloning.py::test_aac_in_mp3_filename).
        FFmpeg does container detection FIRST. This is not cosmetic: this
        function used to try libsndfile (`sf.read`) first and only fall back
        to FFmpeg if that raised. libsndfile's own MP3 decoding does
        frame-resync scanning that can succeed *wrongly* - producing
        corrupted/near-silent samples instead of raising - on a compressed
        container that is not really MP3, most commonly AAC/MP4 audio saved
        with a plain ".mp3" extension, which is a routine upload from a
        phone voice recorder. Trying libsndfile first let exactly that
        garbage decode slip past the `except Exception` fallback entirely
        and only get caught later by the amplitude/finite-sample check below
        - by which point a real, valid reference file had already been
        rejected as INVALID_REFERENCE_AUDIO, even though the OmniVoice
        provider this profile is destined for decodes the identical file
        correctly. WAV/FLAC remain decodable via a signature-checked
        libsndfile fallback, but ONLY when FFmpeg itself is not installed (a
        narrow FileNotFoundError catch) - not on any other decode failure,
        so genuinely corrupt or unsupported audio is still rejected.
        """
        try:
            try:
                decoded = subprocess.run(
                    ["ffmpeg", "-v", "error", "-nostdin", "-i", str(temp_path.resolve()),
                     "-map", "0:a:0", "-f", "wav", "-acodec", "pcm_f32le", "pipe:1"],
                    capture_output=True, timeout=30, check=True
                )
                samples, rate = sf.read(io.BytesIO(decoded.stdout), dtype="float32", always_2d=True)
            except FileNotFoundError:
                # FFmpeg is not installed - WAV/FLAC remain usable via a
                # signature-checked libsndfile fallback. Do not hand an
                # unknown compressed container to a decoder chosen by file
                # extension alone.
                with temp_path.open("rb") as source:
                    header = source.read(12)
                if not (header[:4] == b"fLaC" or (header[:4] == b"RIFF" and header[8:12] == b"WAVE")):
                    raise ValueError("FFmpeg is required to decode this container") from None
                samples, rate = sf.read(temp_path, dtype="float32", always_2d=True)

            if rate <= 0 or not samples.size or not np.isfinite(samples).all() or not np.any(samples):
                raise ValueError("Invalid audio samples")

            channels = samples.shape[1]
            duration = samples.shape[0] / rate
            if not (MIN_REFERENCE_DURATION <= duration <= MAX_REFERENCE_DURATION):
                raise ValueError(f"Duration {duration:.2f}s outside [{MIN_REFERENCE_DURATION}, {MAX_REFERENCE_DURATION}]")

            return float(duration), int(rate), int(channels)
        except Exception as exc:
            logger.warning("invalid_reference_audio error=%s", type(exc).__name__)
            raise ApplicationError(ErrorCode.INVALID_REFERENCE_AUDIO) from None

    @serialized_inference
    def create_profile(
        self,
        audio_bytes: bytes,
        filename: str,
        transcript: str,
        name: str | None = None,
    ) -> VoiceProfileResponse:
        # 1. Validate upload size
        if len(audio_bytes) > MAX_REFERENCE_SIZE:
            logger.warning("reference_audio_too_large size=%d", len(audio_bytes))
            raise ApplicationError(ErrorCode.REFERENCE_AUDIO_TOO_LARGE)
        if len(audio_bytes) == 0:
            raise ApplicationError(ErrorCode.INVALID_REFERENCE_AUDIO)

        # 2. Validate transcript
        if transcript is None or not isinstance(transcript, str) or not transcript.strip():
            raise ApplicationError(ErrorCode.INVALID_REFERENCE_TRANSCRIPT)
        cleaned_transcript = transcript.strip()
        if len(cleaned_transcript) > MAX_TRANSCRIPT_LENGTH:
            raise ApplicationError(ErrorCode.INVALID_REFERENCE_TRANSCRIPT)

        # 3. Write to temporary backend-controlled file
        suffix = Path(filename or "audio.wav").suffix
        if not suffix:
            suffix = ".wav"
        temp_file = self._temp_dir / f"ref_{uuid.uuid4().hex}{suffix}"
        try:
            temp_file.write_bytes(audio_bytes)

            # 4. Validate audio
            duration, rate, channels = self._validate_reference_audio(temp_file)

            # 5. Ensure provider loaded & create profile via provider
            provider = self._provider_service.ensure_primary_provider_loaded()
            try:
                provider_profile = provider.create_voice_profile(temp_file, cleaned_transcript)
            except ApplicationError:
                raise
            except Exception as exc:
                logger.error("voice_profile_creation_exception error=%s", exc)
                raise ApplicationError(ErrorCode.VOICE_PROFILE_CREATION_FAILED) from None

            if provider_profile is None:
                raise ApplicationError(ErrorCode.VOICE_PROFILE_CREATION_FAILED)

            # 6. Store profile record
            profile_id = str(uuid.uuid4())
            display_name = name.strip() if name and name.strip() else f"Voice Profile {profile_id[:8]}"
            record = VoiceProfileRecord(
                profile_id=profile_id,
                name=display_name,
                provider_id=provider.provider_name(),
                provider_profile=provider_profile,
                duration_seconds=round(duration, 3),
                sample_rate=rate,
                channels=channels,
                created_at=time.time(),
            )

            with self._lock:
                reference = self._output_dir / 'references' / f'{profile_id}{suffix}'
                reference.parent.mkdir(parents=True, exist_ok=True)
                reference.write_bytes(audio_bytes)
                record.reference_path = str(reference.resolve())
                record.reference_checksum = checksum(reference)
                record.transcript = cleaned_transcript
                try:
                    self._persist(record)
                except Exception:
                    reference.unlink(missing_ok=True)
                    raise
                self._records[profile_id] = record

            logger.info(
                "voice_profile_created profile_id=%s provider=%s duration=%.2f rate=%d channels=%d transcript_len=%d",
                profile_id, record.provider_id, duration, rate, channels, len(cleaned_transcript),
            )

            return VoiceProfileResponse(
                ok=True,
                data=VoiceProfileData(
                    profile_id=profile_id,
                    name=display_name,
                    provider=record.provider_id,
                    status="ready",
                    reference=ReferenceAudioInfo(
                        duration_seconds=round(duration, 3),
                        sample_rate=rate,
                        channels=channels,
                    ),
                ),
            )
        finally:
            if temp_file.is_file():
                try:
                    temp_file.unlink()
                except Exception:
                    pass

    def get_profile(self, profile_id: str) -> VoiceProfileResponse:
        record = self.get_profile_record(profile_id)
        return VoiceProfileResponse(
            ok=True,
            data=VoiceProfileData(
                profile_id=record.profile_id,
                name=record.name,
                provider=record.provider_id,
                status="ready",
                reference=ReferenceAudioInfo(
                    duration_seconds=record.duration_seconds,
                    sample_rate=record.sample_rate,
                    channels=record.channels,
                ),
            ),
        )

    def get_profile_record(self, profile_id: str) -> VoiceProfileRecord:
        if not isinstance(profile_id, str) or not UUID_RE.fullmatch(profile_id):
            raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_FOUND)
        with self._lock:
            record = self._records.get(profile_id)
        if record is None:
            raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_FOUND)
        return record

    def list_profiles(self) -> VoiceProfileListResponse:
        with self._lock:
            records = list(self._records.values())
        return VoiceProfileListResponse(
            ok=True,
            data=[
                VoiceProfileData(
                    profile_id=rec.profile_id,
                    name=rec.name,
                    provider=rec.provider_id,
                    status="ready",
                    reference=ReferenceAudioInfo(
                        duration_seconds=rec.duration_seconds,
                        sample_rate=rec.sample_rate,
                        channels=rec.channels,
                    ),
                )
                for rec in records
            ],
        )

    def delete_profile(self, profile_id: str) -> None:
        if not isinstance(profile_id, str) or not UUID_RE.fullmatch(profile_id):
            raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_FOUND)
        with self._lock:
            if profile_id in self._records and self._records[profile_id].active_jobs:
                raise ApplicationError(ErrorCode.PROFILE_IN_USE)
            record = self._records.get(profile_id)
            if record is not None:
                self._db.delete_profile(profile_id)
                self._records.pop(profile_id)
        if record is None:
            raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_FOUND)

        if record.reference_path:
            reference = Path(record.reference_path).resolve()
            if reference.is_relative_to((self._output_dir / 'references').resolve()):
                reference.unlink(missing_ok=True)

        # Release provider prompt if provider has internal _profiles dict
        try:
            provider = self._provider_service.get_primary_provider()
            prov_profiles = getattr(provider, "_profiles", None)
            if isinstance(prov_profiles, dict) and hasattr(record.provider_profile, "profile_id"):
                prov_profiles.pop(record.provider_profile.profile_id, None)
        except Exception:
            pass

        logger.info("voice_profile_deleted profile_id=%s", profile_id)

    def reserve_profile(self, profile_id: str) -> VoiceProfileRecord:
        """Resolve once and pin atomically, including time spent queued."""
        if not isinstance(profile_id, str) or not UUID_RE.fullmatch(profile_id):
            raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_FOUND)
        with self._lock:
            record = self._records.get(profile_id)
            if record is None:
                raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_FOUND)
            record.active_jobs += 1
            return record

    def release_profile(self, record: VoiceProfileRecord) -> None:
        with self._lock:
            record.active_jobs -= 1

    @serialized_inference
    def synthesize_clone(self, profile_id: str, request: CloneTestRequest) -> CloneTTSResponse:
        # 1. Resolve profile
        record = self.get_profile_record(profile_id)

        # 2. Validate request
        text = request.text
        if text is None or not isinstance(text, str) or not text.strip():
            raise ApplicationError(ErrorCode.INVALID_TEXT)
        cleaned_text = text.strip()
        if len(cleaned_text) > MAX_TEXT_LENGTH:
            raise ApplicationError(ErrorCode.TEXT_TOO_LONG)

        language = request.language
        if not isinstance(language, str) or language_status(language) != VERIFIED:
            raise ApplicationError(ErrorCode.LANGUAGE_NOT_SUPPORTED)

        speed = request.speed
        if speed is None or isinstance(speed, bool) or not isinstance(speed, (int, float)):
            raise ApplicationError(ErrorCode.INVALID_SPEED)
        if not (0.5 <= speed <= 2.0) or float(speed) != 1.0:
            raise ApplicationError(ErrorCode.INVALID_SPEED)
        speed = float(speed)

        fmt = request.format
        if not isinstance(fmt, str) or fmt.lower() not in ("wav", "mp3"):
            raise ApplicationError(ErrorCode.INVALID_FORMAT)
        fmt = fmt.lower()

        record = self.reserve_profile(profile_id)
        try:
            with self._db.generation('clone', {'request': request.model_dump(),
                    'provider_id': record.provider_id, 'profile_revision': record.created_at,
                    'provider_version': None, 'model_revision': None, 'seed': None,
                    'normalizer_version': 'strip-v1', 'chunker_version': None,
                    'audio': {'sample_rate': 24000, 'channels': 1, 'format': fmt}}, profile_id) as job:
                return self._generate_clone(record, cleaned_text, language, fmt, job)
        finally:
            self.release_profile(record)

    def _generate_clone(self, record, cleaned_text, language, fmt, job):
        profile_id = record.profile_id

        # 3. Ensure primary provider loaded
        provider = self._provider_service.ensure_primary_provider_loaded()

        self.restore_profile(record)

        generation_id = job.job_id
        wav_path = self._output_dir / f"{generation_id}.wav"

        try:
            result = provider.synthesize_cloned(
                text=cleaned_text,
                language=language,
                profile=record.provider_profile,
                output_path=wav_path,
            )
        except Exception as exc:
            logger.error("clone_synthesis_exception generation_id=%s error=%s", generation_id, exc)
            if wav_path.is_file():
                try:
                    wav_path.unlink()
                except Exception:
                    pass
            raise ApplicationError(ErrorCode.CLONE_GENERATION_FAILED) from None

        if result.status != "PASS" or not wav_path.is_file():
            logger.error(
                "clone_generation_failed generation_id=%s provider=%s language=%s error=%s",
                generation_id, provider.provider_name(), language, result.error,
            )
            if wav_path.is_file():
                try:
                    wav_path.unlink()
                except Exception:
                    pass
            raise ApplicationError(ErrorCode.CLONE_GENERATION_FAILED)

        # 4. Validate output audio properties
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
            raise ApplicationError(ErrorCode.CLONE_GENERATION_FAILED) from None

        # 5. Optional MP3 export
        if fmt == "mp3":
            mp3_path = self._output_dir / f"{generation_id}.mp3"
            exported = export_mp3(wav_path, mp3_path)
            if exported is None or not mp3_path.is_file() or mp3_path.stat().st_size == 0:
                logger.error("audio_export_failed generation_id=%s wav_retained=true", generation_id)
                raise ApplicationError(ErrorCode.AUDIO_EXPORT_FAILED)

        with self._lock:
            record.use_count += 1
            self._persist(record)

        logger.info(
            "clone_tts_completed generation_id=%s profile_id=%s provider=%s language=%s format=%s duration=%.2f text_length=%d gen_time=%.2f",
            generation_id, profile_id, result.provider_id, language, fmt, duration, len(cleaned_text), result.gen_time,
        )

        self._db.complete_generation(job, f'/api/audio/{generation_id}.{fmt}',
            [wav_path] + ([mp3_path] if fmt == 'mp3' else []),
            {'duration_seconds': duration, 'provider_id': result.provider_id})
        return CloneTTSResponse(
            ok=True,
            data=CloneTTSData(
                generation_id=generation_id,
                profile_id=profile_id,
                status="completed",
                provider=result.provider_id,
                language=language,
                duration_seconds=round(duration, 3),
                sample_rate=sample_rate,
                channels=1,
                format=fmt,
                audio_url=f"/api/audio/{generation_id}.{fmt}",
            ),
        )
