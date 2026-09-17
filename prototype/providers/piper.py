"""Piper provider: fixed, per-language dedicated voice models (CP0 POC promoted
to the backend). No voice cloning, no GPU - CPU-only via onnxruntime.

Scope (deliberately narrow, decided with the project owner on 2026-09-16):
only the six languages whose candidate voice package is PENDING (not
REJECTED) in docs/model_license_matrix.md are wired here - en/es/pt/fr/it/zh.
Japanese and Hindi Piper voices exist in the same CP0 checkpoint but are
REJECTED for the proposed commercial catalogue (CC-BY-NC-SA-4.0 datasets, no
commercial grant), so they are intentionally NOT registered as usable
languages by this provider; requests for "ja"/"hi" keep going to the primary
(OmniVoice) provider exactly as before, unchanged by this file.

IMPORTANT - license status: piper-tts itself is GPL-3.0-or-later and the six
voice packages here are still PENDING (not APPROVED) per the license matrix.
This integration makes the six languages technically usable end-to-end; it
does NOT close the licensing gap. Do not represent this as commercially
cleared without a real license review sign-off.

IMPORTANT - model file location: the six .onnx/.onnx.json pairs this provider
loads currently live under `<repo_root>/.cp0/models/piper/...`, which is a
gitignored checkpoint/scratch directory (see CP0's own note: "no combined
runtime + voice package is approved for production"). Referencing them there
was a deliberate pragmatic choice to avoid a slow bulk file transfer through
the remote-device bridge. If `.cp0` is ever cleaned up/deleted, these six
voice folders must be moved to a permanent location first and MODELS_ROOT
below updated to match - otherwise this provider will fail to load.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import threading
import time
import wave
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.languages import LANGUAGES as CORE_LANGUAGES

from .base import AudioSynthResult, ManagedTTSProvider, VoiceInfo

logger = logging.getLogger("backend.providers.piper")

_CORE_LANGUAGE_INFO = {item.id: item for item in CORE_LANGUAGES}


class PiperError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f"{code}: {message}")


@contextmanager
def _quiet_piper_logs():
    # onnxruntime/piper can be chatty at INFO/WARNING; keep application logs clean.
    logger_obj = logging.getLogger("piper")
    suppress = lambda record: False
    logger_obj.addFilter(suppress)
    try:
        yield
    finally:
        logger_obj.removeFilter(suppress)


class PiperProvider(ManagedTTSProvider):
    PROVIDER_ID = "piper"
    SAMPLE_RATE = 24000  # Piper's native rate varies per voice; always resampled to this.
    AUTO_VOICE_ID = "piper_auto"

    # language id -> Piper voice package name (matches .cp0/models/piper/<name>/<name>.onnx)
    VOICE_MAP = {
        "en": "en_US-lessac-medium",
        "es": "es_ES-davefx-medium",
        "pt": "pt_BR-faber-medium",
        "fr": "fr_FR-siwis-medium",
        "it": "it_IT-riccardo-x_low",
        "zh": "zh_CN-huayan-medium",
    }
    LANGUAGES = tuple(VOICE_MAP.keys())

    MODELS_ROOT = Path(__file__).resolve().parents[2] / ".cp0" / "models" / "piper"

    def __init__(self):
        self._voices: dict[str, object] = {}
        self._lock = threading.RLock()
        self._load_time = 0.0

    def provider_name(self):
        return self.PROVIDER_ID

    def capabilities(self):
        language_metadata = []
        for language_id in self.LANGUAGES:
            info = _CORE_LANGUAGE_INFO[language_id]
            language_metadata.append({
                "id": info.id, "display_name": info.display_name, "native_name": info.native_name,
                "status": "VERIFIED",
                "verification_scope": "CP0 Piper POC: PCM audio validated (non-silent, non-clipping); "
                                      "no subjective/listening content QA performed",
                "cloned_live_verified": False,
                "production_ready": False,
            })
        return {
            "provider_id": self.PROVIDER_ID,
            "languages": list(self.LANGUAGES),
            "verified_languages": list(self.LANGUAGES),
            "language_metadata": language_metadata,
            "experimental_upstream_languages": [],
            "experimental_languages_enabled": False,
            "language_policy": "One fixed dedicated voice per language; no aliases, no cloning",
            "cloned_live_verified_languages": [],
            "verification_source": "scripts/cp0_benchmark.py (engineering PCM validation only)",
            "verification_scope": "CP0 checkpoint promoted to backend; content/pronunciation not independently verified",
            "sample_rate": self.SAMPLE_RATE, "channels": 1,
            "short_tts": True, "voice_cloning": False, "reusable_voice_profiles": False, "long_text": False,
            "voice_selection": "auto", "cpu_verified": True,
            "production_ready": False,
        }

    def list_languages(self):
        return list(self.LANGUAGES)

    def list_voices(self, language):
        if language not in self.LANGUAGES:
            return []
        return [VoiceInfo(self.AUTO_VOICE_ID, f"Piper Auto ({language})", language,
                          provider=self.PROVIDER_ID, model=self.VOICE_MAP[language],
                          sample_rate=self.SAMPLE_RATE)]

    def is_loaded(self):
        with self._lock:
            return len(self._voices) == len(self.LANGUAGES)

    def _model_path(self, language: str) -> Path:
        name = self.VOICE_MAP[language]
        return self.MODELS_ROOT / name / f"{name}.onnx"

    def load(self):
        with self._lock:
            if self.is_loaded():
                return self
            started = time.perf_counter()
            try:
                from piper import PiperVoice
            except Exception as exc:
                raise PiperError("MODEL_LOAD_FAILED", f"piper-tts is not installed: {exc}") from exc
            for language in self.LANGUAGES:
                if language in self._voices:
                    continue
                path = self._model_path(language)
                if not path.is_file():
                    raise PiperError("MODEL_LOAD_FAILED", f"Missing Piper voice file: {path}")
                try:
                    with _quiet_piper_logs():
                        self._voices[language] = PiperVoice.load(str(path), use_cuda=False)
                except Exception as exc:
                    raise PiperError("MODEL_LOAD_FAILED", f"Failed to load Piper voice for '{language}': {exc}") from exc
            self._load_time = time.perf_counter() - started
            return self

    def unload(self):
        with self._lock:
            self._voices.clear()

    @staticmethod
    def _resample_to_target(native_wav_path: Path, output_path: Path, target_rate: int):
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-nostdin", "-i", str(native_wav_path),
                 "-ar", str(target_rate), "-ac", "1", "-acodec", "pcm_s16le", str(output_path)],
                capture_output=True, timeout=60, check=True)
        except FileNotFoundError:
            raise PiperError("EXPORT_FAILED", "ffmpeg is required to resample Piper output") from None
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else str(exc.stderr)
            raise PiperError("EXPORT_FAILED", f"ffmpeg resample failed: {stderr[:300]}") from None

    def synthesize(self, text, language, voice=AUTO_VOICE_ID, output_path=None, speed=1.0, **options):
        return self._synthesize(text, language, voice, output_path, speed, **options)

    def _synthesize(self, text, language, voice=AUTO_VOICE_ID, output_path=None, speed=1.0, **options):
        result = AudioSynthResult(provider=self.PROVIDER_ID, model=self.VOICE_MAP.get(language, ""),
                                  language=language if isinstance(language, str) else "", voice=voice, device="cpu")
        try:
            if not isinstance(text, str) or not text.strip():
                raise PiperError("INVALID_TEXT", "Text must be non-empty")
            if language not in self.LANGUAGES:
                raise PiperError("LANGUAGE_NOT_SUPPORTED", "Piper provider only serves its six dedicated voices")
            if voice != self.AUTO_VOICE_ID:
                raise PiperError("VOICE_NOT_FOUND", str(voice))
            if options or speed != 1.0:
                raise PiperError("INVALID_OPTIONS", "Piper provider supports auto-voice TTS at default speed only")

            with self._lock:
                self.load()
                voice_model = self._voices[language]
                started = time.perf_counter()
                tmp_path = None
                try:
                    from piper import SynthesisConfig
                    fd, tmp_name = tempfile.mkstemp(suffix=".wav", prefix="piper_native_")
                    os.close(fd)
                    tmp_path = Path(tmp_name)
                    with _quiet_piper_logs():
                        with wave.open(str(tmp_path), "wb") as stream:
                            stream.setparams((1, 2, voice_model.config.sample_rate, 0, "NONE", "not compressed"))
                            voice_model.synthesize_wav(text.strip(), stream, syn_config=SynthesisConfig(speaker_id=0))

                    if not tmp_path.is_file() or tmp_path.stat().st_size == 0:
                        raise PiperError("GENERATION_FAILED", "Piper produced no output")

                    if output_path is not None:
                        out_path = Path(output_path)
                        out_path.parent.mkdir(parents=True, exist_ok=True)
                        self._resample_to_target(tmp_path, out_path, self.SAMPLE_RATE)
                        with wave.open(str(out_path), "rb") as check:
                            channels, rate, n_frames = check.getnchannels(), check.getframerate(), check.getnframes()
                        if channels != 1 or rate != self.SAMPLE_RATE or n_frames <= 0:
                            raise PiperError("GENERATION_FAILED", "Resampled Piper output has unexpected format")
                        result.wav_path = str(out_path)
                        result.duration = n_frames / self.SAMPLE_RATE
                        with wave.open(str(out_path), "rb") as check:
                            raw = check.readframes(n_frames)
                        audio = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
                        if not audio.size or not np.isfinite(audio).all():
                            raise PiperError("GENERATION_FAILED", "Resampled Piper output is empty/non-finite")
                        result.audio = np.ascontiguousarray(audio)
                    else:
                        with wave.open(str(tmp_path), "rb") as check:
                            n_frames, native_rate = check.getnframes(), check.getframerate()
                        if n_frames <= 0:
                            raise PiperError("GENERATION_FAILED", "Piper produced empty audio")
                        result.duration = n_frames / native_rate
                finally:
                    if tmp_path is not None:
                        try:
                            tmp_path.unlink()
                        except Exception:
                            pass

                result.gen_time = time.perf_counter() - started
                result.sample_rate = self.SAMPLE_RATE
                result.rtf = (result.gen_time / result.duration) if result.duration else 0.0
                result.text_length = len(text.strip())
                result.metadata = {
                    "channels": 1, "dtype": "int16", "device": "cpu", "engine": "piper",
                    "voice_model": self.VOICE_MAP.get(language), "cloning_supported": False,
                }
        except PiperError as exc:
            result.status = "FAIL"
            result.error = str(exc)
            result.metadata["error_code"] = exc.code
        result.metadata["diagnostics"] = {
            "provider": self.PROVIDER_ID,
            "language": language if isinstance(language, str) else None,
            "device": "cpu",
            "verification_scope": "CP0 Piper POC: PCM validated only, no subjective/content QA",
            "cloned_live_verified": False,
            "generation_time": result.gen_time,
            "duration": result.duration, "rtf": result.rtf,
            "status": result.status,
        }
        return result

    def health_check(self):
        with self._lock:
            loaded_languages = list(self._voices)
        return {"provider": self.PROVIDER_ID, "device": "cpu",
                "loaded_languages": loaded_languages,
                "status": "LOADED" if self.is_loaded() else "UNLOADED",
                "cpu_verified": True}
