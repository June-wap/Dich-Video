"""CP7 integration tests without model/runtime dependencies."""
from __future__ import annotations

import time
import wave
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.config import Settings
from backend.errors import ApplicationError, ErrorCode
from backend.schemas.tts import TTSRequest
from backend.services.provider_base import AudioSynthResult, VoiceInfo
from backend.services.provider_service import ProviderService
from backend.services.tts_service import TTSService


class Provider:
    def __init__(self, provider_id):
        self.provider_id = provider_id
        self.device = "test"
        self.loaded = False
        self.load_calls = 0
        self.calls = []

    def provider_name(self): return self.provider_id
    def capabilities(self):
        return {
            "verified_languages": ["vi"] if self.provider_id == "vieneu" else ["en", "es"],
            "language_metadata": [],
            "experimental_languages_enabled": False,
            "production_ready": True,
        }
    def is_loaded(self): return self.loaded
    def load(self): self.loaded = True; self.load_calls += 1; return self
    def unload(self): self.loaded = False
    def list_voices(self, language):
        return [VoiceInfo(id=f"{self.provider_id}_default", name="Default", language=language,
                          provider=self.provider_id, sample_rate=24000)]
    def synthesize(self, text, language, voice, output_path, speed=1.0, **kwargs):
        self.calls.append(("baseline", text, language))
        self._write(output_path)
        return AudioSynthResult(
            status="PASS", provider=self.provider_id, language=language, voice=voice,
            wav_path=str(output_path), sample_rate=24000, duration=0.01, gen_time=0.01,
        )
    def synthesize_cloned(self, text, language, profile, output_path, **kwargs):
        self.calls.append(("clone", text, language))
        self._write(output_path)
        return AudioSynthResult(
            status="PASS", provider=self.provider_id, language=language, voice="clone",
            wav_path=str(output_path), sample_rate=24000, duration=0.01, gen_time=0.01,
        )
    @staticmethod
    def _write(path):
        with wave.open(str(path), "wb") as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(24000); out.writeframes(b"\0\0" * 240)


class Profiles:
    def get_profile_record(self, profile_id):
        # Baseline provider voices are not persisted clone profiles. Match the
        # real VoiceProfileService contract by reporting them as absent.
        if profile_id in {"vieneu_default", "chatterbox_default"}:
            raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_FOUND)
        return SimpleNamespace(provider_id="chatterbox", provider_profile={})
    def reserve_profile(self, profile_id): return self.get_profile_record(profile_id)
    def restore_profile(self, record): pass
    def release_profile(self, record): pass


def _service(tmp_path, translator):
    settings = Settings(output_dir=tmp_path / "out", database_path=tmp_path / "db.sqlite3")
    providers = ProviderService()
    vi, chatterbox = Provider("vieneu"), Provider("chatterbox")
    providers.register(vi, device="cpu", available=True)
    providers.register(chatterbox, device="cuda", available=True)
    return TTSService(settings, providers, translator, Profiles()), vi, chatterbox


def _wait(service, job_id):
    for _ in range(500):
        status = service.status(job_id)
        if status.status in {"COMPLETED", "FAILED"}: return status
        time.sleep(.01)
    pytest.fail("job did not finish")


def test_same_language_bypasses_translation_and_routes_target(tmp_path):
    translator = SimpleNamespace(translate=Mock())
    service, vi, chatterbox = _service(tmp_path, translator)
    try:
        result = _wait(service, service.submit(TTSRequest(text="xin chao", source_language="vi", language="vi", voice_id="vieneu_default")).job_id)
        assert result.status == "COMPLETED"
        translator.translate.assert_not_called()
        assert vi.calls == [("baseline", "xin chao", "vi")]
        assert not chatterbox.calls
    finally: service.close()


def test_cross_language_translates_before_chatterbox_and_never_uses_source(tmp_path):
    translator = SimpleNamespace(translate=Mock(return_value="hello"))
    service, vi, chatterbox = _service(tmp_path, translator)
    try:
        result = _wait(service, service.submit(TTSRequest(text="xin chao", source_language="vi", language="en", voice_id="chatterbox_default")).job_id)
        assert result.status == "COMPLETED"
        translator.translate.assert_called_once_with("xin chao", "vi", "en")
        assert chatterbox.calls == [("baseline", "hello", "en")]
        assert not vi.calls
    finally: service.close()


def test_translation_failure_never_loads_or_synthesizes_provider(tmp_path):
    translator = SimpleNamespace(translate=Mock(side_effect=ApplicationError(ErrorCode.TRANSLATION_FAILED)))
    service, vi, chatterbox = _service(tmp_path, translator)
    try:
        result = _wait(service, service.submit(TTSRequest(text="xin chao", source_language="vi", language="en", voice_id="chatterbox_default")).job_id)
        assert result.status == "FAILED" and result.error.code == "TRANSLATION_FAILED"
        assert chatterbox.load_calls == 0 and not chatterbox.calls and not vi.calls
        assert "xin chao" not in [call[1] for call in chatterbox.calls + vi.calls]
        assert not list((tmp_path / "out").glob("*"))
    finally: service.close()


def test_cross_language_translated_text_reaches_clone_provider(tmp_path):
    translator = SimpleNamespace(translate=Mock(return_value="hola"))
    service, _, chatterbox = _service(tmp_path, translator)
    try:
        result = _wait(service, service.submit(TTSRequest(
            text="xin chao", source_language="vi", language="es", voice_id="clone-profile"
        )).job_id)
        assert result.status == "COMPLETED"
        assert chatterbox.calls == [("clone", "hola", "es")]
    finally: service.close()


def test_source_language_changes_idempotency_semantics(tmp_path):
    translator = SimpleNamespace(translate=Mock(return_value="hello"))
    service, _, _ = _service(tmp_path, translator)
    try:
        first = service.submit(TTSRequest(text="xin chao", source_language="vi", language="en", voice_id="chatterbox_default", idempotency_key="same"))
        _wait(service, first.job_id)
        with pytest.raises(ApplicationError) as caught:
            service.submit(TTSRequest(text="xin chao", source_language="fr", language="en", voice_id="chatterbox_default", idempotency_key="same"))
        assert caught.value.code == ErrorCode.IDEMPOTENCY_KEY_CONFLICT
    finally: service.close()
