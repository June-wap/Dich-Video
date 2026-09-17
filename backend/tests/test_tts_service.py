from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path
import re
import tempfile
import uuid
import wave
from unittest.mock import Mock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.config import OMNIVOICE_PROVIDER_ID, Settings
from backend.errors import ErrorCode
from backend.main import create_app
from backend.services.provider_service import ProviderService
from backend.services.system_service import RuntimeInfo, SystemService
from backend.services.translation_service import TranslationService
from backend.services.tts_service import TTSService
from backend.services.voice_profile_service import VoiceProfileService
from backend.tests.provider_fakes import FakeProvider
from providers.base import AudioSynthResult


class FakeTTSProvider(FakeProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fail_synthesize = False
        self.synthesize_calls = 0

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
            # Write 0.5s of 24kHz 16-bit mono silence/sine
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
            voice=voice,
        )


@pytest.fixture
def tts_app_env(tmp_path):
    output_dir = tmp_path / "outputs" / "api"
    settings = Settings(output_dir=output_dir)
    provider = FakeTTSProvider()
    provider_service = ProviderService()
    provider_service.register(provider, device=provider.device, available=True)
    provider_service.select_primary(OMNIVOICE_PROVIDER_ID)
    probe = Mock(return_value=RuntimeInfo(
        python_version="3.12.10", torch_version="2.8.0+cu128",
        cuda_available=True, gpu_name="test GPU",
    ))
    sys_service = SystemService(provider_service, probe)
    # TTSService.__init__ has needed translation_service/voice_profile_service
    # since a Short TTS job's voice_id can also name a cloned voice profile
    # (see main.py's lifespan) - real, cheap-to-construct services here (no
    # network call happens unless translate()/create_voice_profile() is
    # actually invoked, and this fixture's requests are all Vietnamese, so
    # neither is).
    translation_service = TranslationService(settings)
    voice_profile_service = VoiceProfileService(settings, provider_service)
    tts_service = TTSService(settings, provider_service, translation_service, voice_profile_service)

    app = create_app(
        settings=settings,
        service_factory=lambda _: sys_service,
        provider_service_factory=lambda _: provider_service,
        # create_app()'s lifespan always calls this with all 5 positional
        # args (settings, providers, translation_service, voice_profile_service,
        # app_settings_service) - accept and ignore the extra ones since this
        # fixture already has its own pre-built tts_service to return.
        tts_service_factory=lambda *args: tts_service,
    )

    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, provider, provider_service, tts_service, output_dir


def test_valid_tts_request_wav(tts_app_env):
    client, provider, provider_service, _, output_dir = tts_app_env
    # Check initially not loaded
    assert provider_service.status().providers[0].state.value == "NOT_LOADED"
    assert provider.load_calls == 0

    response = client.post("/api/tts", json={
        "text": "Xin chào, đây là bài kiểm tra giọng nói.",
        "language": "vi",
        "voice_id": "omnivoice_auto",
        "speed": 1.0,
        "format": "wav",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    res = data["data"]
    assert res["status"] == "completed"
    assert res["provider"] == "omnivoice"
    assert res["language"] == "vi"
    assert res["voice_id"] == "omnivoice_auto"
    assert res["sample_rate"] == 24000
    assert res["channels"] == 1
    assert res["format"] == "wav"
    assert res["duration_seconds"] > 0
    gen_id = res["generation_id"]
    # Check valid UUID
    uuid.UUID(gen_id)
    assert res["audio_url"] == f"/api/audio/{gen_id}.wav"

    # Verify provider is now READY and loaded once
    assert provider_service.status().providers[0].state.value == "READY"
    assert provider.load_calls == 1

    # Verify file exists on disk
    wav_file = output_dir / f"{gen_id}.wav"
    assert wav_file.is_file()
    assert wav_file.stat().st_size > 0


def test_second_request_reuses_provider(tts_app_env):
    client, provider, _, _, _ = tts_app_env
    payload = {"text": "Xin chào một lần nữa.", "language": "vi"}

    res1 = client.post("/api/tts", json=payload)
    assert res1.status_code == 200
    assert provider.load_calls == 1
    assert provider.synthesize_calls == 1

    res2 = client.post("/api/tts", json=payload)
    assert res2.status_code == 200
    assert provider.load_calls == 1  # Not reloaded!
    assert provider.synthesize_calls == 2


@pytest.mark.parametrize("invalid_text", ["", "   ", None])
def test_empty_or_whitespace_or_null_text_rejected(tts_app_env, invalid_text):
    client, provider, _, _, _ = tts_app_env
    response = client.post("/api/tts", json={"text": invalid_text, "language": "vi"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.INVALID_TEXT.value
    assert provider.load_calls == 0


def test_oversized_text_rejected(tts_app_env):
    client, provider, _, _, _ = tts_app_env
    long_text = "a" * 2001
    response = client.post("/api/tts", json={"text": long_text, "language": "vi"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.TEXT_TOO_LONG.value
    assert provider.load_calls == 0


def test_unsupported_language_rejected(tts_app_env):
    client, provider, _, _, _ = tts_app_env
    response = client.post("/api/tts", json={"text": "Hello", "language": "klingon"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.LANGUAGE_NOT_SUPPORTED.value
    assert provider.load_calls == 0


def test_invalid_voice_rejected(tts_app_env):
    client, provider, _, _, _ = tts_app_env
    response = client.post("/api/tts", json={"text": "Hello", "language": "vi", "voice_id": "nonexistent_voice"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.VOICE_NOT_FOUND.value
    assert provider.load_calls == 0


@pytest.mark.parametrize("invalid_speed", [0.4, 2.1, 1.5, -1.0, 0, "fast", True, False])
def test_invalid_speed_rejected(tts_app_env, invalid_speed):
    client, provider, _, _, _ = tts_app_env
    response = client.post("/api/tts", json={"text": "Hello", "language": "vi", "speed": invalid_speed})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.INVALID_SPEED.value
    assert provider.load_calls == 0


@pytest.mark.parametrize("invalid_format", ["ogg", "flac", "aac", "raw", 123])
def test_invalid_format_rejected(tts_app_env, invalid_format):
    client, provider, _, _, _ = tts_app_env
    response = client.post("/api/tts", json={"text": "Hello", "language": "vi", "format": invalid_format})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.INVALID_FORMAT.value
    assert provider.load_calls == 0


def test_provider_load_failure_normalized(tts_app_env):
    client, provider, provider_service, _, _ = tts_app_env
    provider.fail_load = True
    response = client.post("/api/tts", json={"text": "Hello", "language": "vi"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == ErrorCode.PROVIDER_LOAD_FAILED.value
    assert "private" not in response.text
    assert provider_service.status().providers[0].state.value == "ERROR"


def test_generation_failure_normalized(tts_app_env):
    client, provider, _, _, output_dir = tts_app_env
    provider.fail_synthesize = True
    response = client.post("/api/tts", json={"text": "Hello", "language": "vi"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == ErrorCode.GENERATION_FAILED.value
    assert "Internal model synthesis error" not in response.text
    # Partial audio must be cleaned
    wav_files = list(output_dir.glob("*.wav"))
    assert len(wav_files) == 0


def test_mp3_export_success(tts_app_env):
    client, _, _, _, output_dir = tts_app_env
    with patch("backend.services.tts_service.export_mp3") as mock_export:
        def fake_export(wav_path, mp3_path):
            mp3_path.write_bytes(b"FAKE_MP3_DATA")
            return mp3_path
        mock_export.side_effect = fake_export

        response = client.post("/api/tts", json={"text": "Xin chào", "language": "vi", "format": "mp3"})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["format"] == "mp3"
        gen_id = data["generation_id"]
        assert data["audio_url"] == f"/api/audio/{gen_id}.mp3"
        assert (output_dir / f"{gen_id}.mp3").is_file()


def test_mp3_export_failure_retains_wav(tts_app_env):
    client, _, _, _, output_dir = tts_app_env
    with patch("backend.services.tts_service.export_mp3", return_value=None):
        response = client.post("/api/tts", json={"text": "Xin chào", "language": "vi", "format": "mp3"})
        assert response.status_code == 500
        assert response.json()["error"]["code"] == ErrorCode.AUDIO_EXPORT_FAILED.value
        # WAV must be retained for diagnostics
        wav_files = list(output_dir.glob("*.wav"))
        assert len(wav_files) == 1


def test_audio_retrieval_and_media_types(tts_app_env):
    client, _, _, _, output_dir = tts_app_env
    # Generate WAV
    res = client.post("/api/tts", json={"text": "Xin chào", "language": "vi", "format": "wav"})
    assert res.status_code == 200
    gen_id = res.json()["data"]["generation_id"]

    audio_res = client.get(f"/api/audio/{gen_id}.wav")
    assert audio_res.status_code == 200
    assert audio_res.headers["content-type"].startswith("audio/wav")
    assert len(audio_res.content) > 0

    # Also test an MP3 file
    mp3_file = output_dir / f"{gen_id}.mp3"
    mp3_file.write_bytes(b"ID3_DUMMY_MP3")
    mp3_res = client.get(f"/api/audio/{gen_id}.mp3")
    assert mp3_res.status_code == 200
    assert mp3_res.headers["content-type"].startswith("audio/mpeg")


def test_missing_artifact_returns_404(tts_app_env):
    client, _, _, _, _ = tts_app_env
    missing_id = str(uuid.uuid4())
    res = client.get(f"/api/audio/{missing_id}.wav")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == ErrorCode.ARTIFACT_NOT_FOUND.value


@pytest.mark.parametrize("traversal_attempt", [
    "../../secret.txt",
    "../reference.wav",
    "C:/Windows/system32/calc.exe",
    "/etc/passwd",
    "not-a-uuid.wav",
    f"../../{uuid.uuid4()}.wav",
    f"{uuid.uuid4()}.exe",
])
def test_path_traversal_blocked(tts_app_env, traversal_attempt):
    client, _, _, _, _ = tts_app_env
    res = client.get(f"/api/audio/{traversal_attempt}")
    assert res.status_code in (404, 422)
    assert res.json()["error"]["code"] in (ErrorCode.ARTIFACT_NOT_FOUND.value, ErrorCode.NOT_FOUND.value, ErrorCode.INVALID_REQUEST.value)


def test_no_absolute_paths_returned(tts_app_env):
    client, _, _, _, output_dir = tts_app_env
    res = client.post("/api/tts", json={"text": "Xin chào", "language": "vi"})
    assert res.status_code == 200
    text_content = res.text
    assert str(output_dir) not in text_content
    assert "\\" not in text_content


def test_customer_text_not_logged(tts_app_env, caplog):
    client, _, _, _, _ = tts_app_env
    secret_text = "SECRET_CUSTOMER_CONFIDENTIAL_123456789"
    with caplog.at_level(logging.INFO):
        res = client.post("/api/tts", json={"text": secret_text, "language": "vi"})
        assert res.status_code == 200
    assert secret_text not in caplog.text
    # text_length should be logged
    assert f"text_length={len(secret_text)}" in caplog.text


def test_concurrent_first_requests_do_not_double_load(tmp_path):
    output_dir = tmp_path / "concurrent_api"
    settings = Settings(output_dir=output_dir)
    provider = FakeTTSProvider()
    provider_service = ProviderService()
    provider_service.register(provider, device=provider.device, available=True)
    provider_service.select_primary(OMNIVOICE_PROVIDER_ID)
    tts_service = TTSService(settings, provider_service, TranslationService(settings),
                              VoiceProfileService(settings, provider_service))
    sys_service = SystemService(provider_service, Mock(return_value=RuntimeInfo("3.12.10", "2.8.0+cu128", True, "GPU")))
    app = create_app(settings=settings, service_factory=lambda _: sys_service,
                     provider_service_factory=lambda _: provider_service,
                     tts_service_factory=lambda *args: tts_service)

    with TestClient(app, base_url="http://127.0.0.1") as client:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(client.post, "/api/tts", json={"text": f"Request {i}", "language": "vi"})
                for i in range(4)
            ]
            responses = [f.result() for f in futures]

        assert all(r.status_code == 200 for r in responses)
        assert provider.load_calls == 1
        assert provider_service.status().providers[0].state.value == "READY"

    # After shutdown, provider is unloaded
    assert provider_service.status().providers[0].state.value == "NOT_LOADED"
