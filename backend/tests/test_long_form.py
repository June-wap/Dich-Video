import io
from pathlib import Path
import threading
import time
import uuid
from unittest.mock import Mock

from fastapi.testclient import TestClient
import numpy as np
import pytest
import soundfile as sf

from backend.config import Settings
from backend.errors import ApplicationError, ErrorCode
from backend.main import create_app
from backend.schemas.long_form import LongFormRequest
from backend.services.long_form_service import validate_wav
from backend.tests.provider_fakes import FakeCloneProvider, registry
from core.long_text import build_chunks
import core.tts_manager as core

TEXT = ('Anh nói: “Hôm nay có 3.14 mét vải, giá 12.500 đồng.”\n'
        'Chúng ta kiểm tra số 123, dấu chấm phẩy; và câu hỏi?\n\n'
        'Đoạn thứ hai! Đây là nội dung tiếp theo, không được bỏ hoặc lặp.\n\n'
        + 'một câu tiếng Việt dài có dấu và nhiều từ ' * 25 + '.')


def wait(jobs, job_id):
    deadline = time.monotonic() + 10
    history = []
    while time.monotonic() < deadline:
        result = jobs.status(job_id)
        history.append(result.progress_percent)
        if result.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            assert history == sorted(history)
            return result
        time.sleep(.005)
    pytest.fail("Job did not terminate")


@pytest.fixture
def harness(tmp_path):
    settings = Settings(output_dir=tmp_path / "âm thanh")
    provider = FakeCloneProvider()
    providers = registry(provider)
    app = create_app(settings, provider_service_factory=lambda _: providers)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        profiles = app.state.voice_profile_service
        audio = io.BytesIO()
        sf.write(audio, np.ones(72000) * .1, 24000, format="WAV")
        profile_id = profiles.create_profile(audio.getvalue(), "ref.wav", "Mẫu đã kiểm tra.").data.profile_id
        yield client, app.state.long_form_service, provider, profiles, profile_id, settings


def payload(profile_id, **kwargs):
    return {"text": TEXT, "profile_id": profile_id, **kwargs}


def test_create_order_identity_merge_and_artifact(harness, monkeypatch):
    client, jobs, provider, profiles, pid, settings = harness
    calls, merged = [], []
    original = provider.synthesize_cloned
    merge = core.merge_segments
    profile = profiles.get_profile_record(pid).provider_profile

    def synthesize(**kw):
        calls.append((kw["text"], kw["profile"], Path(kw["output_path"])))
        result = original(**kw)
        sf.write(kw["output_path"], np.ones(12000) * (len(calls) / 20), 24000)
        return result

    def ordered(paths, *args, **kwargs):
        merged.extend(paths)
        return merge(paths, *args, **kwargs)

    monkeypatch.setattr(provider, "synthesize_cloned", synthesize)
    monkeypatch.setattr(core, "merge_segments", ordered)
    response = client.post("/api/tts/long-form", json=payload(pid))
    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED"
    result = wait(jobs, response.json()["job_id"])
    assert result.status == "COMPLETED"
    assert [c[0] for c in calls] == [c.text for c in build_chunks(TEXT)]
    assert "".join(TEXT.split()) == "".join("".join(c[0].split()) for c in calls)
    assert all(c[1] is profile for c in calls)
    assert merged == [c[2] for c in calls]
    assert provider.create_profile_calls == 1
    assert provider.load_calls == provider._load_count == 1
    assert provider.synthesize_calls == 0
    assert result.progress_percent == 100
    data = client.get(result.audio_url)
    assert data.status_code == 200
    decoded, sr = sf.read(io.BytesIO(data.content))
    assert sr == 24000 and decoded.ndim == 1 and np.isfinite(decoded).all()
    # Boundary processing must retain the source amplitudes in source order.
    # Ignore the existing 3 ms edge fades; inspect sustained plateaus only.
    from itertools import groupby
    runs = [value for value, samples in groupby(np.round(decoded * 20).astype(int))
            if value and sum(1 for _ in samples) > 2400]
    assert runs == list(range(1, len(calls) + 1))
    assert not list((settings.output_dir / "long_form_private").rglob("chunk_*.wav"))
    assert set(client.get(f"/api/tts/long-form/{result.job_id}").json()) == {
        "job_id", "status", "progress_percent", "audio_url"}
    assert client.delete(f"/api/tts/long-form/{result.job_id}").json()["status"] == "COMPLETED"
    assert client.delete(f"/api/voices/profiles/{pid}").status_code == 200


@pytest.mark.parametrize("override", [
    {"text": ""}, {"text": " \n "}, {"text": None}, {"text": 4},
    {"text": "a" * 100001}, {"language": "xx"}, {"language": []},
    {"speed": 0.8}, {"speed": True}, {"speed": "1"}, {"format": "flac"},
    {"profile_id": None}, {"profile_id": "../../private"},
    {"profile_id": str(uuid.uuid4())}, {"filename": "C:/private.wav"},
])
def test_validation(harness, override):
    client, jobs, provider, _, pid, _ = harness
    response = client.post("/api/tts/long-form", json=payload(pid, **override) if "profile_id" not in override
                           else {**payload(pid), **override})
    assert response.status_code in (404, 422)
    assert not jobs._jobs and provider.synthesize_cloned_calls == 0


def test_profile_required(harness):
    client = harness[0]
    assert client.post("/api/tts/long-form", json={"text": "Xin chào"}).status_code == 422


def test_fifo_running_cancel_and_profile_deletion(harness, monkeypatch):
    client, jobs, provider, profiles, pid, _ = harness
    entered, release = threading.Event(), threading.Event()
    original = provider.synthesize_cloned
    def blocked(**kw):
        entered.set()
        assert release.wait(5)
        return original(**kw)
    monkeypatch.setattr(provider, "synthesize_cloned", blocked)
    try:
        first = client.post("/api/tts/long-form", json=payload(pid)).json()["job_id"]
        assert entered.wait(3)
        second = client.post("/api/tts/long-form", json=payload(pid)).json()["job_id"]
        third = client.post("/api/tts/long-form", json=payload(pid)).json()["job_id"]
        assert jobs.status(second).status == jobs.status(third).status == "QUEUED"
        response = client.delete(f"/api/voices/profiles/{pid}")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "PROFILE_IN_USE"
        assert client.delete(f"/api/tts/long-form/{second}").json()["status"] == "CANCELLED"
        assert client.delete(f"/api/tts/long-form/{first}").json()["status"] == "RUNNING"
        release.set()
        assert wait(jobs, first).status == "CANCELLED"
        assert wait(jobs, third).status == "COMPLETED"
        assert provider.synthesize_cloned_calls == 1 + len(build_chunks(TEXT))
        assert profiles.get_profile_record(pid).active_jobs == 0
    finally:
        release.set()


@pytest.mark.parametrize("fault", ["exception", "nonpass", "missing", "wrong_path", "nan", "empty", "stereo", "rate", "reload"])
def test_chunk_failure_never_skips_or_merges(harness, monkeypatch, caplog, fault):
    client, jobs, provider, profiles, pid, settings = harness
    original = provider.synthesize_cloned
    call_count = 0
    def broken(**kw):
        nonlocal call_count
        call_count += 1
        result = original(**kw)
        if call_count != 2:
            return result
        path = kw["output_path"]
        if fault == "exception":
            raise RuntimeError("SECRET_CUSTOMER_TEXT C:/private/reference.wav")
        if fault == "nonpass":
            result.status, result.error = "FAIL", "SECRET_CUSTOMER_TEXT"
        elif fault == "missing":
            Path(path).unlink()
        elif fault == "wrong_path":
            result.wav_path = "C:/private/reference.wav"
        elif fault == "nan":
            sf.write(path, [float("nan")], 24000, subtype="FLOAT")
        elif fault == "empty":
            Path(path).write_bytes(b"RIFF")
        elif fault == "stereo":
            sf.write(path, np.ones((240, 2)), 24000)
        elif fault == "rate":
            sf.write(path, np.ones(240), 16000)
        elif fault == "reload":
            provider._model = object()
        return result
    monkeypatch.setattr(provider, "synthesize_cloned", broken)
    merge = Mock(side_effect=AssertionError("must not merge"))
    monkeypatch.setattr(core, "merge_segments", merge)
    result = wait(jobs, jobs.submit(LongFormRequest(**payload(pid))).job_id)
    assert result.status == "FAILED" and result.audio_url is None
    assert result.error.code == "GENERATION_FAILED"
    assert call_count == 2 and merge.call_count == 0
    assert "SECRET_CUSTOMER_TEXT" not in caplog.text and "C:/private" not in caplog.text
    assert not list(settings.output_dir.glob("*.wav"))
    assert profiles.get_profile_record(pid).active_jobs == 0


def test_invalid_final_rejected_before_mp3(harness, monkeypatch):
    _, jobs, _, _, pid, settings = harness
    def invalid(paths, output_path, **kw):
        sf.write(output_path, [float("inf")], 24000, subtype="FLOAT")
    monkeypatch.setattr(core, "merge_segments", invalid)
    exporter = Mock()
    monkeypatch.setattr(core, "export_mp3", exporter)
    result = wait(jobs, jobs.submit(LongFormRequest(**payload(pid, format="mp3"))).job_id)
    assert result.status == "FAILED" and exporter.call_count == 0
    assert not list(settings.output_dir.glob("*.wav"))


@pytest.mark.parametrize("successful", [False, True])
def test_mp3_keeps_valid_wav(harness, monkeypatch, successful):
    _, jobs, _, _, pid, settings = harness
    def export(path):
        validate_wav(path)
        if successful:
            out = path.with_suffix(".mp3")
            out.write_bytes(b"mock encoder output")
            return out
        return None
    monkeypatch.setattr(core, "export_mp3", export)
    result = wait(jobs, jobs.submit(LongFormRequest(**payload(pid, format="mp3"))).job_id)
    assert result.status == "COMPLETED"
    assert result.audio_url.endswith(".mp3" if successful else ".wav")
    assert len(list(settings.output_dir.glob("*.wav"))) == 1


def test_shutdown_cancels_and_releases_queued(harness):
    _, jobs, _, profiles, pid, _ = harness
    with jobs._providers.inference_lock:
        result = jobs.submit(LongFormRequest(**payload(pid)))
        assert jobs.cancel(result.job_id).status == "CANCELLED"
    jobs.close()
    assert profiles.get_profile_record(pid).active_jobs == 0
    with pytest.raises(ApplicationError):
        jobs.submit(LongFormRequest(**payload(pid)))


def test_unknown_job_paths_and_cors(harness):
    client = harness[0]
    for method in (client.get, client.delete):
        assert method("/api/tts/long-form/missing").status_code == 404
    for path in ("chunk_0000.wav", "long_form_private", "..%5Csecret.wav", str(uuid.uuid4()) + ".wav"):
        assert client.get("/api/audio/" + path).status_code == 404
    response = client.options("/api/tts/long-form/id", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE"})
    assert response.status_code == 200


def test_text_integrity_guard_prevents_generation(harness, monkeypatch):
    _, jobs, provider, _, pid, _ = harness
    original = core.build_chunks
    monkeypatch.setattr(core, "build_chunks", lambda *a: original(*a)[1:])
    result = wait(jobs, jobs.submit(LongFormRequest(**payload(pid))).job_id)
    assert result.status == "FAILED" and provider.synthesize_cloned_calls == 0


def test_profile_unloaded_fails_without_model_reload(harness):
    _, jobs, provider, _, pid, _ = harness
    provider._model = None
    result = wait(jobs, jobs.submit(LongFormRequest(**payload(pid))).job_id)
    assert result.status == "FAILED" and result.error.code == "VOICE_PROFILE_NOT_READY"
    assert provider.load_calls == 1 and provider.synthesize_cloned_calls == 0


def test_numbers_quotes_and_unicode_intact():
    chunks = build_chunks(TEXT)
    assert "3.14" in chunks[0].text and "12.500" in chunks[0].text
    assert chunks[0].text.count("“") == chunks[0].text.count("”") == 1
    assert "".join(TEXT.split()) == "".join("".join(c.text.split()) for c in chunks)


def test_short_and_clone_share_execution_gate(harness, monkeypatch):
    client, jobs, provider, _, pid, _ = harness
    entered, release, short_done = threading.Event(), threading.Event(), threading.Event()
    original = provider.synthesize_cloned
    def blocked(**kw):
        entered.set()
        assert release.wait(5)
        return original(**kw)
    monkeypatch.setattr(provider, "synthesize_cloned", blocked)
    job_id = jobs.submit(LongFormRequest(**payload(pid))).job_id
    assert entered.wait(3)
    responses = []
    def short():
        responses.append(client.post("/api/tts", json={"text": "Xin chào.", "language": "vi"}))
        short_done.set()
    thread = threading.Thread(target=short)
    thread.start()
    try:
        assert not short_done.wait(.1)
        assert provider.synthesize_calls == 0
    finally:
        release.set()
        thread.join(5)
    assert wait(jobs, job_id).status == "COMPLETED"
    assert responses[0].status_code == 200


def test_cancel_last_chunk_never_merges(harness, monkeypatch):
    _, jobs, provider, _, pid, _ = harness
    entered, release = threading.Event(), threading.Event()
    original = provider.synthesize_cloned
    def blocked(**kw):
        entered.set()
        assert release.wait(5)
        return original(**kw)
    monkeypatch.setattr(provider, "synthesize_cloned", blocked)
    merge = Mock(side_effect=AssertionError("cancelled job must not merge"))
    monkeypatch.setattr(core, "merge_segments", merge)
    try:
        job = jobs.submit(LongFormRequest(**payload(pid, text="Một câu duy nhất.")))
        assert entered.wait(3)
        jobs.cancel(job.job_id)
        release.set()
        assert wait(jobs, job.job_id).status == "CANCELLED"
        assert merge.call_count == 0
    finally:
        release.set()


def test_mp3_exception_keeps_valid_wav(harness, monkeypatch, caplog):
    _, jobs, _, _, pid, _ = harness
    monkeypatch.setattr(core, "export_mp3", Mock(side_effect=RuntimeError("SECRET_TRANSCRIPT")))
    result = wait(jobs, jobs.submit(LongFormRequest(**payload(pid, format="mp3"))).job_id)
    assert result.status == "COMPLETED" and result.audio_url.endswith(".wav")
    assert "SECRET_TRANSCRIPT" not in caplog.text


def test_success_logs_never_include_customer_text(harness, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    _, jobs, _, _, pid, _ = harness
    text = "NỘI_DUNG_RIÊNG_TƯ_583194. Đây là câu tiếp theo."
    result = wait(jobs, jobs.submit(LongFormRequest(**payload(pid, text=text))).job_id)
    assert result.status == "COMPLETED"
    assert "NỘI_DUNG_RIÊNG_TƯ_583194" not in caplog.text


def test_queued_profile_pin_blocks_deletion(harness):
    _, jobs, _, profiles, pid, _ = harness
    with jobs._providers.inference_lock:
        job = jobs.submit(LongFormRequest(**payload(pid)))
        assert jobs.status(job.job_id).status == "QUEUED"
        with pytest.raises(ApplicationError) as exc:
            profiles.delete_profile(pid)
        assert exc.value.code == ErrorCode.PROFILE_IN_USE
        jobs.cancel(job.job_id)
        profiles.delete_profile(pid)


def test_merge_exception_never_publishes(harness, monkeypatch, caplog):
    _, jobs, _, _, pid, settings = harness
    def broken(paths, output_path, **kw):
        Path(output_path).write_bytes(b"partial")
        raise RuntimeError("SECRET_REFERENCE_TRANSCRIPT")
    monkeypatch.setattr(core, "merge_segments", broken)
    result = wait(jobs, jobs.submit(LongFormRequest(**payload(pid))).job_id)
    assert result.status == "FAILED" and not list(settings.output_dir.glob("*.wav"))
    assert "SECRET_REFERENCE_TRANSCRIPT" not in caplog.text
