import uuid
import wave
from pathlib import Path
import numpy as np

from backend.services.provider_base import AudioSynthResult, VoiceInfo
from backend.services.provider_service import ProviderService

# Short-TTS production routing is intentionally fixed: Vietnamese requests
# always resolve to the registered VieNeu provider.  This fake is interface-
# only; it never imports or loads the real model.
TEST_PROVIDER_ID = "vieneu"


class VoiceProfile:
    def __init__(self, profile_id, provider_id, reference_duration):
        self.profile_id = profile_id
        self.provider_id = provider_id
        self.reference_duration = reference_duration


class FakeProvider:
    PROVIDER_ID = TEST_PROVIDER_ID
    def __init__(self, **kwargs):
        self.device = kwargs.get("device", "cpu")
        self._model = None
        self._load_count = 0
        self._profiles = {}
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

    def is_loaded(self):
        return self._model is not None

    def provider_name(self):
        return self.PROVIDER_ID

    def capabilities(self):
        return {"verified_languages": ["vi"], "language_metadata": [],
                "experimental_languages_enabled": False, "production_ready": False}

    def list_languages(self):
        return ["vi"]

    def list_voices(self, language):
        return [VoiceInfo(id="test_auto", name="Test Auto", language=language,
                          provider=self.PROVIDER_ID, sample_rate=24000)] if language == "vi" else []


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

    def synthesize(self, text, language, voice="test_auto", output_path=None, speed=1.0, **options):
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


class FakeAdditionalProvider:
    """A second generic provider used only to exercise multi-provider behavior."""
    PROVIDER_ID = "test-provider-secondary"
    LANGUAGES = ("vi",)
    AUTO_VOICE_ID = "test-secondary-auto"

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
        return [VoiceInfo(id=self.AUTO_VOICE_ID, name="Secondary Test Auto", language=language,
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

    def synthesize(self, text, language, voice="test-secondary-auto", output_path=None, speed=1.0, **options):
        self.synthesize_calls += 1
        self.last_synthesize_options = options
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


def registry(provider=None, *, available=True, with_additional=False, additional_provider=None):
    provider = provider or FakeProvider()
    service = ProviderService()
    service.register(provider, device=provider.device, available=available)
    service.select_primary(TEST_PROVIDER_ID)
    if with_additional or additional_provider is not None:
        service.register(
            additional_provider or FakeAdditionalProvider(), device="cpu", available=True)
    return service
