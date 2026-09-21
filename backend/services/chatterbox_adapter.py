"""Pinned, CUDA-only Chatterbox Multilingual V3 baseline TTS adapter.

This module intentionally has no top-level Chatterbox, PyTorch, torchaudio, or
Hugging Face imports.  The normal VieNeu runtime does not install Chatterbox;
constructing this adapter and importing this module must therefore remain safe
in that environment.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
import time
import wave
from pathlib import Path
from threading import RLock

from backend.services.provider_base import AudioSynthResult, VoiceInfo
from backend.core.languages import CHATTERBOX_LANGUAGE_IDS


class ChatterboxLocalGpuUnavailable(RuntimeError):
    """The local CUDA-only Chatterbox backend cannot run on this machine."""


class ChatterboxGpuResourceInsufficient(RuntimeError):
    """The local GPU could not allocate enough memory for Chatterbox."""


class ChatterboxAdapter:
    """Official Chatterbox Multilingual V3, pinned for local CUDA inference.

    This is a baseline-only provider.  It deliberately exposes no cloning
    methods and is not registered in the production provider registry yet.
    """

    PROVIDER_ID = "chatterbox"
    SOURCE_REPOSITORY = "https://github.com/resemble-ai/chatterbox"
    SOURCE_REVISION = "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
    MODEL_REPOSITORY = "ResembleAI/chatterbox"
    MODEL_REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
    T3_MODEL = "v3"
    T3_CHECKPOINT = "t3_mtl23ls_v3.safetensors"
    DEFAULT_VOICE_ID = "chatterbox_default"
    CANGJIE_FILENAME = "Cangjie5_TC.json"
    CANGJIE_SIZE_BYTES = 1_920_163
    CANGJIE_SHA256 = "7073fd9de919443ae88e0bd2449917a65fe54898a4413ed1edcc4b67f28bce8c"

    # This is the exact V3 loader dependency set in the pinned upstream
    # `mtl_tts.py`.  Passing it to snapshot_download keeps all weights and
    # tokenizer assets at the immutable model revision before from_local().
    _MODEL_FILES = (
        "ve.pt",
        T3_CHECKPOINT,
        "s3gen.pt",
        "grapheme_mtl_merged_expanded_v1.json",
        "conds.pt",
        "Cangjie5_TC.json",
    )
    _SUPPORTED_LANGUAGES = {language: language for language in CHATTERBOX_LANGUAGE_IDS}

    def __init__(self, device: str = "cuda"):
        self.device = device
        self._runtime = None
        self._lock = RLock()
        self._last_error: str | None = None
        self._baseline_conditions = None
        # Pinned upstream exposes prepare_conditionals(path), whose result is
        # model-owned GPU state. Cache it per validated reference path so a
        # persistent worker does not re-encode a profile for every request.
        self._clone_conditions: dict[str, object] = {}
        self._last_load_timings: dict[str, float] = {}

    @property
    def provider_id(self) -> str:
        return self.PROVIDER_ID

    def provider_name(self) -> str:
        return self.PROVIDER_ID

    def is_loaded(self) -> bool:
        return self._runtime is not None

    @classmethod
    def _normalize_language(cls, language: str) -> str:
        if not isinstance(language, str):
            raise ValueError("INVALID_LANGUAGE")
        normalized = language.strip().lower()
        if normalized.replace("_", "-") == "vi-vn" or normalized == "vi":
            raise ValueError("VIETNAMESE_OWNED_BY_VIENEU")
        if normalized not in cls._SUPPORTED_LANGUAGES:
            raise ValueError("LANGUAGE_NOT_SUPPORTED")
        return normalized

    def list_languages(self) -> list[str]:
        return list(self._SUPPORTED_LANGUAGES)

    def list_voices(self, language: str) -> list[VoiceInfo]:
        try:
            normalized = self._normalize_language(language)
        except ValueError:
            return []
        return [VoiceInfo(
            id=self.DEFAULT_VOICE_ID,
            name="Chatterbox Default",
            language=normalized,
            provider=self.PROVIDER_ID,
        )]

    def capabilities(self) -> dict:
        return {
            "verified_languages": self.list_languages(),
            "language_metadata": [],
            "experimental_languages_enabled": False,
            "production_ready": False,
            "model_family": "ChatterboxMultilingual",
            "t3_model": self.T3_MODEL,
            "cuda_only": True,
            "baseline_only": True,
        }

    def health_check(self) -> dict:
        return {
            "provider": self.PROVIDER_ID,
            "loaded": self.is_loaded(),
            "device": self.device,
            "model_family": "ChatterboxMultilingual",
            "t3_model": self.T3_MODEL,
            "last_error": self._last_error,
        }

    @staticmethod
    def _is_oom(exc: BaseException) -> bool:
        return "out of memory" in str(exc).lower()

    @staticmethod
    def _offline_mode_enabled() -> bool:
        return any(
            os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
            for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
        )

    @staticmethod
    def _read_pinned_cangjie_mapping(snapshot_path: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
        """Read only the approved Cangjie artifact in the pinned snapshot."""
        snapshot = snapshot_path.resolve(strict=True)
        logical_mapping = snapshot / ChatterboxAdapter.CANGJIE_FILENAME
        if not logical_mapping.is_file():
            raise RuntimeError("Pinned Chatterbox Cangjie mapping is invalid")
        mapping = logical_mapping.resolve(strict=True)
        if logical_mapping.is_symlink():
            # HF snapshots may link to either per-repository blobs or the
            # cache-wide blob store. Both remain under the same HF cache root;
            # the pinned size/hash below binds the target to this artifact.
            repo_cache = snapshot.parent.parent
            permitted_roots = (repo_cache / "blobs", repo_cache.parent / "blobs")
            if not any(mapping.is_relative_to(root.resolve()) for root in permitted_roots if root.is_dir()):
                raise RuntimeError("Pinned Chatterbox Cangjie mapping is invalid")
        elif not mapping.is_relative_to(snapshot):
            raise RuntimeError("Pinned Chatterbox Cangjie mapping is invalid")
        if mapping.stat().st_size != ChatterboxAdapter.CANGJIE_SIZE_BYTES:
            raise RuntimeError("Pinned Chatterbox Cangjie mapping has unexpected size")
        digest = hashlib.sha256(mapping.read_bytes()).hexdigest()
        if digest != ChatterboxAdapter.CANGJIE_SHA256:
            raise RuntimeError("Pinned Chatterbox Cangjie mapping has unexpected SHA256")
        word2cj: dict[str, str] = {}
        cj2word: dict[str, list[str]] = {}
        with mapping.open("r", encoding="utf-8") as source:
            for entry in json.load(source):
                word, code = entry.split("\t")[:2]
                word2cj[word] = code
                cj2word.setdefault(code, []).append(word)
        if not word2cj:
            raise RuntimeError("Pinned Chatterbox Cangjie mapping is empty")
        return word2cj, cj2word

    @contextmanager
    def _pinned_cangjie_loader(self, snapshot_path: Path):
        """Narrow compatibility shim for upstream's snapshot-as-cache bug."""
        word2cj, cj2word = self._read_pinned_cangjie_mapping(snapshot_path)
        from chatterbox.models.tokenizers import tokenizer as tokenizer_module

        original = tokenizer_module.ChineseCangjieConverter._load_cangjie_mapping

        def load_from_pinned_snapshot(converter, _model_dir=None):
            converter.word2cj = dict(word2cj)
            converter.cj2word = {code: list(words) for code, words in cj2word.items()}

        tokenizer_module.ChineseCangjieConverter._load_cangjie_mapping = load_from_pinned_snapshot
        try:
            yield
        finally:
            tokenizer_module.ChineseCangjieConverter._load_cangjie_mapping = original

    def load(self):
        """Download the pinned snapshot and load V3 only when explicitly used."""
        with self._lock:
            if self._runtime is not None:
                return self

            # All optional runtime imports remain here so the main runtime can
            # import this adapter without the isolated Chatterbox dependency
            # set.
            import torch

            if not self.device.startswith("cuda") or not torch.cuda.is_available():
                self._last_error = "LOCAL_GPU_UNAVAILABLE"
                raise ChatterboxLocalGpuUnavailable(self._last_error)

            from huggingface_hub import snapshot_download
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS

            try:
                started = time.perf_counter()
                snapshot_path = Path(snapshot_download(
                    repo_id=self.MODEL_REPOSITORY,
                    repo_type="model",
                    revision=self.MODEL_REVISION,
                    allow_patterns=list(self._MODEL_FILES),
                    local_files_only=self._offline_mode_enabled(),
                ))
                snapshot_ms = (time.perf_counter() - started) * 1000
                missing = [name for name in self._MODEL_FILES if not (snapshot_path / name).is_file()]
                if missing:
                    raise RuntimeError(f"Pinned Chatterbox snapshot missing: {', '.join(missing)}")

                # Pinned upstream signature: from_local(ckpt_dir, device,
                # t3_model=None).  Explicitly selecting V3 prevents the
                # upstream default (V2) from ever being used.
                started = time.perf_counter()
                with self._pinned_cangjie_loader(snapshot_path):
                    self._runtime = ChatterboxMultilingualTTS.from_local(
                        snapshot_path,
                        device=self.device,
                        t3_model=self.T3_MODEL,
                    )
                model_load_ms = (time.perf_counter() - started) * 1000
                self._baseline_conditions = self._runtime.conds
                self._last_load_timings = {"snapshot_resolution_ms": snapshot_ms, "model_construction_cuda_init_ms": model_load_ms}
                self._last_error = None
                return self
            except Exception as exc:
                self._runtime = None
                if self._is_oom(exc):
                    self._last_error = "GPU_RESOURCE_INSUFFICIENT"
                    raise ChatterboxGpuResourceInsufficient(self._last_error) from exc
                self._last_error = str(exc)
                raise

    def unload(self) -> None:
        with self._lock:
            self._runtime = None
            self._baseline_conditions = None
            self._clone_conditions.clear()

    def create_voice_profile(self, reference_audio: str | Path, transcript: str | None = None) -> dict:
        """Return durable reference metadata; upstream V3 does not need a transcript.

        Conditioning is intentionally prepared lazily in the persistent CUDA
        worker. This avoids loading the model merely to create a profile.
        """
        path = Path(reference_audio).resolve()
        if not path.is_file():
            raise ValueError("INVALID_REFERENCE_AUDIO")
        return {"reference_audio": str(path)}

    def _clone_reference_path(self, profile: object) -> Path:
        if not isinstance(profile, dict) or not isinstance(profile.get("reference_audio"), str):
            raise ValueError("INVALID_VOICE_PROFILE")
        path = Path(profile["reference_audio"]).resolve()
        if not path.is_file():
            raise ValueError("INVALID_REFERENCE_AUDIO")
        return path

    def _write_audio(self, audio, target: Path) -> tuple[int, float]:
        import torchaudio
        target.parent.mkdir(parents=True, exist_ok=True)
        torchaudio.save(str(target), audio.detach().cpu(), self._runtime.sr,
                        format="wav", encoding="PCM_S", bits_per_sample=16)
        if not target.is_file() or target.stat().st_size <= 44:
            raise RuntimeError("INVALID_AUDIO_OUTPUT")
        with wave.open(str(target), "rb") as wav_file:
            channels, sample_rate = wav_file.getnchannels(), wav_file.getframerate()
            duration = wav_file.getnframes() / sample_rate if sample_rate else 0.0
        if channels != 1 or sample_rate < 1 or duration <= 0:
            raise RuntimeError("INVALID_AUDIO_OUTPUT")
        return sample_rate, duration

    def _result(self, target: Path, sample_rate: int, duration: float, elapsed: float,
                language: str, voice: str, *, cloned: bool) -> AudioSynthResult:
        return AudioSynthResult(status="PASS", wav_path=str(target), sample_rate=sample_rate,
            duration=duration, gen_time=elapsed, rtf=elapsed / duration, provider=self.PROVIDER_ID,
            model=f"ChatterboxMultilingual-{self.T3_MODEL}", language=language, voice=voice,
            device=self.device, metadata={"t3_checkpoint": self.T3_CHECKPOINT, "cloned": cloned, **self._last_load_timings})

    def synthesize(
        self,
        text: str,
        language: str,
        voice: str = DEFAULT_VOICE_ID,
        output_path: str | Path | None = None,
        speed: float = 1.0,
        **options,
    ) -> AudioSynthResult:
        try:
            normalized_language = self._normalize_language(language)
            if (not isinstance(text, str) or not text.strip() or output_path is None
                    or voice != self.DEFAULT_VOICE_ID or speed != 1.0 or options):
                raise ValueError("INVALID_REQUEST")

            started = time.perf_counter()
            with self._lock:
                load_started = time.perf_counter()
                self.load()
                load_ms = (time.perf_counter() - load_started) * 1000
                # A preceding clone must never leak its reference conditioning
                # into a later baseline request.
                self._runtime.conds = self._baseline_conditions
                # No audio_prompt_path is supplied: this uses the official
                # pinned snapshot's bundled `conds.pt` baseline conditioning.
                generate_started = time.perf_counter()
                audio = self._runtime.generate(text.strip(), language_id=normalized_language)
                generate_ms = (time.perf_counter() - generate_started) * 1000

                target = Path(output_path)
                # Chatterbox returns a floating-point tensor.  Torchaudio's
                # default encodes that as IEEE-float WAV (format tag 3),
                # which Python's standard ``wave`` validator intentionally
                # rejects.  Write ordinary signed PCM explicitly while
                # preserving the model's native sample rate and mono shape.
                save_started = time.perf_counter()
                sample_rate, duration = self._write_audio(audio, target)
                save_ms = (time.perf_counter() - save_started) * 1000

            elapsed = time.perf_counter() - started
            result = self._result(target, sample_rate, duration, elapsed, normalized_language, voice, cloned=False)
            result.metadata.update({"adapter_load_ms": load_ms, "generate_ms": generate_ms, "wav_save_ms": save_ms, "total_ms": elapsed * 1000})
            return result
        except ChatterboxLocalGpuUnavailable:
            return self._failure("LOCAL_GPU_UNAVAILABLE", language, voice)
        except ChatterboxGpuResourceInsufficient:
            return self._failure("GPU_RESOURCE_INSUFFICIENT", language, voice)
        except ValueError as exc:
            return self._failure(str(exc), language, voice)
        except Exception as exc:
            # CUDA errors can be raised by generate(), serialization, or a
            # native dependency below those calls. Preserve non-OOM failures
            # verbatim, but never leak CUDA OOM as an implementation error.
            if self._is_oom(exc):
                return self._failure("GPU_RESOURCE_INSUFFICIENT", language, voice)
            return self._failure(str(exc), language, voice)

    def synthesize_cloned(self, text: str, language: str, profile: object,
                          output_path: str | Path, **options) -> AudioSynthResult:
        """Generate with cached V3 reference conditioning for any supported non-VI target."""
        voice = "chatterbox_clone"
        try:
            normalized_language = self._normalize_language(language)
            if not isinstance(text, str) or not text.strip() or output_path is None or options:
                raise ValueError("INVALID_REQUEST")
            reference = self._clone_reference_path(profile)
            started = time.perf_counter()
            with self._lock:
                self.load()
                key = str(reference)
                conditionals = self._clone_conditions.get(key)
                if conditionals is None:
                    self._runtime.prepare_conditionals(str(reference))
                    conditionals = self._runtime.conds
                    self._clone_conditions[key] = conditionals
                self._runtime.conds = conditionals
                audio = self._runtime.generate(text.strip(), language_id=normalized_language)
                target = Path(output_path)
                sample_rate, duration = self._write_audio(audio, target)
            elapsed = time.perf_counter() - started
            return self._result(target, sample_rate, duration, elapsed, normalized_language, voice, cloned=True)
        except ChatterboxLocalGpuUnavailable:
            return self._failure("LOCAL_GPU_UNAVAILABLE", language, voice)
        except ChatterboxGpuResourceInsufficient:
            return self._failure("GPU_RESOURCE_INSUFFICIENT", language, voice)
        except ValueError as exc:
            return self._failure(str(exc), language, voice)
        except Exception as exc:
            return self._failure("GPU_RESOURCE_INSUFFICIENT" if self._is_oom(exc) else str(exc), language, voice)

    def _failure(self, error: str, language: str, voice: str) -> AudioSynthResult:
        self._last_error = error
        return AudioSynthResult(
            status="FAIL",
            error=error,
            provider=self.PROVIDER_ID,
            language=language,
            voice=voice,
            device=self.device,
        )
