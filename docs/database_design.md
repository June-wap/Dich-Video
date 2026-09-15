# SQLite persistence design

The backend keeps durable metadata in `metadata.sqlite3` under the configured
output directory (or `LOCAL_AI_DATABASE_PATH`). Schema version 1 is created
transactionally and rejected if a newer version is encountered. Every database
operation uses a short-lived connection with foreign keys enabled.

`settings`, `voices`, and `voice_profiles` contain JSON metadata only. Audio,
reference recordings, and per-chunk WAV files remain on the filesystem; their
paths and SHA-256 checksums are recorded in SQLite.

`tts_jobs` stores the public status snapshot plus an immutable execution
snapshot. `tts_chunks` has a `(job_id, chunk_index)` uniqueness constraint,
source offsets, normalized text, input hash, attempts, artifact metadata, and
timestamps. `audio_outputs` has a foreign key to its job and a unique path.

At startup, QUEUED and RUNNING jobs are atomically marked FAILED with
`error_code=INTERRUPTED`; active chunks receive the same terminal error. This
MVP intentionally does not resume generation and assumes one backend process
owns an output directory at a time.
