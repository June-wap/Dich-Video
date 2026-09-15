"""Application TTS service: request validation, provider coordination, synthesis, and safe artifact export."""
from __future__ import annotations

import logging
from pathlib import Path
import wave

from backend.config import Settings
from backend.errors import ApplicationError, ErrorCode
from backend.schemas.tts import TTSData, TTSRequest, TTSResponse
from backend.services.provider_service import ProviderService
from backend.services.execution import serialized_inference
from core.audio_utils import export_mp3
from core.languages import VERIFIED, language_status
from backend.persistence import Repository

logger = logging.getLogger("backend.tts")
MAX_TEXT_LENGTH = 2000


class TTSService:
    def __init__(self, settings: Settings, provider_service: ProviderService):
        self._settings = settings
        self._provider_service = provider_service
        self._output_dir = Path(settings.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._db = Repository(settings)
        # Explicit allowlist: do not serialize environment, credentials or auth configuration.
        self._db.put('settings', 'runtime', {
            'primary_tts_provider': settings.primary_tts_provider,
            'omnivoice_device': settings.omnivoice_device, 'app_version': settings.app_version})

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    def validate_request(self, request: TTSRequest) -> tuple[str, str, str, float, str]:
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

        # Voice validation against provider without triggering model load
        provider = self._provider_service.get_primary_provider()
        voices = provider.list_voices(language)
        valid_voices = {v.id for v in voices}
        for voice in voices:
            self._db.put('voices', voice.id, {'id': voice.id, 'provider_id': provider.provider_name()})
        voice_id = request.voice_id
        if not voice_id:
            voice_id = "omnivoice_auto"
        if not isinstance(voice_id, str) or voice_id not in valid_voices:
            raise ApplicationError(ErrorCode.VOICE_NOT_FOUND)

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

        return cleaned_text, language, voice_id, speed, fmt

    @serialized_inference
    def synthesize(self, request: TTSRequest) -> TTSResponse:
        text, language, voice_id, speed, fmt = self.validate_request(request)

        with self._db.generation('short', {'request': request.model_dump(),
                'provider_id': self._settings.primary_tts_provider, 'provider_version': None,
                'model_revision': None, 'voice_revision': None, 'seed': None,
                'normalizer_version': 'strip-v1', 'chunker_version': None,
                'audio': {'sample_rate': 24000, 'channels': 1, 'format': fmt}}) as job:
            return self._generate(text, language, voice_id, speed, fmt, job)

    def _generate(self, text, language, voice_id, speed, fmt, job):

        # Ensure primary provider is loaded (lazy model load)
        provider = self._provider_service.ensure_primary_provider_loaded()

        generation_id = job.job_id
        wav_path = self._output_dir / f"{generation_id}.wav"

        try:
            result = provider.synthesize(
                text=text,
                language=language,
                voice=voice_id,
                output_path=wav_path,
                speed=speed,
            )
        except Exception as exc:
            logger.error("tts_synthesis_exception generation_id=%s error=%s", generation_id, exc)
            if wav_path.is_file():
                try:
                    wav_path.unlink()
                except Exception:
                    pass
            raise ApplicationError(ErrorCode.GENERATION_FAILED) from None

        if result.status != "PASS" or not wav_path.is_file():
            logger.error("tts_generation_failed generation_id=%s provider=%s language=%s error=%s",
                         generation_id, provider.provider_name(), language, result.error)
            if wav_path.is_file():
                try:
                    wav_path.unlink()
                except Exception:
                    pass
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

        # Optional MP3 export
        if fmt == "mp3":
            mp3_path = self._output_dir / f"{generation_id}.mp3"
            exported = export_mp3(wav_path, mp3_path)
            if exported is None or not mp3_path.is_file() or mp3_path.stat().st_size == 0:
                logger.error("audio_export_failed generation_id=%s wav_retained=true", generation_id)
                raise ApplicationError(ErrorCode.AUDIO_EXPORT_FAILED)

        logger.info("tts_completed generation_id=%s provider=%s language=%s voice_id=%s format=%s duration=%.2f text_length=%d gen_time=%.2f",
                    generation_id, result.provider_id, language, voice_id, fmt, duration, len(text), result.gen_time)

        self._db.complete_generation(job, f'/api/audio/{generation_id}.{fmt}',
            [wav_path] + ([mp3_path] if fmt == 'mp3' else []),
            {'duration_seconds': duration, 'provider_id': result.provider_id})
        return TTSResponse(
            ok=True,
            data=TTSData(
                generation_id=generation_id,
                status="completed",
                provider=result.provider_id,
                language=language,
                voice_id=voice_id,
                duration_seconds=round(duration, 3),
                sample_rate=sample_rate,
                channels=1,
                format=fmt,
                audio_url=f"/api/audio/{generation_id}.{fmt}",
            )
        )
