import uuid
import wave
from pathlib import Path
import numpy as np

from providers.base import AudioSynthResult
from providers.omnivoice import OmniVoiceProvider, VoiceProfile
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
        if self.fail_synthesize:
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
        if self.fail_synthesize_cloned:
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


def registry(provider=None, *, available=True):
    provider = provider or FakeProvider()
    service = ProviderService()
    service.register(provider, device=provider.device, available=available)
    service.select_primary(OMNIVOICE_PROVIDER_ID)
    return service

