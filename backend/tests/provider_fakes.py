import uuid
import wave
from pathlib import Path
import numpy as np

from providers.base import AudioSynthResult, VoiceInfo
from providers.omnivoice import OmniVoiceProvider, VoiceProfile
from providers.piper import PiperProvider as _RealPiperProvider
from backend.config import OMNIVOICE_PROVIDER_ID
from backend.services.provider_service import ProviderService


class FakeProvider(OmniVoiceProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.load_calls = 0
        self.unload_calls = 0
        self.fail_load = False
        self.fail_unload = False

    def load(self):
        self.load_calls += 1
        if self.fail_load:
            raise RuntimeError("private C:/secret/model/weights load error")
        self._model = object()
        self._load_count += 1
        return self

    def unload(self):
        self.unload_calls += 1
        if self.fail_unload:
            raise RuntimeError("private C:/secret/model unload error")
        self._model = None


class FakeCloneProvider(FakeProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.create_profile_calls = 0
        self.synthesize_cloned_calls = 0
        self.synthesize_calls = 0
        self.fail_create_profile = False
        self.fail_synthesize_cloned = False
        self.fail_synthesize = False
        # Fail exactly this many calls, then succeed - for exercising
        # TTSService/LongFormTTSService's Retry Count wiring (Task 4).
        # fail_synthesize/fail_synthesize_cloned above stay "always fail".
        self.fail_synthesize_count = 0
        self.fail_synthesize_cloned_count = 0
        self.created_profiles = []

    def create_voice_profile(self, reference_audio, reference_transcript):
        self.create_profile_calls += 1
        if self.fail_create_profile:
            raise RuntimeError("Model clone prompt preparation failed")
        profile = VoiceProfile(profile_id=uuid.uuid4().hex, provider_id=self.PROVIDER_ID, reference_duration=26.7)
        self._profiles[profile.profile_id] = (profile, "fake_clone_prompt")
        self.created_profiles.append(profile)
        return profile

    def synthesize(self, text, language, voice="omnivoice_auto", output_path=None, speed=1.0, **options):
        self.synthesize_calls += 1
        self.last_synthesize_options = options
        if self.fail_synthesize or self.fail_synthesize_count > 0:
            if self.fail_synthesize_count > 0:
                self.fail_synthesize_count -= 1
            return AudioSynthResult(
                status="FAIL",
                error="Internal model synthesis error",
                provider=self.PROVIDER_ID,
                language=language,
                voice=voice,
            )
        if output_path is not None:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            sample_rate = 24000
            n_frames = 12000
            pcm = np.zeros(n_frames, dtype=np.int16)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm.tobytes())

        return AudioSynthResult(
            status="PASS",
            wav_path=str(output_path) if output_path else None,
            sample_rate=24000,
            duration=0.5,
            gen_time=0.05,
            provider=self.PROVIDER_ID,
            language=language,
        )

    def synthesize_cloned(self, text, language, profile, output_path=None, **options):
        self.synthesize_cloned_calls += 1
        self.last_synthesize_cloned_options = options
        if self.fail_synthesize_cloned or self.fail_synthesize_cloned_count > 0:
            if self.fail_synthesize_cloned_count > 0:
                self.fail_synthesize_cloned_count -= 1
            return AudioSynthResult(
                status="FAIL",
                error="Internal cloned synthesis error",
                provider=self.PROVIDER_ID,
                language=language,
            )
        if output_path is not None:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            sample_rate = 24000
            n_frames = 12000
            pcm = np.zeros(n_frames, dtype=np.int16)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm.tobytes())

        return AudioSynthResult(
            status="PASS",
            wav_path=str(output_path) if output_path else None,
            sample_rate=24000,
            duration=0.5,
            gen_time=0.05,
            provider=self.PROVIDER_ID,
            language=language,
        )


class FakePiperProvider:
    """Duck-typed stand-in for the real PiperProvider (prototype/providers/piper.py)
    - deliberately does NOT need real onnx voice models, but faithfully
    reproduces the one behavior this file's regression tests care about:
    PiperProvider's _synthesize() rejects ANY unrecognized keyword option or
    non-default speed (`if options or speed != 1.0: raise ... INVALID_OPTIONS`).
    Used to catch TTSService accidentally passing OmniVoice-only kwargs
    (num_step, trim_silence) down the Piper route, which would crash every
    real job in Piper's six dedicated languages - see
    test_tts_settings_wiring.py's Piper-routing tests.
    """
    PROVIDER_ID = _RealPiperProvider.PROVIDER_ID
    LANGUAGES = _RealPiperProvider.LANGUAGES
    AUTO_VOICE_ID = _RealPiperProvider.AUTO_VOICE_ID

    def __init__(self):
        self.device = "cpu"
        self._loaded = False
        self.synthesize_calls = 0
        self.last_synthesize_options = None

    def provider_name(self):
        return self.PROVIDER_ID

    def list_voices(self, language):
        if language not in self.LANGUAGES:
            return []
        return [VoiceInfo(id=self.AUTO_VOICE_ID, name="Piper Auto", language=language,
                          provider=self.PROVIDER_ID, model="", sample_rate=24000)]

    def capabilities(self):
        return {
            "verified_languages": list(self.LANGUAGES),
            "language_metadata": [],
            "experimental_languages_enabled": False,
            "production_ready": False,
        }

    def is_loaded(self):
        return self._loaded

    def load(self):
        self._loaded = True
        return self

    def unload(self):
        self._loaded = False

    def synthesize(self, text, language, voice="piper_auto", output_path=None, speed=1.0, **options):
        self.synthesize_calls += 1
        self.last_synthesize_options = options
        if options or speed != 1.0:
            raise RuntimeError(
                "INVALID_OPTIONS: Piper provider supports auto-voice TTS at default speed only"
            )
        if output_path is not None:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            sample_rate = 24000
            n_frames = 12000
            pcm = np.zeros(n_frames, dtype=np.int16)
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm.tobytes())
        return AudioSynthResult(
            status="PASS",
            wav_path=str(output_path) if output_path else None,
            sample_rate=24000,
            duration=0.5,
            gen_time=0.05,
            provider=self.PROVIDER_ID,
            language=language,
        )


def registry(provider=None, *, available=True, with_piper=False, piper_provider=None):
    provider = provider or FakeProvider()
    service = ProviderService()
    service.register(provider, device=provider.device, available=available)
    service.select_primary(OMNIVOICE_PROVIDER_ID)
    if with_piper or piper_provider is not None:
        # A caller that wants to assert on the Piper fake afterwards (e.g.
        # last_synthesize_options/synthesize_calls) must pass its own
        # instance here - otherwise this would silently construct and
        # register a second, different FakePiperProvider that the caller
        # never sees calls on, and every such assertion would wrongly look
        # at an object that was never actually invoked.
        service.register(piper_provider or FakePiperProvider(), device="cpu", available=True)
    return service

