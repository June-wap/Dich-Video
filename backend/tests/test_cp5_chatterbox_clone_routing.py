"""CP5 routing tests: profile ownership follows target/output language."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.errors import ApplicationError, ErrorCode
from backend.schemas.tts import TTSRequest
from backend.services.provider_base import VoiceInfo
from backend.services.tts_service import TTSService


class _Provider:
    def __init__(self, provider_id, languages, default):
        self._id, self._languages, self._default = provider_id, languages, default
        self.lookups = 0
    def provider_name(self): return self._id
    def list_voices(self, language):
        return [VoiceInfo(id=self._default, name="default", language=language, provider=self._id)]


class _Registry:
    def __init__(self):
        self.vieneu = _Provider("vieneu", ("vi",), "vieneu_default")
        self.chatterbox = _Provider("chatterbox", ("en", "es", "ja"), "chatterbox_default")
    def get_provider(self, provider_id):
        getattr(self, provider_id).lookups += 1
        return getattr(self, provider_id)


class _Profiles:
    def __init__(self):
        self.records = {
            "11111111-1111-1111-1111-111111111111": SimpleNamespace(provider_id="vieneu"),
            "22222222-2222-2222-2222-222222222222": SimpleNamespace(provider_id="chatterbox"),
        }
    def get_profile_record(self, profile_id):
        if profile_id not in self.records:
            raise ApplicationError(ErrorCode.VOICE_PROFILE_NOT_FOUND)
        return self.records[profile_id]


def _service():
    service = object.__new__(TTSService)
    service._provider_service = _Registry()
    service._voice_profiles = _Profiles()
    service._db = SimpleNamespace(put=lambda *args: None)
    return service


def _request(language, voice_id=None):
    return TTSRequest(text="Clone routing test", language=language, voice_id=voice_id, speed=1.0, format="wav")


def _validated_voice_id(service, request):
    _text, _source_language, _target_language, voice_id, *_rest = service.validate_request(request)
    return voice_id


def test_existing_vietnamese_baseline_and_clone_keep_vieneu_ownership():
    service = _service()
    assert _validated_voice_id(service, _request("vi", "vieneu_default")) == "vieneu_default"
    assert service.validate_request(_request("vi", "11111111-1111-1111-1111-111111111111"))[-1] == "11111111-1111-1111-1111-111111111111"


def test_service_requires_canonical_vieneu_default_while_frontend_normalizes_null():
    service = _service()
    with pytest.raises(ApplicationError) as caught:
        service.validate_request(_request("vi"))
    assert caught.value.code == ErrorCode.VOICE_NOT_FOUND


def test_non_vietnamese_baseline_and_chatterbox_clone_route_to_chatterbox():
    service = _service()
    assert _validated_voice_id(service, _request("en")) == "chatterbox_default"
    assert service.validate_request(_request("es", "22222222-2222-2222-2222-222222222222"))[-1] == "22222222-2222-2222-2222-222222222222"


@pytest.mark.parametrize(("language", "profile"), [
    ("en", "11111111-1111-1111-1111-111111111111"),
    ("vi", "22222222-2222-2222-2222-222222222222"),
])
def test_cross_provider_profile_is_rejected_before_provider_execution(language, profile):
    service = _service()
    with pytest.raises(ApplicationError) as caught:
        service.validate_request(_request(language, profile))
    assert caught.value.code == ErrorCode.VOICE_PROFILE_PROVIDER_MISMATCH
    assert service._provider_service.vieneu.lookups == service._provider_service.chatterbox.lookups == 0


def test_unsupported_output_language_is_rejected_before_provider_execution():
    service = _service()
    with pytest.raises(ApplicationError) as caught:
        service.validate_request(_request("xx", "22222222-2222-2222-2222-222222222222"))
    assert caught.value.code == ErrorCode.LANGUAGE_NOT_SUPPORTED
    assert service._provider_service.vieneu.lookups == service._provider_service.chatterbox.lookups == 0
