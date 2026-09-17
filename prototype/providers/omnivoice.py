"""CP0.2A: short local TTS and model lifecycle, without UI dependencies."""
from __future__ import annotations

import gc
import io
import logging
from contextlib import contextmanager
import subprocess
import uuid
from dataclasses import dataclass
import threading
import time
from pathlib import Path

import numpy as np

from core.languages import (VERIFIED_LANGUAGE_IDS, EXPERIMENTAL_LANGUAGE_IDS,
                            VERIFIED, language_status, language_metadata)

from .base import AudioSynthResult, ManagedTTSProvider, VoiceInfo


def _trim_silence(audio: np.ndarray, sample_rate: int, threshold_dbfs: float = -48.0,
                   preserve_ms: int = 35, max_trim_ms: int = 250) -> np.ndarray:
    """Trim only confidently-silent leading/trailing samples, capped and padded.

    Deliberately conservative and self-contained (no pydub/ffmpeg dependency,
    since `audio` here is already a raw float32 numpy array, not a file) -
    mirrors the defaults of core/audio_utils.py's BoundaryDSPConfig, which
    does the equivalent job for long-form segment boundaries via pydub. Never
    trims more than max_trim_ms from either edge, and always leaves
    preserve_ms of near-silence in place, so a quiet intake breath or the
    natural decay of the last word can never be clipped.
    """
    if audio.size == 0:
        return audio
    threshold_amplitude = 10 ** (threshold_dbfs / 20.0)
    above_threshold = np.flatnonzero(np.abs(audio) > threshold_amplitude)
    if above_threshold.size == 0:
        # Entire clip reads as silence - nothing safe to trim from either end.
        return audio
    preserve_samples = int(sample_rate * preserve_ms / 1000)
    max_trim_samples = int(sample_rate * max_trim_ms / 1000)
    leading = max(0, min(max_trim_samples, int(above_threshold[0]) - preserve_samples))
    trailing = max(0, min(max_trim_samples, (audio.size - 1 - int(above_threshold[-1])) - preserve_samples))
    end = audio.size - trailing
    if end <= leading:
        return audio
    return audio[leading:end]


class OmniVoiceError(RuntimeError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f"{code}: {message}")


@contextmanager
def _private_runtime_logs():
    # Runtime DEBUG messages may include text. Never propagate them for cloning.
    logger = logging.getLogger("omnivoice.models.omnivoice")
    suppress = lambda record: False
    logger.addFilter(suppress)
    try:
        yield
    finally:
        logger.removeFilter(suppress)


@dataclass(frozen=True)
class VoiceProfile:
    """Opaque in-memory handle. No audio, transcript or prompt in repr/serialization."""
    profile_id: str
    provider_id: str
    reference_duration: float


class OmniVoiceProvider(ManagedTTSProvider):
    PROVIDER_ID = "omnivoice"
    LANGUAGES = VERIFIED_LANGUAGE_IDS
    SAMPLE_RATE = 24000

    def __init__(self, model_id="k2-fsa/OmniVoice", device="cuda:0",
                 allow_unverified_cpu=False):
        self.model_id = str(model_id)
        self.device = device
        self.allow_unverified_cpu = allow_unverified_cpu
        self._model = None
        self._torch = None
        self._lock = threading.RLock()
        self._load_time = 0.0
        self._load_count = 0
        self._profiles = {}

    def provider_name(self):
        return self.PROVIDER_ID

    def capabilities(self):
        return {
            "provider_id": self.PROVIDER_ID,
            "languages": list(self.LANGUAGES),
            "verified_languages": list(self.LANGUAGES),
            "language_metadata": language_metadata(),
            "experimental_upstream_languages": list(EXPERIMENTAL_LANGUAGE_IDS),
            "experimental_languages_enabled": False,
            "language_policy": "Exact canonical IDs only; no fallback",
            "cloned_live_verified_languages": ["vi"],
            "verification_source": "external/OmniVoice/benchmark_results.json",
            "verification_scope": "Existing CUDA short-TTS baseline; not production certification",
            "sample_rate": self.SAMPLE_RATE, "channels": 1,
            "short_tts": True, "voice_cloning": True, "reusable_voice_profiles": True, "long_text": False,
            "voice_selection": "auto", "cpu_verified": False,
            "production_ready": False,
        }

    def list_languages(self):
        return list(self.LANGUAGES)

    def list_voices(self, language):
        if language_status(language) != VERIFIED:
            return []
        return [VoiceInfo("omnivoice_auto", "OmniVoice Auto", language,
                          provider=self.PROVIDER_ID, model=self.model_id,
                          sample_rate=self.SAMPLE_RATE)]

    def is_loaded(self):
        with self._lock:
            return self._model is not None

    def _load_model(self):
        # Runtime imports stay inside this provider. Never download implicitly.
        import torch
        from omnivoice import OmniVoice
        from huggingface_hub import snapshot_download

        self._torch = torch
        if self.device == "cpu":
            if not self.allow_unverified_cpu:
                raise ValueError("CPU is unverified; explicitly enable experimental CPU to use it")
            dtype = torch.float32
        elif str(self.device).startswith("cuda"):
            if not torch.cuda.is_available():
                raise ValueError("CUDA unavailable; no automatic CPU fallback")
            dtype = torch.float16
        else:
            raise ValueError(f"Unsupported device: {self.device}")
        path = Path(self.model_id)
        if not path.is_dir():
            path = Path(snapshot_download(self.model_id, local_files_only=True))
        if not (path / "audio_tokenizer").is_dir():
            raise ValueError("Local model must include audio_tokenizer; automatic downloads disabled")
        return OmniVoice.from_pretrained(str(path), device_map=self.device,
                                         dtype=dtype, local_files_only=True)

    def load(self):
        with self._lock:
            if self._model is not None:
                return self
            started = time.perf_counter()
            try:
                model = self._load_model()
                if getattr(model, "sampling_rate", None) != self.SAMPLE_RATE:
                    raise ValueError("Expected native 24000 Hz model; resampling is outside CP0.2A")
                model.eval()
            except Exception as exc:
                raise OmniVoiceError("MODEL_LOAD_FAILED", str(exc)) from exc
            self._model = model
            self._load_time = time.perf_counter() - started
            self._load_count += 1
            return self

    def _synchronize(self):
        if self._torch is not None and str(self.device).startswith("cuda"):
            self._torch.cuda.synchronize(self.device)

    @staticmethod
    def _decode_reference(reference_audio):
        # libsndfile sniffs content. FFmpeg handles AAC/MP4 even with an .mp3 name.
        import soundfile as sf
        try:
            path = Path(reference_audio)
            if not path.is_file():
                raise ValueError()
            try:
                # FFmpeg probes container bytes; avoid libsndfile's MP3 resync
                # path on mislabeled AAC containers, which can stall.
                decoded = subprocess.run(
                    ["ffmpeg", "-v", "error", "-nostdin", "-i", str(path.resolve()),
                     "-map", "0:a:0", "-f", "wav", "-acodec", "pcm_f32le", "pipe:1"],
                    capture_output=True, timeout=60, check=True)
                samples, rate = sf.read(io.BytesIO(decoded.stdout), dtype="float32", always_2d=True)
            except FileNotFoundError:
                # WAV/FLAC remain usable without FFmpeg. Do not hand unknown
                # compressed containers to a decoder selected by extension.
                with path.open("rb") as source:
                    header = source.read(12)
                if not (header[:4] == b"fLaC" or (header[:4] == b"RIFF" and header[8:12] == b"WAVE")):
                    raise ValueError()
                samples, rate = sf.read(path, dtype="float32", always_2d=True)
            if rate <= 0 or not samples.size or not np.isfinite(samples).all():
                raise ValueError()
            if not np.any(samples):
                raise ValueError()
            return np.ascontiguousarray(samples.T), rate
        except Exception:
            raise OmniVoiceError("INVALID_REFERENCE_AUDIO", "Reference is missing, undecodable or empty") from None

    def create_voice_profile(self, reference_audio, reference_transcript):
        if not isinstance(reference_transcript, str) or not reference_transcript.strip():
            raise OmniVoiceError("INVALID_REFERENCE_TRANSCRIPT", "Exact reference transcript is required")
        samples, rate = self._decode_reference(reference_audio)
        with self._lock:
            self.load()
            try:
                with _private_runtime_logs():
                    prompt = self._model.create_voice_clone_prompt(
                        ref_audio=(samples, rate), ref_text=reference_transcript,
                        preprocess_prompt=False)
                tokens = getattr(prompt, "ref_audio_tokens", None)
                if (getattr(prompt, "ref_text", None) != reference_transcript
                        or getattr(tokens, "ndim", 0) != 2
                        or not all(d > 0 for d in tokens.shape)):
                    raise ValueError()
            except Exception:
                raise OmniVoiceError("VOICE_PROFILE_FAILED", "Unable to prepare reference prompt") from None
            profile = VoiceProfile(uuid.uuid4().hex, self.PROVIDER_ID, samples.shape[-1] / rate)
            self._profiles[profile.profile_id] = (profile, prompt)
            return profile

    DEFAULT_CLONE_NUM_STEP = 24
    DEFAULT_NORMAL_NUM_STEP = 16

    def synthesize_cloned(self, text, language, profile, output_path=None, num_step=DEFAULT_CLONE_NUM_STEP,
                          trim_silence=False):
        return self._synthesize(text, language, output_path=output_path, profile=profile,
                                cloned=True, num_step=num_step, trim_silence=trim_silence)

    def synthesize(self, text, language, voice="omnivoice_auto", output_path=None,
                   speed=1.0, **options):
        return self._synthesize(text, language, voice, output_path, speed, **options)

    def _synthesize(self, text, language, voice="omnivoice_auto", output_path=None,
                    speed=1.0, *, profile=None, cloned=False, num_step=None, trim_silence=False, **options):
        result = AudioSynthResult(provider=self.PROVIDER_ID, model=self.model_id,
                                  language=language if isinstance(language, str) else "", voice=voice, device=self.device)
        inference_dtype = None
        try:
            if not isinstance(text, str) or not text.strip():
                raise OmniVoiceError("INVALID_TEXT", "Text must be non-empty")
            if language_status(language) != VERIFIED:
                raise OmniVoiceError("LANGUAGE_NOT_SUPPORTED", "Only the nine verified canonical IDs are enabled")
            if voice != "omnivoice_auto":
                raise OmniVoiceError("VOICE_NOT_FOUND", str(voice))
            if options or speed != 1.0:
                raise OmniVoiceError("INVALID_OPTIONS", "CP0.2A supports short auto-voice TTS at default speed only")
            with self._lock:
                prompt_options = {}
                if cloned:
                    entry = self._profiles.get(profile.profile_id) if isinstance(profile, VoiceProfile) else None
                    if entry is None or entry[0] is not profile:
                        raise OmniVoiceError("INVALID_VOICE_PROFILE", "Profile is invalid, foreign or released")
                    prompt_options["voice_clone_prompt"] = entry[1]
                    result.voice = profile.profile_id
                already_loaded = self.is_loaded()
                self.load()
                inference_dtype = self._model_dtype()
                result.load_time = 0.0 if already_loaded else self._load_time
                self._synchronize()
                started = time.perf_counter()
                step_val = (self.DEFAULT_CLONE_NUM_STEP if cloned else self.DEFAULT_NORMAL_NUM_STEP) if num_step is None else int(num_step)
                try:
                    with _private_runtime_logs():
                        generated = self._model.generate(text=text.strip(), language=language,
                                                         num_step=step_val, **prompt_options)
                    self._synchronize()
                    if len(generated) != 1:
                        raise ValueError("Expected one audio output")
                    raw = generated[0]
                    if hasattr(raw, "detach"):
                        raw = raw.detach().cpu().numpy()
                    audio = np.asarray(raw, dtype=np.float32)
                    if audio.ndim == 2 and 1 in audio.shape:
                        audio = audio.reshape(-1)
                    if audio.ndim != 1 or not audio.size or not np.isfinite(audio).all():
                        raise ValueError("Expected non-empty finite mono audio")
                    audio = np.ascontiguousarray(audio)
                    if trim_silence:
                        trimmed = _trim_silence(audio, self.SAMPLE_RATE)
                        if trimmed.size:
                            audio = np.ascontiguousarray(trimmed)
                        # else: trimming would have removed the entire clip
                        # (shouldn't happen given _trim_silence's own guards,
                        # but never ship an empty file) - keep the untrimmed
                        # audio rather than fail an otherwise-successful job.
                except Exception as exc:
                    raise OmniVoiceError("GENERATION_FAILED", "Cloned synthesis failed" if cloned else str(exc)) from None
                result.gen_time = time.perf_counter() - started
                result.audio = audio
                result.sample_rate = self.SAMPLE_RATE
                result.duration = audio.size / self.SAMPLE_RATE
                result.rtf = result.gen_time / result.duration
                result.text_length = len(text.strip())
                result.metadata = {"num_step": step_val, "channels": 1, "dtype": "float32",
                                   "load_count": self._load_count, "silence_trim_applied": bool(trim_silence),
                                   "cpu_verified": False, "model_reused": already_loaded}
                if output_path is not None:
                    try:
                        import soundfile as sf
                        path = Path(output_path)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        sf.write(path, audio, self.SAMPLE_RATE, subtype="PCM_16")
                        result.wav_path = str(path)
                    except Exception as exc:
                        raise OmniVoiceError("EXPORT_FAILED", str(exc)) from exc
        except OmniVoiceError as exc:
            result.status = "FAIL"
            result.error = str(exc)
            result.metadata["error_code"] = exc.code
        result.metadata["diagnostics"] = {
            "provider": self.PROVIDER_ID,
            "language": language if isinstance(language, str) else None,
            "language_status": language_status(language),
            "device": self.device,
            "dtype": inference_dtype,
            "verification_scope": "CUDA normal short TTS baseline",
            "cloned_live_verified": language == "vi" if cloned else None,
            "audio_dtype": str(result.audio.dtype) if result.audio is not None else None,
            "generation_time": result.gen_time,
            "duration": result.duration, "rtf": result.rtf,
            "mode": "cloned" if cloned else "normal",
            "status": result.status,
        }
        return result

    def _model_dtype(self):
        if self._model is None:
            return None
        dtype = str(getattr(self._model, "dtype", ""))
        return dtype.removeprefix("torch.") if dtype in (
            "torch.float16", "torch.float32", "torch.bfloat16",
            "float16", "float32", "bfloat16") else None

    def unload(self):
        with self._lock:
            if self._model is None:
                return
            self._profiles.clear()
            self._model = None
            gc.collect()
            if self._torch is not None and str(self.device).startswith("cuda"):
                with self._torch.cuda.device(self.device):
                    self._torch.cuda.empty_cache()

    def health_check(self):
        return {"provider": self.PROVIDER_ID, "model_path": self.model_id,
                "device": self.device, "loaded": self.is_loaded(),
                "status": "LOADED" if self.is_loaded() else "UNLOADED",
                "load_count": self._load_count, "cpu_verified": False}
