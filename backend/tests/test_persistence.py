import io
import json
from pathlib import Path
import sqlite3
import time
import uuid

import numpy as np
import pytest
import soundfile as sf

from backend.config import Settings
from backend.errors import ApplicationError, ErrorCode
from backend.persistence import (
    LATEST_SCHEMA_VERSION,
    MIGRATIONS,
    Repository,
    apply_migrations,
    checksum,
)
from backend.schemas.long_form import LongFormRequest, LongFormStatus
from backend.services.long_form_service import LongFormTTSService
from backend.services.provider_service import ProviderService
from backend.services.tts_service import TTSService
from backend.services.voice_profile_service import VoiceProfileService
from backend.tests.provider_fakes import FakeCloneProvider, registry


def make_test_wav(path: Path, duration_seconds: float = 1.0, sample_rate: int = 24000) -> Path:
    t = np.linspace(0, duration_seconds, int(sample_rate * duration_seconds), endpoint=False)
    samples = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), samples, sample_rate, format="WAV")
    return path


def test_schema_and_tables_creation(tmp_path):
    settings = Settings(database_path=tmp_path / "test.sqlite3", output_dir=tmp_path)
    repo = Repository(settings)

    with repo.connect() as db:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        assert version == 1

        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        assert tables == {"settings", "voices", "voice_profiles", "tts_jobs", "tts_chunks", "audio_outputs"}

        # Verify tts_chunks columns
        columns = {row[1] for row in db.execute("PRAGMA table_info(tts_chunks)").fetchall()}
        required_chunk_columns = {
            "id",
            "job_id",
            "chunk_index",
            "source_start",
            "source_end",
            "normalized_text",
            "input_hash",
            "status",
            "attempt_count",
            "artifact_path",
            "artifact_checksum",
            "duration_ms",
            "error_code",
            "started_at",
            "completed_at",
        }
        assert required_chunk_columns.issubset(columns)


def test_migration_upgrade_and_version_control(tmp_path):
    db_path = tmp_path / "mig.sqlite3"
    conn = sqlite3.connect(db_path)
    try:
        # Start at v0
        v = conn.execute("PRAGMA user_version").fetchone()[0]
        assert v == 0

        # Apply migrations
        apply_migrations(conn)
        v = conn.execute("PRAGMA user_version").fetchone()[0]
        assert v == LATEST_SCHEMA_VERSION

        # Calling again is idempotent
        apply_migrations(conn)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == LATEST_SCHEMA_VERSION

        # Test incremental migration to v2
        mock_migrations = MIGRATIONS + [(2, ["CREATE TABLE extra_meta (k TEXT PRIMARY KEY, v TEXT);"])]
        apply_migrations(conn, migrations=mock_migrations, latest_version=2)
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2

        extra_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='extra_meta'"
            ).fetchall()
        }
        assert "extra_meta" in extra_tables

        # Future unsupported version raises RuntimeError
        conn.execute("PRAGMA user_version=999")
        with pytest.raises(RuntimeError, match="Unsupported database schema version"):
            apply_migrations(conn)
    finally:
        conn.close()


def test_foreign_key_constraints(tmp_path):
    settings = Settings(database_path=tmp_path / "fk.sqlite3", output_dir=tmp_path)
    repo = Repository(settings)

    with repo.connect() as db:
        # 1. Chunk with nonexistent job fails
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO tts_chunks (id, job_id, chunk_index, normalized_text, input_hash, status) "
                "VALUES ('c1', 'nonexistent-job', 0, 'text', 'hash', 'PENDING')"
            )

        # 2. Audio output with nonexistent job fails
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO audio_outputs (id, job_id, path, checksum, format, created_at) "
                "VALUES ('a1', 'nonexistent-job', '/path/out.wav', 'csum', 'wav', 123.0)"
            )

    # 3. Create profile and job referencing profile
    repo.put("voice_profiles", "prof-1", {"name": "Test Profile"})
    snapshot = LongFormStatus(job_id="job-1", status="COMPLETED")
    repo.create_job(snapshot, {"model": "m1"}, profile_id="prof-1")

    # Add chunk and audio output for job-1
    with repo.connect() as db:
        db.execute(
            "INSERT INTO tts_chunks (id, job_id, chunk_index, normalized_text, input_hash, status) "
            "VALUES ('j1:0', 'job-1', 0, 'text', 'hash', 'COMPLETED')"
        )
        db.execute(
            "INSERT INTO audio_outputs (id, job_id, path, checksum, format, created_at) "
            "VALUES ('j1:out', 'job-1', '/out/1.wav', 'hash', 'wav', 100.0)"
        )

    # Deleting profile sets job profile_id to NULL
    repo.delete_profile("prof-1")
    with repo.connect() as db:
        job_row = db.execute("SELECT profile_id FROM tts_jobs WHERE id='job-1'").fetchone()
        assert job_row[0] is None

        # Deleting job cascades to chunks and audio_outputs
        db.execute("DELETE FROM tts_jobs WHERE id='job-1'")
        assert db.execute("SELECT COUNT(*) FROM tts_chunks WHERE job_id='job-1'").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM audio_outputs WHERE job_id='job-1'").fetchone()[0] == 0


def test_unique_constraints(tmp_path):
    settings = Settings(database_path=tmp_path / "uniq.sqlite3", output_dir=tmp_path)
    repo = Repository(settings)

    snapshot = LongFormStatus(job_id="job-u", status="RUNNING")
    repo.create_job(snapshot, {})

    with repo.connect() as db:
        # Unique (job_id, chunk_index)
        db.execute(
            "INSERT INTO tts_chunks (id, job_id, chunk_index, normalized_text, input_hash, status) "
            "VALUES ('c1', 'job-u', 0, 'text1', 'h1', 'PENDING')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO tts_chunks (id, job_id, chunk_index, normalized_text, input_hash, status) "
                "VALUES ('c2', 'job-u', 0, 'text2', 'h2', 'PENDING')"
            )

        # Unique path in audio_outputs
        db.execute(
            "INSERT INTO audio_outputs (id, job_id, path, checksum, format, created_at) "
            "VALUES ('a1', 'job-u', '/unique/path.wav', 'csum1', 'wav', 10.0)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO audio_outputs (id, job_id, path, checksum, format, created_at) "
                "VALUES ('a2', 'job-u', '/unique/path.wav', 'csum2', 'wav', 20.0)"
            )


def test_settings_and_voices_survive_reconnect(tmp_path):
    db_file = tmp_path / "persist.sqlite3"
    settings = Settings(database_path=db_file, output_dir=tmp_path)

    repo1 = Repository(settings)
    repo1.put("settings", "theme", {"dark_mode": True})
    repo1.put("voices", "v-1", {"id": "v-1", "name": "Giọng chuẩn"})

    # Reconnect
    repo2 = Repository(settings)
    assert repo2.get_setting("theme") == {"dark_mode": True}
    with repo2.connect() as db:
        voice = json.loads(db.execute("SELECT metadata FROM voices WHERE id='v-1'").fetchone()[0])
        assert voice["name"] == "Giọng chuẩn"


def test_voice_profiles_survive_restart(tmp_path):
    out_dir = tmp_path / "audio_out"
    db_file = tmp_path / "voice.sqlite3"
    settings = Settings(output_dir=out_dir, database_path=db_file)

    provider = FakeCloneProvider()
    providers = ProviderService()
    providers.register(provider, device="cuda:0", available=True)
    providers.select_primary("omnivoice")

    # 1. Create profile
    vps1 = VoiceProfileService(settings, providers)
    audio = io.BytesIO()
    sf.write(audio, np.ones(72000) * 0.1, 24000, format="WAV")
    created = vps1.create_profile(audio.getvalue(), "sample.wav", "Câu mẫu chuẩn.", "Giọng mẫu 1")
    pid = created.data.profile_id
    assert created.ok is True

    # 2. Restart VoiceProfileService with same DB & filesystem
    provider2 = FakeCloneProvider()
    providers2 = ProviderService()
    providers2.register(provider2, device="cuda:0", available=True)
    providers2.select_primary("omnivoice")

    vps2 = VoiceProfileService(settings, providers2)
    fetched = vps2.get_profile(pid)
    assert fetched.ok is True
    assert fetched.data.name == "Giọng mẫu 1"
    assert fetched.data.reference.duration_seconds == 3.0

    # 3. Test synthesis using restored profile
    req = FakeCloneProvider()
    from backend.schemas.voices import CloneTestRequest

    synth_resp = vps2.synthesize_clone(
        pid, CloneTestRequest(text="Xin chào sau restart.", language="vi", speed=1.0, format="wav")
    )
    assert synth_resp.ok is True
    assert synth_resp.data.profile_id == pid


def test_interrupted_job_recovery(tmp_path):
    settings = Settings(database_path=tmp_path / "recover.sqlite3", output_dir=tmp_path)
    repo = Repository(settings)

    # Simulate a job that was RUNNING when process crashed
    job_id = "interrupted-job-123"
    snapshot = LongFormStatus(job_id=job_id, status="RUNNING", progress_percent=45.0)
    repo.create_job(snapshot, {"text": "Dài..."}, kind="long_form")
    repo.save_job(snapshot, {})

    # Create chunks: chunk 0 completed, chunk 1 generating, chunk 2 pending
    wav_path = make_test_wav(tmp_path / "chunk_0.wav")
    repo.chunk(job_id, 0, "Đoạn 0", "COMPLETED", path=wav_path)
    repo.chunk(job_id, 1, "Đoạn 1", "GENERATING")
    repo.chunk(job_id, 2, "Đoạn 2", "PENDING")

    # Verify initial chunk states
    chunks_before = repo.get_chunks(job_id)
    assert chunks_before[0]["status"] == "COMPLETED"
    assert chunks_before[1]["status"] == "GENERATING"
    assert chunks_before[2]["status"] == "PENDING"

    # Simulate restart recovery
    repo.recover()

    # Job must now be FAILED with error_code INTERRUPTED
    job = repo.get_job(job_id)
    assert job["status"] == "FAILED"
    assert job["error_code"] == "INTERRUPTED"
    assert job["completed_at"] is not None

    snapshot_after = json.loads(job["snapshot"])
    assert snapshot_after["status"] == "FAILED"
    assert snapshot_after["error"]["code"] == "INTERRUPTED"
    assert snapshot_after["audio_url"] is None

    # Check chunks after recovery: completed chunk remains COMPLETED!
    chunks_after = repo.get_chunks(job_id)
    assert chunks_after[0]["status"] == "COMPLETED"
    assert chunks_after[0]["artifact_path"] is not None

    # In-progress chunks became FAILED with INTERRUPTED
    assert chunks_after[1]["status"] == "FAILED"
    assert chunks_after[1]["error_code"] == "INTERRUPTED"
    assert chunks_after[1]["completed_at"] is not None

    assert chunks_after[2]["status"] == "FAILED"
    assert chunks_after[2]["error_code"] == "INTERRUPTED"
    assert chunks_after[2]["completed_at"] is not None


def test_missing_and_corrupt_artifact_safety(tmp_path):
    # None or non-existent paths should return None rather than raising exceptions
    assert checksum(None) is None
    assert checksum(tmp_path / "nonexistent.wav") is None

    # Corrupt file
    corrupt = tmp_path / "corrupt.bin"
    corrupt.write_bytes(b"corrupt non audio data")
    assert checksum(corrupt) is not None  # SHA256 of arbitrary binary bytes works

    # Chunk registration with nonexistent artifact does not crash
    settings = Settings(database_path=tmp_path / "safety.sqlite3", output_dir=tmp_path)
    repo = Repository(settings)
    job_id = "safe-job"
    repo.create_job(LongFormStatus(job_id=job_id, status="RUNNING"), {})
    repo.chunk(job_id, 0, "Chunk text", "COMPLETED", path=tmp_path / "missing.wav")
    chunk_row = repo.get_chunks(job_id)[0]
    assert chunk_row["status"] == "COMPLETED"
    assert chunk_row["duration_ms"] is None


def test_audio_outputs_persistence(tmp_path):
    settings = Settings(database_path=tmp_path / "out.sqlite3", output_dir=tmp_path)
    repo = Repository(settings)

    job_id = "output-job-1"
    snapshot = LongFormStatus(job_id=job_id, status="RUNNING")
    repo.create_job(snapshot, {})

    wav_file = make_test_wav(tmp_path / "final.wav")
    mp3_file = tmp_path / "final.mp3"
    mp3_file.write_bytes(b"fake mp3 bytes")

    snapshot_completed = snapshot.model_copy(update={"status": "COMPLETED", "progress_percent": 100})
    repo.save_job(snapshot_completed, {"metrics": 1}, outputs=[wav_file, mp3_file])

    outputs = repo.get_audio_outputs(job_id)
    assert len(outputs) == 2
    formats = {o["format"] for o in outputs}
    assert formats == {"wav", "mp3"}
    assert all(o["checksum"] for o in outputs)

    # Calling save_job again with the same files is safe (no unique violation crash)
    repo.save_job(snapshot_completed, {"metrics": 1}, outputs=[wav_file, mp3_file])
    outputs2 = repo.get_audio_outputs(job_id)
    assert len(outputs2) == 2


def test_job_history_and_status_survives_service_restart(tmp_path):
    settings = Settings(output_dir=tmp_path / "audio", database_path=tmp_path / "jobs.sqlite3")
    provider = FakeCloneProvider()
    providers = registry(provider)

    vps = VoiceProfileService(settings, providers)
    audio = io.BytesIO()
    sf.write(audio, np.ones(72000) * 0.1, 24000, format="WAV")
    profile_id = vps.create_profile(audio.getvalue(), "ref.wav", "Văn bản mẫu.").data.profile_id

    # 1. Run and complete a long-form job
    service1 = LongFormTTSService(settings, providers, vps)
    try:
        job = service1.submit(
            LongFormRequest(text="Câu một ngắn gọn. Câu hai tiếp theo.", profile_id=profile_id)
        )
        job_id = job.job_id
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            st = service1.status(job_id)
            if st.status in {"COMPLETED", "FAILED"}:
                break
            time.sleep(0.01)
        assert service1.status(job_id).status == "COMPLETED"
    finally:
        service1.close()

    # 2. Re-create service (simulating backend restart)
    service2 = LongFormTTSService(settings, providers, vps)
    try:
        # Job must be present in history
        history = service2._db.history("long_form")
        assert any(h[0]["job_id"] == job_id for h in history)

        # Status and progress intact
        st2 = service2.status(job_id)
        assert st2.status == "COMPLETED"
        assert st2.progress_percent == 100
        assert st2.audio_url is not None

        # Diagnostics preserved
        diag = service2.diagnostics(job_id)
        assert "chunk_count" in diag
    finally:
        service2.close()


def test_short_tts_job_persistence(tmp_path):
    settings = Settings(output_dir=tmp_path / "short", database_path=tmp_path / "short.sqlite3")
    provider = FakeCloneProvider()
    providers = registry(provider)
    tts_service = TTSService(settings, providers)

    from backend.schemas.tts import TTSRequest

    req = TTSRequest(text="Kiểm tra short TTS persistence.", language="vi")
    resp = tts_service.synthesize(req)
    assert resp.ok is True
    gen_id = resp.data.generation_id

    # Check job record in database
    job = tts_service._db.get_job(gen_id)
    assert job is not None
    assert job["kind"] == "short"
    assert job["status"] == "COMPLETED"
    assert json.loads(job["snapshot"])["status"] == "COMPLETED"
    assert json.loads(job["execution_snapshot"])["audio"]["sample_rate"] == 24000

    # Check audio output record in database
    outputs = tts_service._db.get_audio_outputs(gen_id)
    assert len(outputs) == 1
    assert outputs[0]["format"] == "wav"
