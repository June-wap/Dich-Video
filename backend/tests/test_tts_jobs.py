"""Task 2: short-TTS job + history API.

Covers the async job endpoints (POST/GET /api/tts/jobs, GET /api/tts/jobs/{id}),
persistence/restart semantics shared with Task 1, idempotency, and that the
legacy synchronous POST /api/tts contract is unchanged.
"""
from concurrent.futures import ThreadPoolExecutor
import io
import time
import uuid
from unittest.mock import Mock, patch

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.tests.provider_fakes import TEST_PROVIDER_ID
from backend.errors import ErrorCode
from backend.main import create_app
from backend.persistence import Repository
from backend.schemas.tts import TTSRequest, TTSStatus
from backend.services.provider_service import ProviderService
from backend.services.system_service import RuntimeInfo, SystemService
from backend.services.translation_service import TranslationService
from backend.services.tts_service import TTSService
from backend.services.voice_profile_service import VoiceProfileService
from backend.tests.provider_fakes import FakeCloneProvider


def payload(**overrides):
    base = {
        "text": "Xin chào, đây là kiểm tra job TTS.",
        "language": "vi",
        "voice_id": "test_auto",
        "speed": 1.0,
        "format": "wav",
    }
    base.update(overrides)
    return base


def wait_http(client, job_id, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/tts/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"COMPLETED", "FAILED"}:
            return body
        time.sleep(0.005)
    pytest.fail("Job did not terminate in time")


def wait_service(service, job_id, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = service.status(job_id)
        if snapshot.status in {"COMPLETED", "FAILED"}:
            return snapshot
        time.sleep(0.005)
    pytest.fail("Job did not terminate in time")


@pytest.fixture
def jobs_env(tmp_path):
    output_dir = tmp_path / "outputs" / "api"
    # database_path must be isolated per test like output_dir is: without it,
    # Repository falls back to Settings.app_data_dir's real, persistent
    # %LOCALAPPDATA%\Voca Basic\data\metadata.sqlite3 (see backend/persistence.py),
    # so jobs created by every test run - not just this one - accumulate in
    # the same database (this was the actual cause of
    # test_validation_failure_returns_422_and_creates_no_job expecting
    # tts_service.history() == [] and getting a long leaked history instead).
    settings = Settings(output_dir=output_dir, database_path=tmp_path / "metadata.sqlite3")
    provider = FakeCloneProvider()
    provider_service = ProviderService()
    provider_service.register(provider, device=provider.device, available=True)
    provider_service.select_primary(TEST_PROVIDER_ID)
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
        yield client, provider, provider_service, tts_service, settings, output_dir


# ---------------------------------------------------------------------------
# WAV success
# ---------------------------------------------------------------------------

def test_create_job_wav_success(jobs_env):
    client, provider, _, _, _, output_dir = jobs_env
    response = client.post("/api/tts/jobs", json=payload())
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    job_id = body["job_id"]
    uuid.UUID(job_id)  # valid UUID

    final = wait_http(client, job_id)
    assert final["status"] == "COMPLETED"
    assert final["audio_url"] == f"/api/audio/{job_id}.wav"

    get_resp = client.get(f"/api/tts/jobs/{job_id}")
    assert get_resp.status_code == 200
    assert get_resp.json() == final

    wav_file = output_dir / f"{job_id}.wav"
    assert wav_file.is_file()
    assert wav_file.stat().st_size > 0
    assert provider.synthesize_calls == 1


# ---------------------------------------------------------------------------
# MP3 success
# ---------------------------------------------------------------------------

def test_create_job_mp3_success(jobs_env):
    client, _, _, _, _, output_dir = jobs_env
    with patch("backend.services.tts_service.export_mp3") as mock_export:
        def fake_export(wav_path, mp3_path):
            mp3_path.write_bytes(b"FAKE_MP3_DATA")
            return mp3_path
        mock_export.side_effect = fake_export

        response = client.post("/api/tts/jobs", json=payload(format="mp3"))
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        final = wait_http(client, job_id)
        assert final["status"] == "COMPLETED"
        assert final["audio_url"] == f"/api/audio/{job_id}.mp3"
        assert (output_dir / f"{job_id}.mp3").is_file()


# ---------------------------------------------------------------------------
# Validation failure
# ---------------------------------------------------------------------------

def test_validation_failure_returns_422_and_creates_no_job(jobs_env):
    client, provider, _, tts_service, _, _ = jobs_env
    response = client.post("/api/tts/jobs", json=payload(text=""))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.INVALID_TEXT.value
    assert provider.load_calls == 0
    assert tts_service.history() == []


def test_invalid_idempotency_key_type_rejected(jobs_env):
    client, *_ = jobs_env
    response = client.post("/api/tts/jobs", json=payload(idempotency_key=12345))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.INVALID_REQUEST.value


# ---------------------------------------------------------------------------
# Provider/generation failure
# ---------------------------------------------------------------------------

def test_provider_generation_failure(jobs_env):
    client, provider, _, _, _, output_dir = jobs_env
    provider.fail_synthesize = True
    response = client.post("/api/tts/jobs", json=payload())
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    final = wait_http(client, job_id)
    assert final["status"] == "FAILED"
    assert final["error"]["code"] == ErrorCode.GENERATION_FAILED.value
    assert not final.get("audio_url")
    assert list(output_dir.glob("*.wav")) == []


def test_provider_load_failure(jobs_env):
    client, provider, provider_service, _, _, _ = jobs_env
    provider.fail_load = True
    response = client.post("/api/tts/jobs", json=payload())
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    final = wait_http(client, job_id)
    assert final["status"] == "FAILED"
    assert final["error"]["code"] == ErrorCode.PROVIDER_LOAD_FAILED.value
    assert "private" not in str(final)
    assert provider_service.status().providers[0].state.value == "ERROR"


# ---------------------------------------------------------------------------
# Persisted history
# ---------------------------------------------------------------------------

def test_persisted_history(jobs_env):
    client, *_ = jobs_env
    ids = []
    for i in range(3):
        response = client.post("/api/tts/jobs", json=payload(text=f"Câu thứ {i}."))
        assert response.status_code == 202
        ids.append(response.json()["job_id"])
    for job_id in ids:
        wait_http(client, job_id)

    history_resp = client.get("/api/tts/jobs")
    assert history_resp.status_code == 200
    history = history_resp.json()
    returned_ids = [item["job_id"] for item in history]
    assert set(ids).issubset(set(returned_ids))
    for item in history:
        if item["job_id"] in ids:
            assert item["status"] == "COMPLETED"


# ---------------------------------------------------------------------------
# Restart / read-back
# ---------------------------------------------------------------------------

def test_restart_read_back(tmp_path):
    settings = Settings(output_dir=tmp_path / "restart", database_path=tmp_path / "restart.sqlite3")
    provider = ProviderService()
    fake = FakeCloneProvider()
    provider.register(fake, device=fake.device, available=True)
    provider.select_primary(TEST_PROVIDER_ID)

    service1 = TTSService(settings, provider, TranslationService(settings),
                           VoiceProfileService(settings, provider))
    snapshot = service1.submit(
    TTSRequest(
        text="Trước khi khởi động lại.",
        language="vi",
        voice_id="test_auto",
    )
)
    final = wait_service(service1, snapshot.job_id)
    assert final.status == "COMPLETED"
    service1.close()

    # Simulate a backend restart: a fresh service/provider registry, same DB/output dir.
    provider2 = ProviderService()
    fake2 = FakeCloneProvider()
    provider2.register(fake2, device=fake2.device, available=True)
    provider2.select_primary(TEST_PROVIDER_ID)
    service2 = TTSService(settings, provider2, TranslationService(settings),
                           VoiceProfileService(settings, provider2))
    try:
        read_back = service2.status(snapshot.job_id)
        assert read_back.status == "COMPLETED"
        assert read_back.audio_url == final.audio_url

        history = service2.history()
        assert any(item.job_id == snapshot.job_id for item in history)

        job_row = service2._db.get_job(snapshot.job_id)
        assert job_row["kind"] == "short"
        assert job_row["status"] == "COMPLETED"

        outputs = service2._db.get_audio_outputs(snapshot.job_id)
        assert len(outputs) == 1
    finally:
        service2.close()


def test_interrupted_job_marked_failed_on_restart_not_resumed(tmp_path):
    """Task 1's recovery semantics must hold for short-TTS jobs too:
    QUEUED/RUNNING -> FAILED/INTERRUPTED on restart, never resumed."""
    settings = Settings(output_dir=tmp_path / "interrupt", database_path=tmp_path / "interrupt.sqlite3")

    repo = Repository(settings)
    stuck = TTSStatus(job_id="stuck-short-job", status="RUNNING")
    repo.create_job(
        stuck,
        {"request": {"text": "..."}, "audio": {"sample_rate": 24000, "channels": 1, "format": "wav"}},
        kind="short",
    )
    repo.save_job(stuck, {})

    provider_service = ProviderService()
    fake = FakeCloneProvider()
    provider_service.register(fake, device=fake.device, available=True)
    provider_service.select_primary(TEST_PROVIDER_ID)

    service = TTSService(settings, provider_service, TranslationService(settings),
                          VoiceProfileService(settings, provider_service))
    try:
        recovered = service.status("stuck-short-job")
        assert recovered.status == "FAILED"
        assert recovered.error.code == "INTERRUPTED"
        # Never resumed/re-run: the provider was never asked to synthesize it.
        assert fake.synthesize_calls == 0
    finally:
        service.close()


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_idempotency_retry_same_key_returns_same_job(jobs_env):
    client, provider, _, tts_service, _, _ = jobs_env
    key = "client-retry-key-1"

    first = client.post("/api/tts/jobs", json=payload(idempotency_key=key))
    assert first.status_code == 202
    job_id = first.json()["job_id"]
    wait_http(client, job_id)

    second = client.post("/api/tts/jobs", json=payload(idempotency_key=key))
    assert second.status_code == 202
    assert second.json()["job_id"] == job_id

    matching = [h for h in tts_service.history() if h.job_id == job_id]
    assert len(matching) == 1
    assert provider.synthesize_calls == 1


def test_idempotency_different_keys_create_different_jobs(jobs_env):
    client, provider, *_ = jobs_env
    first = client.post("/api/tts/jobs", json=payload(idempotency_key="key-a"))
    second = client.post("/api/tts/jobs", json=payload(idempotency_key="key-b"))
    assert first.json()["job_id"] != second.json()["job_id"]
    wait_http(client, first.json()["job_id"])
    wait_http(client, second.json()["job_id"])
    assert provider.synthesize_calls == 2


def test_idempotency_concurrent_same_key_creates_single_job(jobs_env):
    client, provider, *_ = jobs_env
    key = "concurrent-key"
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(client.post, "/api/tts/jobs", json=payload(idempotency_key=key))
            for _ in range(4)
        ]
        responses = [f.result() for f in futures]

    assert all(r.status_code == 202 for r in responses)
    job_ids = {r.json()["job_id"] for r in responses}
    assert len(job_ids) == 1
    wait_http(client, next(iter(job_ids)))
    assert provider.synthesize_calls == 1


def test_idempotency_same_key_conflicting_payload_rejected(jobs_env):
    """Reusing an idempotency_key with a DIFFERENT request payload must be a
    deterministic conflict, never a silent replay of the unrelated prior job.
    """
    client, provider, _, tts_service, _, _ = jobs_env
    key = "reused-key-different-payload"

    first = client.post("/api/tts/jobs", json=payload(idempotency_key=key, text="Xin chào lần một."))
    assert first.status_code == 202
    job_id = first.json()["job_id"]
    wait_http(client, job_id)

    second = client.post("/api/tts/jobs", json=payload(idempotency_key=key, text="Một câu hoàn toàn khác."))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == ErrorCode.IDEMPOTENCY_KEY_CONFLICT.value

    # No new job was created, and the original job's own record is untouched.
    matching = [h for h in tts_service.history() if h.job_id == job_id]
    assert len(matching) == 1
    assert provider.synthesize_calls == 1

    # A genuinely identical retry (same key, same payload) still works after a
    # conflicting attempt was rejected: the stored fingerprint of the ORIGINAL
    # job is untouched by the rejected conflicting submit.
    third = client.post("/api/tts/jobs", json=payload(idempotency_key=key, text="Xin chào lần một."))
    assert third.status_code == 202
    assert third.json()["job_id"] == job_id
    assert provider.synthesize_calls == 1


def test_idempotency_same_key_conflicting_format_rejected(jobs_env):
    """The conflict check covers the whole payload, not just text."""
    client, provider, *_ = jobs_env
    key = "reused-key-different-format"

    first = client.post("/api/tts/jobs", json=payload(idempotency_key=key, format="wav"))
    assert first.status_code == 202
    wait_http(client, first.json()["job_id"])

    second = client.post("/api/tts/jobs", json=payload(idempotency_key=key, format="mp3"))
    assert second.status_code == 409
    assert second.json()["error"]["code"] == ErrorCode.IDEMPOTENCY_KEY_CONFLICT.value
    assert provider.synthesize_calls == 1


# ---------------------------------------------------------------------------
# Missing artifact / error state
# ---------------------------------------------------------------------------

def test_unknown_job_returns_404(jobs_env):
    client, *_ = jobs_env
    response = client.get("/api/tts/jobs/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == ErrorCode.JOB_NOT_FOUND.value


def test_failed_job_has_no_retrievable_audio(jobs_env):
    client, provider, *_ = jobs_env
    provider.fail_synthesize = True
    response = client.post("/api/tts/jobs", json=payload())
    job_id = response.json()["job_id"]
    final = wait_http(client, job_id)
    assert final["status"] == "FAILED"

    audio_resp = client.get(f"/api/audio/{job_id}.wav")
    assert audio_resp.status_code == 404
    assert audio_resp.json()["error"]["code"] == ErrorCode.ARTIFACT_NOT_FOUND.value


def test_missing_artifact_after_completion_returns_404_but_job_stays_completed(jobs_env):
    """Clarifies the contract when a COMPLETED job's audio file is later
    removed from disk (out-of-band cleanup, disk issue, etc.): job status is
    a historical record of the synthesis outcome and does NOT re-check the
    filesystem, so it keeps reporting COMPLETED with its original audio_url.
    Whether the bytes are still actually fetchable is decided independently,
    and only at request time, by GET /api/audio/{artifact_id} - which is the
    single source of truth for artifact availability.
    """
    client, _, _, _, _, output_dir = jobs_env
    response = client.post("/api/tts/jobs", json=payload())
    job_id = response.json()["job_id"]
    final = wait_http(client, job_id)
    assert final["status"] == "COMPLETED"
    audio_url = final["audio_url"]

    wav_file = output_dir / f"{job_id}.wav"
    assert wav_file.is_file()
    wav_file.unlink()  # Simulate the artifact disappearing after completion.

    # Job status/history is unaffected: it still reflects that synthesis
    # completed successfully, with the same audio_url as before.
    status_resp = client.get(f"/api/tts/jobs/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "COMPLETED"
    assert status_resp.json()["audio_url"] == audio_url

    history_resp = client.get("/api/tts/jobs")
    matching = [item for item in history_resp.json() if item["job_id"] == job_id]
    assert len(matching) == 1
    assert matching[0]["status"] == "COMPLETED"

    # Only the audio endpoint, which checks the filesystem, reports the
    # artifact as gone.
    audio_resp = client.get(audio_url)
    assert audio_resp.status_code == 404
    assert audio_resp.json()["error"]["code"] == ErrorCode.ARTIFACT_NOT_FOUND.value


# ---------------------------------------------------------------------------
# Backward compatibility: legacy synchronous POST /api/tts is unchanged
# ---------------------------------------------------------------------------

def test_legacy_endpoint_still_synchronous_200(jobs_env):
    client, _, _, _, _, output_dir = jobs_env
    response = client.post("/api/tts", json=payload())
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "completed"
    gen_id = data["generation_id"]
    assert (output_dir / f"{gen_id}.wav").is_file()

    # The legacy job is also visible through the new history endpoint.
    history_resp = client.get("/api/tts/jobs")
    assert any(item["job_id"] == gen_id for item in history_resp.json())


def test_legacy_endpoint_generation_failure_still_500(jobs_env):
    client, provider, _, _, _, output_dir = jobs_env
    provider.fail_synthesize = True
    response = client.post("/api/tts", json=payload())
    assert response.status_code == 500
    assert response.json()["error"]["code"] == ErrorCode.GENERATION_FAILED.value
    assert list(output_dir.glob("*.wav")) == []


# ---------------------------------------------------------------------------
# CP3: Short-TTS voice_id names a real cloned voice profile
#
# jobs_env's app.state.voice_profile_service (built by create_app's own
# default voice_profile_service_factory) is a SEPARATE VoiceProfileService
# instance from the one jobs_env manually wired into its own pre-built
# tts_service - so profiles must be created directly through
# `tts_service._voice_profiles` (the instance TTSService actually resolves
# voice_id against), not through POST /api/voices/profiles, or the two
# instances' in-memory _records would silently diverge despite sharing one
# database file.
# ---------------------------------------------------------------------------

def _clone_wav_bytes(duration: float = 5.0, sample_rate: int = 24000) -> bytes:
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    sig = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, sig, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def _create_clone_profile(tts_service, transcript="Văn bản mẫu để nhân bản giọng nói."):
    resp = tts_service._voice_profiles.create_profile(
        audio_bytes=_clone_wav_bytes(), filename="ref.wav", transcript=transcript,
    )
    return resp.data.profile_id


def test_short_tts_accepts_existing_clone_profile_as_voice_id(jobs_env):
    client, provider, _, tts_service, _, output_dir = jobs_env
    pid = _create_clone_profile(tts_service)
    assert provider.create_profile_calls == 1

    response = client.post("/api/tts/jobs", json=payload(voice_id=pid))
    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED"
    job_id = response.json()["job_id"]

    final = wait_http(client, job_id)
    assert final["status"] == "COMPLETED"

    # Routed through synthesize_cloned, never the normal built-in-voice path.
    assert provider.synthesize_cloned_calls == 1
    assert provider.synthesize_calls == 0

    wav_file = output_dir / f"{job_id}.wav"
    assert wav_file.is_file()
    assert wav_file.stat().st_size > 0


def test_short_tts_rejects_arbitrary_uuid_as_voice_id(jobs_env):
    client, provider, _, _, _, _ = jobs_env
    response = client.post("/api/tts/jobs", json=payload(voice_id=str(uuid.uuid4())))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.VOICE_NOT_FOUND.value
    # An unknown profile id must never trigger a real model load just to be rejected.
    assert provider.load_calls == 0


def test_short_tts_rejects_malformed_voice_id(jobs_env):
    client, provider, _, _, _, _ = jobs_env
    response = client.post("/api/tts/jobs", json=payload(voice_id="not-a-real-voice-or-uuid"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.VOICE_NOT_FOUND.value
    assert provider.load_calls == 0


def test_short_tts_vieneu_clone_rejects_non_vietnamese_language(jobs_env):
    client, provider, _, tts_service, _, _ = jobs_env
    pid = _create_clone_profile(tts_service)
    # _create_clone_profile() above already loads the provider for real (a
    # voice profile is created by actually encoding the reference audio) -
    # so load_calls is legitimately 1 by this point. What must never happen
    # is the language-rejected request itself touching synthesis.
    assert provider.load_calls == 1
    response = client.post("/api/tts/jobs", json=payload(voice_id=pid, language="en"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == ErrorCode.VOICE_PROFILE_PROVIDER_MISMATCH.value
    assert provider.load_calls == 1  # No additional load triggered by the rejected request.
    assert provider.synthesize_calls == 0
    assert provider.synthesize_cloned_calls == 0


def test_short_tts_clone_diagnostics_marks_cloned_true(jobs_env):
    client, provider, _, tts_service, _, _ = jobs_env
    pid = _create_clone_profile(tts_service)
    response = client.post("/api/tts/jobs", json=payload(voice_id=pid))
    job_id = response.json()["job_id"]
    wait_http(client, job_id)

    job = tts_service._get(job_id)
    assert job.diagnostics["result"]["cloned"] is True


def test_baseline_vieneu_default_voice_unaffected_by_clone_routing(jobs_env):
    """A clone profile existing must not change normal built-in-voice routing."""
    client, provider, _, tts_service, _, _ = jobs_env
    _create_clone_profile(tts_service)

    response = client.post("/api/tts/jobs", json=payload())
    job_id = response.json()["job_id"]
    final = wait_http(client, job_id)
    assert final["status"] == "COMPLETED"
    assert provider.synthesize_calls == 1
    assert provider.synthesize_cloned_calls == 0


def test_short_tts_clone_generation_failure_marks_job_failed_and_releases_profile(jobs_env):
    client, provider, _, tts_service, _, _ = jobs_env
    pid = _create_clone_profile(tts_service)
    provider.fail_synthesize_cloned = True

    response = client.post("/api/tts/jobs", json=payload(voice_id=pid))
    job_id = response.json()["job_id"]
    final = wait_http(client, job_id)
    assert final["status"] == "FAILED"
    assert final["error"]["code"] == ErrorCode.GENERATION_FAILED.value

    # reserve_profile()/release_profile() must stay paired even on failure -
    # the finally block in TTSService._run() is what guarantees this.
    record = tts_service._voice_profiles.get_profile_record(pid)
    assert record.active_jobs == 0


def test_short_tts_clone_restore_after_restart(tmp_path):
    """CP3 Section 8-G: provider_profile is never persisted (see
    VoiceProfileService._persist). A fresh process must rebuild it lazily
    from reference_path + transcript, via provider.create_voice_profile(),
    before a Short TTS job naming that profile can synthesize."""
    settings = Settings(output_dir=tmp_path / "clone_restart", database_path=tmp_path / "clone_restart.sqlite3")
    provider1 = ProviderService()
    fake1 = FakeCloneProvider()
    provider1.register(fake1, device=fake1.device, available=True)
    provider1.select_primary(TEST_PROVIDER_ID)
    vps1 = VoiceProfileService(settings, provider1)
    service1 = TTSService(settings, provider1, TranslationService(settings), vps1)

    resp = vps1.create_profile(_clone_wav_bytes(), "ref.wav", "Văn bản mẫu để nhân bản giọng nói.")
    pid = resp.data.profile_id
    assert fake1.create_profile_calls == 1
    service1.close()

    # Simulate a backend restart: fresh service/provider registry, same DB/output dir.
    provider2 = ProviderService()
    fake2 = FakeCloneProvider()
    provider2.register(fake2, device=fake2.device, available=True)
    provider2.select_primary(TEST_PROVIDER_ID)
    vps2 = VoiceProfileService(settings, provider2)
    service2 = TTSService(settings, provider2, TranslationService(settings), vps2)
    try:
        record = vps2.get_profile_record(pid)
        assert record.provider_profile is None  # Never deserialized/persisted verbatim.
        assert fake2.create_profile_calls == 0  # Not rebuilt until actually needed.

        snapshot = service2.submit(TTSRequest(text="Sau khi khởi động lại.", language="vi", voice_id=pid))
        final = wait_service(service2, snapshot.job_id)
        assert final.status == "COMPLETED"
        # restore_profile() rebuilt provider_profile via create_voice_profile(reference_path, transcript).
        assert fake2.create_profile_calls == 1
        assert fake2.synthesize_cloned_calls == 1
    finally:
        service2.close()
