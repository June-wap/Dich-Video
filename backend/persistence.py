"""Small SQLite repository. Each operation owns a connection and transaction."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid

from backend.errors import ApplicationError, ErrorCode
from backend.errors.handlers import MESSAGES
from backend.schemas.common import ErrorBody
from backend.schemas.long_form import LongFormStatus

SCHEMA_V1 = [
    """CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
    """CREATE TABLE voices (
        id TEXT PRIMARY KEY,
        metadata TEXT NOT NULL
    )""",
    """CREATE TABLE voice_profiles (
        id TEXT PRIMARY KEY,
        metadata TEXT NOT NULL
    )""",
    """CREATE TABLE tts_jobs (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','COMPLETED','FAILED','CANCELLED')),
        snapshot TEXT NOT NULL,
        execution_snapshot TEXT NOT NULL,
        diagnostics TEXT NOT NULL DEFAULT '{}',
        profile_id TEXT REFERENCES voice_profiles(id) ON DELETE SET NULL,
        created_at REAL NOT NULL,
        started_at REAL,
        completed_at REAL,
        error_code TEXT
    )""",
    "CREATE INDEX jobs_history ON tts_jobs(created_at DESC)",
    "CREATE INDEX jobs_status ON tts_jobs(status)",
    "CREATE INDEX jobs_kind ON tts_jobs(kind)",
    """CREATE TABLE tts_chunks (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL REFERENCES tts_jobs(id) ON DELETE CASCADE,
        chunk_index INTEGER NOT NULL CHECK(chunk_index >= 0),
        source_start INTEGER,
        source_end INTEGER,
        normalized_text TEXT NOT NULL,
        input_hash TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('PENDING','GENERATING','COMPLETED','FAILED','CANCELLED')),
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
        artifact_path TEXT,
        artifact_checksum TEXT,
        duration_ms REAL,
        error_code TEXT,
        started_at REAL,
        completed_at REAL,
        UNIQUE(job_id, chunk_index)
    )""",
    "CREATE INDEX chunks_job_idx ON tts_chunks(job_id, chunk_index)",
    """CREATE TABLE audio_outputs (
        id TEXT PRIMARY KEY,
        job_id TEXT NOT NULL REFERENCES tts_jobs(id) ON DELETE CASCADE,
        path TEXT NOT NULL UNIQUE,
        checksum TEXT NOT NULL,
        format TEXT NOT NULL,
        created_at REAL NOT NULL
    )""",
    "CREATE INDEX audio_outputs_job_idx ON audio_outputs(job_id)",
]

MIGRATIONS = [
    (1, SCHEMA_V1),
]

LATEST_SCHEMA_VERSION = 1


def apply_migrations(db, migrations=MIGRATIONS, latest_version=LATEST_SCHEMA_VERSION):
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version > latest_version:
        raise RuntimeError(f"Unsupported database schema version: {version}")
    for target_version, statements in migrations:
        if version < target_version:
            for statement in statements:
                if statement.strip():
                    db.execute(statement)
            db.execute(f"PRAGMA user_version={target_version}")
            version = target_version


def checksum(path):
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        with p.open("rb") as source:
            return hashlib.file_digest(source, "sha256").hexdigest()
    except (OSError, ValueError):
        return None


class Repository:
    def __init__(self, settings):
        self.path = Path(settings.database_path or (Path(settings.output_dir) / "metadata.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("BEGIN IMMEDIATE")
            apply_migrations(db)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, table, key, value):
        if table not in {"settings", "voices", "voice_profiles"}:
            raise ValueError("Unsupported metadata table")
        columns = "key,value" if table == "settings" else "id,metadata"
        key_column, value_column = columns.split(",")
        with self.connect() as db:
            db.execute(
                f"INSERT INTO {table} ({columns}) VALUES (?,?) "
                f"ON CONFLICT({key_column}) DO UPDATE SET {value_column}=excluded.{value_column}",
                (key, json.dumps(value, ensure_ascii=False)),
            )

    def profiles(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT metadata FROM voice_profiles")]

    def get_setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    @contextmanager
    def generation(self, kind, execution, profile_id=None):
        """Track existing synchronous APIs without changing their response contract."""
        snapshot = LongFormStatus(job_id=str(uuid.uuid4()), status="RUNNING")
        self.create_job(snapshot, execution, profile_id, kind)
        self.save_job(snapshot, {})
        try:
            yield snapshot
        except Exception as exc:
            code = exc.code if isinstance(exc, ApplicationError) else ErrorCode.GENERATION_FAILED
            failed = snapshot.model_copy(
                update={"status": "FAILED", "error": ErrorBody(code=code.value, message=MESSAGES[code])}
            )
            self.save_job(failed, {})
            raise

    def complete_generation(self, snapshot, audio_url, paths, diagnostics):
        completed = snapshot.model_copy(
            update={"status": "COMPLETED", "progress_percent": 100, "audio_url": audio_url}
        )
        self.save_job(completed, diagnostics, paths)

    def delete_profile(self, key):
        with self.connect() as db:
            db.execute("DELETE FROM voice_profiles WHERE id=?", (key,))

    def create_job(self, snapshot, execution, profile_id=None, kind="long_form"):
        with self.connect() as db:
            db.execute(
                "INSERT INTO tts_jobs (id,kind,status,snapshot,execution_snapshot,profile_id,created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    snapshot.job_id,
                    kind,
                    snapshot.status,
                    snapshot.model_dump_json(),
                    json.dumps(execution, ensure_ascii=False),
                    profile_id,
                    time.time(),
                ),
            )

    def save_job(self, snapshot, diagnostics, outputs=()):
        with self.connect() as db:
            db.execute(
                "UPDATE tts_jobs SET status=?,snapshot=?,diagnostics=?,error_code=?, "
                "started_at=CASE WHEN ?='RUNNING' THEN COALESCE(started_at,?) ELSE started_at END, "
                "completed_at=CASE WHEN ? IN ('COMPLETED','FAILED','CANCELLED') THEN ? ELSE completed_at END "
                "WHERE id=?",
                (
                    snapshot.status,
                    snapshot.model_dump_json(),
                    json.dumps(diagnostics),
                    snapshot.error.code if snapshot.error else None,
                    snapshot.status,
                    time.time(),
                    snapshot.status,
                    time.time(),
                    snapshot.job_id,
                ),
            )
            for path in outputs:
                path = Path(path)
                if not path.is_file():
                    continue
                csum = checksum(path)
                if not csum:
                    continue
                output_id = f"{snapshot.job_id}:{path.name}"
                db.execute(
                    "INSERT INTO audio_outputs (id, job_id, path, checksum, format, created_at) "
                    "VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(path) DO UPDATE SET "
                    "checksum=excluded.checksum, format=excluded.format, created_at=excluded.created_at",
                    (
                        output_id,
                        snapshot.job_id,
                        str(path.resolve()),
                        csum,
                        path.suffix.lstrip(".") or "unknown",
                        time.time(),
                    ),
                )
            if snapshot.status in {"FAILED", "CANCELLED"}:
                db.execute(
                    "UPDATE tts_chunks SET status=?,error_code=?,completed_at=? "
                    "WHERE job_id=? AND status IN ('PENDING','GENERATING')",
                    (
                        snapshot.status,
                        snapshot.error.code if snapshot.error else None,
                        time.time(),
                        snapshot.job_id,
                    ),
                )

    def recover(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            rows = db.execute("SELECT id,snapshot FROM tts_jobs WHERE status IN ('QUEUED','RUNNING')").fetchall()
            for row in rows:
                snapshot = json.loads(row["snapshot"])
                snapshot.update(
                    status="FAILED",
                    audio_url=None,
                    error={"code": "INTERRUPTED", "message": "Backend restarted before job completion."},
                )
                db.execute(
                    "UPDATE tts_jobs SET status='FAILED',snapshot=?,error_code='INTERRUPTED',completed_at=? WHERE id=?",
                    (json.dumps(snapshot), now, row["id"]),
                )
                db.execute(
                    "UPDATE tts_chunks SET status='FAILED',error_code='INTERRUPTED',completed_at=? "
                    "WHERE job_id=? AND status IN ('PENDING','GENERATING')",
                    (now, row["id"]),
                )

    def history(self, kind="long_form"):
        with self.connect() as db:
            return [
                (json.loads(r["snapshot"]), json.loads(r["diagnostics"]))
                for r in db.execute(
                    "SELECT snapshot,diagnostics FROM tts_jobs WHERE kind=? ORDER BY created_at", (kind,)
                )
            ]

    def get_job(self, job_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT id, kind, status, snapshot, execution_snapshot, diagnostics, profile_id, "
                "created_at, started_at, completed_at, error_code FROM tts_jobs WHERE id=?",
                (job_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_chunks(self, job_id):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM tts_chunks WHERE job_id=? ORDER BY chunk_index ASC", (job_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_audio_outputs(self, job_id):
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM audio_outputs WHERE job_id=? ORDER BY created_at ASC", (job_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def chunk(self, job_id, index, text, status, path=None, source_range=(None, None), error=None):
        artifact = Path(path) if path else None
        with self.connect() as db:
            db.execute(
                "INSERT INTO tts_chunks (id,job_id,chunk_index,normalized_text,input_hash,status,source_start,source_end,attempt_count,started_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(job_id,chunk_index) DO UPDATE SET "
                "status=excluded.status, attempt_count=tts_chunks.attempt_count+CASE WHEN excluded.status='GENERATING' THEN 1 ELSE 0 END, "
                "started_at=COALESCE(tts_chunks.started_at,excluded.started_at)",
                (
                    f"{job_id}:{index}",
                    job_id,
                    index,
                    text,
                    hashlib.sha256(text.encode()).hexdigest(),
                    status,
                    *source_range,
                    int(status == "GENERATING"),
                    time.time() if status == "GENERATING" else None,
                ),
            )
            if status in {"COMPLETED", "FAILED"}:
                duration = None
                if artifact and artifact.is_file():
                    try:
                        import soundfile as sf

                        duration = sf.info(artifact).duration * 1000
                    except Exception:
                        duration = None
                db.execute(
                    "UPDATE tts_chunks SET artifact_path=?,artifact_checksum=?,duration_ms=?,error_code=?,completed_at=? WHERE job_id=? AND chunk_index=?",
                    (
                        str(artifact.resolve()) if artifact and artifact.is_file() else (str(artifact) if artifact else None),
                        checksum(artifact) if artifact else None,
                        duration,
                        error,
                        time.time(),
                        job_id,
                        index,
                    ),
                )
