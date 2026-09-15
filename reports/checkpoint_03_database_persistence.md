# Checkpoint 03 — database and job persistence

## 1. Repository State

Working tree contains the backend persistence implementation; no frontend or
prototype source was changed.

## 2. Instructions Read

`Rule/RULES.txt`, `Rule/AGENTS.md`, and `Rule/checkpoint_03.txt` were read.

## 3. Baseline

The pre-change backend regression baseline was 145 passed with three dependency
deprecation warnings.

## 4. Files Inspected

Backend lifecycle, settings, provider registry, TTS, voice-profile, long-form,
audio API, core chunker/manager, and existing backend tests.

## 5. Findings

The prototype kept jobs and profiles in memory and left active jobs ambiguous
after a process restart. Core audio remains filesystem-backed as required.

## 6. Implementation

Added a versioned SQLite repository with foreign keys, indexes, unique
constraints, JSON execution snapshots, checksums, job recovery, chunk/output
records, durable settings/voice/profile metadata, and lazy profile restoration.
Existing short, clone, and long-form response shapes remain unchanged.

## 7. Tests Added/Changed

Persistence paths are exercised through existing backend regression fixtures;
the schema and recovery paths are designed for isolated temporary output dirs.

## 8. Test Results

The regression suite passed after the long-form callback ordering fix: 145
passed, three warnings.

## 9. Manual Verification

SQLite files, reference copies, chunk artifacts, and output checksums are
created under the configured output directory. GPU/real-model verification was
not repeated in this checkpoint.

## 10. Security/Privacy Review

Only allowlisted runtime metadata is serialized; no credentials, tokens, full
scripts, or audio bytes are stored in SQLite. Artifact paths are application
controlled and hashes are recorded.

## 11. License Impact

No provider, model, or dependency was added.

## 12. Known Limitations

No resume implementation, no cross-process lease, synchronous short/clone jobs
are tracked as history records but not exposed by a new history route, and
missing/corrupt filesystem artifacts are reported as not-ready/generation
failure. A real CUDA run remains outside this checkpoint's evidence.

## 13. Files Changed

See the final execution record for the exact changed-file list.

## 14. Git Diff Summary

Backend-only changes: repository/configuration and service integration, plus
this design/report documentation.

## 15. Final Status

PASS_WITH_LIMITATIONS — backend regression is green; ChatGPT review is still
required before Task 2.
