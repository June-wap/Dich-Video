"""Base TTSProvider interface."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SynthResult:
    """Result of a synthesis call."""
    wav_path: str | None = None
    mp3_path: str | None = None
    export_error: str | None = None
    load_time: float = 0.0
    preparation_time: float = 0.0
    text_length: int = 0
    sample_rate: int = 0
    duration: float = 0.0
    gen_time: float = 0.0
    rtf: float = 0.0
    provider: str = ""
    model: str = ""
    language: str = ""
    voice: str = ""
    device: str = "cpu"
    error: str | None = None
    status: str = "PASS"  # PASS | FAIL
    metadata: dict = field(default_factory=dict)

    @property
    def provider_id(self) -> str:
        return self.provider

    @property
    def generation_time(self) -> float:
        return self.gen_time


class AudioSynthResult(SynthResult):
    """In-memory audio result; PCM is deliberately excluded from log serialization."""

    def __init__(self, audio=None, **kwargs):
        super().__init__(**kwargs)
        self.audio = audio


@dataclass
class VoiceInfo:
    """Describes one available voice."""
    id: str
    name: str
    # Optional for providers whose caller already scopes discovery by language.
    # Concrete production providers should continue to populate it.
    language: str = ""
    gender: str = "unknown"
    provider: str = ""
    model: str = ""
    sample_rate: int = 22050


class TTSProvider(abc.ABC):
    """Minimal common interface for TTS providers."""

    @abc.abstractmethod
    def provider_name(self) -> str:
        ...

    @abc.abstractmethod
    def list_languages(self) -> list[str]:
        ...

    @abc.abstractmethod
    def list_voices(self, language: str) -> list[VoiceInfo]:
        ...

    @abc.abstractmethod
    def synthesize(
        self,
        text: str,
        language: str,
        voice: str,
        output_path: str | Path,
        speed: float = 1.0,
        **options,
    ) -> SynthResult:
        ...

    @abc.abstractmethod
    def health_check(self) -> dict:
        ...


class ManagedTTSProvider(TTSProvider):
    """Optional lifecycle contract; existing providers need no changes."""

    @abc.abstractmethod
    def load(self):
        ...

    @abc.abstractmethod
    def is_loaded(self) -> bool:
        ...

    @abc.abstractmethod
    def capabilities(self) -> dict:
        ...

    @abc.abstractmethod
    def unload(self):
        ...


class CloningProvider(TTSProvider):
    """Extension for voice-cloning providers."""

    @abc.abstractmethod
    def prepare_voice_profile(
        self,
        reference_audio: str | Path,
        voice_name: str = "clone",
    ) -> dict:
        """Prepare a voice profile from reference audio.
        Returns profile metadata dict."""
        ...

    @abc.abstractmethod
    def synthesize_with_profile(
        self,
        text: str,
        reference_audio: str | Path,
        language: str,
        output_path: str | Path,
        **options,
    ) -> SynthResult:
        ...
