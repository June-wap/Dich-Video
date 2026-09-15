import io
from pathlib import Path
import tempfile
import uuid
import wave

from fastapi.testclient import TestClient
import numpy as np
import pytest
import soundfile as sf

from backend.config import OMNIVOICE_PROVIDER_ID, Settings
from backend.main import create_app
from backend.services.provider_service import ProviderService
from backend.services.system_service import SystemService
from backend.services.tts_service import TTSService
from backend.services.voice_profile_service import VoiceProfileService
from backend.tests.provider_fakes import FakeCloneProvider


def make_wav_bytes(duration: float = 5.0, sample_rate: int = 24000) -> bytes:
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    sig = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, sig, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


@pytest.fixture
def app_client():
    with tempfile.TemporaryDirectory() as tmp_dir:
        settings = Settings(output_dir=Path(tmp_dir))
        provider = FakeCloneProvider()
        providers = ProviderService()
        providers.register(provider, device="cuda:0", available=True)
        providers.select_primary(OMNIVOICE_PROVIDER_ID)

        app = create_app(
            settings=settings,
            service_factory=lambda provs: SystemService(provs),
            provider_service_factory=lambda s: providers,
            tts_service_factory=lambda s, provs: TTSService(s, provs),
            voice_profile_service_factory=lambda s, provs: VoiceProfileService(s, provs),
        )
        with TestClient(app, base_url="http://127.0.0.1:8000") as client:
            yield client, provider, Path(tmp_dir)


def test_create_profile_api_success(app_client):
    client, provider, _ = app_client
    wav_bytes = make_wav_bytes(5.0)

    resp = client.post(
        "/api/voices/profiles",
        files={"file": ("reference.wav", wav_bytes, "audio/wav")},
        data={"reference_transcript": "Văn bản phát âm chuẩn.", "name": "Giọng Mẫu"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["data"]["name"] == "Giọng Mẫu"
    assert data["data"]["provider"] == OMNIVOICE_PROVIDER_ID
    assert data["data"]["status"] == "ready"
    assert round(data["data"]["reference"]["duration_seconds"], 1) == 5.0
    assert provider.create_profile_calls == 1


def test_create_profile_api_validation(app_client):
    client, _, _ = app_client
    wav_bytes = make_wav_bytes(5.0)

    # Missing transcript
    resp = client.post(
        "/api/voices/profiles",
        files={"file": ("reference.wav", wav_bytes, "audio/wav")},
        data={"reference_transcript": ""},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REFERENCE_TRANSCRIPT"

    # Corrupt audio
    resp = client.post(
        "/api/voices/profiles",
        files={"file": ("reference.wav", b"not-audio-bytes", "audio/wav")},
        data={"reference_transcript": "Văn bản phát âm."},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_REFERENCE_AUDIO"


def test_get_and_list_profiles_api(app_client):
    client, _, _ = app_client
    wav_bytes = make_wav_bytes(5.0)

    create_resp = client.post(
        "/api/voices/profiles",
        files={"file": ("reference.wav", wav_bytes, "audio/wav")},
        data={"reference_transcript": "Văn bản phát âm."},
        headers={"Origin": "http://localhost:5173"},
    )
    pid = create_resp.json()["data"]["profile_id"]

    # Get single profile
    get_resp = client.get(f"/api/voices/profiles/{pid}", headers={"Origin": "http://localhost:5173"})
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["profile_id"] == pid

    # List profiles
    list_resp = client.get("/api/voices/profiles", headers={"Origin": "http://localhost:5173"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()["data"]) == 1
    assert list_resp.json()["data"][0]["profile_id"] == pid

    # Nonexistent profile
    not_found = client.get(f"/api/voices/profiles/{uuid.uuid4()}", headers={"Origin": "http://localhost:5173"})
    assert not_found.status_code == 404
    assert not_found.json()["error"]["code"] == "VOICE_PROFILE_NOT_FOUND"


def test_delete_profile_api(app_client):
    client, _, _ = app_client
    wav_bytes = make_wav_bytes(5.0)

    create_resp = client.post(
        "/api/voices/profiles",
        files={"file": ("reference.wav", wav_bytes, "audio/wav")},
        data={"reference_transcript": "Văn bản phát âm."},
        headers={"Origin": "http://localhost:5173"},
    )
    pid = create_resp.json()["data"]["profile_id"]

    # Delete
    del_resp = client.delete(f"/api/voices/profiles/{pid}", headers={"Origin": "http://localhost:5173"})
    assert del_resp.status_code == 200
    assert del_resp.json()["data"]["deleted"] is True

    # Subsequent GET returns 404
    get_resp = client.get(f"/api/voices/profiles/{pid}", headers={"Origin": "http://localhost:5173"})
    assert get_resp.status_code == 404
    assert get_resp.json()["error"]["code"] == "VOICE_PROFILE_NOT_FOUND"


def test_clone_synthesis_and_profile_reuse_api(app_client):
    client, provider, _ = app_client
    wav_bytes = make_wav_bytes(5.0)

    # 1. Create Profile
    create_resp = client.post(
        "/api/voices/profiles",
        files={"file": ("reference.wav", wav_bytes, "audio/wav")},
        data={"reference_transcript": "Văn bản phát âm."},
        headers={"Origin": "http://localhost:5173"},
    )
    pid = create_resp.json()["data"]["profile_id"]
    assert provider.create_profile_calls == 1

    # 2. Sequential Clone requests reusing SAME profile
    for i in range(1, 4):
        test_resp = client.post(
            f"/api/voices/profiles/{pid}/test",
            json={"text": f"Đây là câu kiểm tra số {i}.", "language": "vi", "speed": 1.0, "format": "wav"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert test_resp.status_code == 200
        data = test_resp.json()["data"]
        assert data["profile_id"] == pid
        assert data["format"] == "wav"
        assert data["sample_rate"] == 24000
        assert data["channels"] == 1

        # Check audio retrieval
        audio_url = data["audio_url"]
        audio_resp = client.get(audio_url, headers={"Origin": "http://localhost:5173"})
        assert audio_resp.status_code == 200
        assert audio_resp.headers["content-type"] == "audio/wav"
        assert len(audio_resp.content) > 0

    # Invariants: profile created once, cloned synthesis called 3 times
    assert provider.create_profile_calls == 1
    assert provider.synthesize_cloned_calls == 3


def test_normal_tts_regression(app_client):
    client, provider, _ = app_client

    # Normal TTS endpoint must continue functioning independently
    tts_resp = client.post(
        "/api/tts",
        json={"text": "Đây là bài kiểm tra TTS thông thường.", "language": "vi", "voice_id": "omnivoice_auto"},
        headers={"Origin": "http://localhost:5173"},
    )
    assert tts_resp.status_code == 200
    assert tts_resp.json()["ok"] is True
    assert provider.synthesize_calls == 1
    assert provider.create_profile_calls == 0


def test_privacy_logs_redaction(app_client, caplog):
    client, _, _ = app_client
    wav_bytes = make_wav_bytes(5.0)

    secret_transcript = "SECRET_REFERENCE_TRANSCRIPT_987654"
    secret_clone_text = "SECRET_CUSTOMER_TEXT_123456"

    with caplog.at_level("INFO"):
        # Create profile
        create_resp = client.post(
            "/api/voices/profiles",
            files={"file": ("reference.wav", wav_bytes, "audio/wav")},
            data={"reference_transcript": secret_transcript},
            headers={"Origin": "http://localhost:5173"},
        )
        pid = create_resp.json()["data"]["profile_id"]

        # Synthesize clone
        client.post(
            f"/api/voices/profiles/{pid}/test",
            json={"text": secret_clone_text, "language": "vi"},
            headers={"Origin": "http://localhost:5173"},
        )

    # Ensure secret text never appears in any backend log message
    for record in caplog.records:
        assert secret_transcript not in record.message
        assert secret_clone_text not in record.message
