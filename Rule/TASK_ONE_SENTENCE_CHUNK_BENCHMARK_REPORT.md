# Task — Benchmark Three One-Sentence Long-Form Chunk Configurations

**Status: BLOCKED for GPU execution / EXECUTED for the mandatory pre-GPU check and everything else achievable without a GPU.**

`device_bash` is still unavailable this turn — re-tested twice (once before starting, once right before delivery), now failing with a slightly different message than earlier rounds (`"Workspace unavailable. The isolated Linux environment on this device failed to start."` instead of the Plan9-mount error), but the practical effect is the same: no shell on your machine, no GPU, no model. `device_stage_files`/`device_commit_files` still work, which is how everything below was done for real.

**I did not run any of the 15 (or, as it turns out, fewer) generations.** What follows is the one part of this task that is explicitly required to happen *before* touching the GPU — and it changes the shape of the whole benchmark.

## The pre-GPU check — actually executed, real result

The task itself anticipated this might happen and required proving it before spending any GPU time: **A, B, and C produce byte-identical chunk lists on this corpus.**

I ran `core.long_text.build_chunks()` — the real, unmodified production chunker — against the real `long_audio_stability_test_vi.txt` (5,733 characters) for all three nominal configs:

| Config | target_chars | max_chars | max_sentences | chunk_count | chars min/avg/max | fingerprint (SHA-256 of ordered chunk text) |
|---|---|---|---|---|---|---|
| A | 100 | 160 | 1 | 113 | 6 / 49.4 / 158 | `f3eae54e312fb178...` |
| B | 120 | 160 | 1 | 113 | 6 / 49.4 / 158 | `f3eae54e312fb178...` (identical) |
| C | 140 | 160 | 1 | 113 | 6 / 49.4 / 158 | `f3eae54e312fb178...` (identical) |

All three fingerprints match exactly. **Reason, once you look at how `build_chunks()` actually works:** `target_chars` only matters as a *soft threshold for deciding whether to add a second sentence to the current chunk*. When `max_sentences_per_chunk=1`, a chunk always closes after exactly one sentence — there is never an opportunity to consult `target_chars` at all. So on any corpus, A/B/C as specified are mathematically the same configuration whenever `max_sentences_per_chunk=1` is held fixed; this isn't specific to this corpus's wording.

Text integrity (`"".join(text.split()) == "".join(chunk texts)`) passed for all three (as expected, since they're identical chunk lists). Five sentences in the corpus exceed `max_chars=160` and get hard-split identically in all three configs — most notably Part Seven's deliberately-long single sentence (564 characters) and four others in the 161–276 char range (paragraph indices 1, 6, 10, 30, 34). These forced splits happen regardless of which of A/B/C you pick, since they're driven by `max_chars`, not `target_chars`.

**Consequence, per the task's own instruction:** this needed 1 effective GPU configuration × 5 runs = **5 generations, not 15**. I did not attempt the other 10.

Full machine-readable result (all 113 chunks' exact text for each config, not just the summary above) is delivered as `precheck_chunk_identity_result.json`.

## What I built to run the actual 5 generations

`external/OmniVoice/benchmark_one_sentence_chunk_configs.py`, committed and byte-verified. It reuses the existing infrastructure rather than duplicating it — same `TTSManager` + `OmniVoiceProvider` direct-call pattern already proven in `benchmark_production_long_form.py` (Task 3.5) and `benchmark_long_form_diagnostic.py` (Task 4.1), same `REPO_ROOT`/`PROTOTYPE_DIR` sys.path convention. I did not build a simplified/fake synthesis path.

One thing worth flagging directly: I could not use the real HTTP API (`backend/api/long_form.py`) for this benchmark even though I used it for the previous round's stability test. `LongFormRequest` has no field for a custom chunk configuration — `chunk_config` is hardcoded to production's `LONG_FORM_CHUNK_CONFIG` inside `long_form_service.py` and isn't a request parameter. Since this task's entire point is to vary chunking, going through HTTP would silently test 240/320/3 three times regardless of what I asked for. So this script calls `TTSManager.synthesize_long_text(chunk_config=...)` directly instead, same as it was already doing for the Task 4.1 diagnostic.

**Voice profile** — not invented. The script reads `reference_path` and `transcript` straight from the real `prototype/outputs/api/metadata.sqlite3` `voice_profiles` table (same DB production reads), then calls `provider.create_voice_profile(reference_path, transcript)` — the exact same lazy-restore call `VoiceProfileService.restore_profile()` makes for an existing profile. Before use it re-verifies the reference file's SHA-256 against the DB's stored checksum, mirroring that same safety check. Only one profile exists: `585337d3-1122-48b1-bd55-bbf31ff14374` ("Thanh Huyền") — confirmed again this round, no ambiguity.

**Control variables**: `num_step=24` is passed explicitly on every `synthesize_cloned()` call rather than relied on as a default (matches `OmniVoiceProvider.DEFAULT_CLONE_NUM_STEP`, and matches the value already confirmed wired into production for the cloning path). `max_retries=0`, `speed=1.0`, same model/provider/merge/DSP — nothing in the generation path changed.

**Artifacts** — `keep_temp=True` preserves every per-chunk WAV (a legitimate `TTSManager.synthesize_long_text` parameter; no monkeypatching needed this time since I call `TTSManager` directly rather than through the production HTTP service, unlike the previous round). Both WAV and MP3 are validated per run.

**Since A/B/C are proven identical here**, the script runs the representative config (A) 5 times, then — per the task's explicit "do not waste GPU time" instruction — populates `B_120_160_1/` and `C_140_160_1/` with **verified byte-identical copies** of A's 5 runs, each with a `MIRROR_NOTICE.txt` explaining exactly why (never silently, never presented as if it were a separate generation).

**Blinded human review**: since only 5 real, independent recordings exist (not 15), the default manifest blinds those 5 — not 15 slots padded with 3 identical copies of each. I made this call deliberately: presenting the same audio three times under different blind IDs would add no diagnostic value and risks a reviewer half-recognizing a repeat, which quietly breaks the blinding the manifest exists to protect. `--full-blind-15` is available if you'd rather have the literal 15-slot version anyway (mapping still correctly records which nominal configs each sample represents). I tested both paths for real (see below) — both produce the correct sample count.

**Historical 240/320/3 reference**: included in the JSON output under a key that says in its own name not to treat it as a direct comparison, with the caveat spelled out (different harness, different corpus, never had a listening check) — exactly as instructed.

## What I actually executed and verified (real, not claimed)

I have no GPU here, so the inference itself is untested by me. Everything else in the script, I ran for real against your actual files:

- **Phase-0 pre-check**, embedded in the script itself, run against the real corpus — reproduced the exact same result as the table above (113 chunks, identical fingerprints, `oversized_sentences=5` for all three).
- **`load_profile_from_db()`** against your real, staged `metadata.sqlite3` — correctly returned the "Thanh Huyền" profile with all required fields; separately confirmed it raises a clear error when a `profile_id` doesn't exist or a table is empty.
- **`verify_reference_checksum()`** against your real staged reference MP3 (`585337d3-....mp3`, 203,327 bytes) — passed against the real DB checksum, and correctly raised `SystemExit` when I deliberately fed it a wrong checksum.
- **`mirror_into_label_dir()`** — built 5 real WAV files (via `ffmpeg`) under a fake `A_100_160_1/run_01..05/`, mirrored them into `B_120_160_1/` and `C_140_160_1/`, and confirmed byte-for-byte identity (SHA-256) between originals and mirrors, plus confirmed `MIRROR_NOTICE.txt` is present only in the mirrored directories, not the original.
- **`build_blind_manifest()`** — ran against those same synthetic runs: confirmed exactly 5 blinded samples by default (not 15), confirmed `--full-blind-15` produces 15, confirmed the manifest's filenames and body never leak `A_100_160_1`/`B_120_160_1`/`C_140_160_1` anywhere a reviewer would see them, confirmed every sample gets all 12 blank review fields, and confirmed the separate mapping file correctly records which nominal configs (A/B/C) each blinded sample stands in for.

Syntax-checked with `ast.parse` as well. What I could not do: submit anything to `TTSManager`/`OmniVoiceProvider`/CUDA — that's the one part that needs your machine.

## Files delivered

- `external/OmniVoice/benchmark_one_sentence_chunk_configs.py` — committed, byte-verified.
- `precheck_chunk_identity_result.json` — the real Phase-0 output (all 113 chunks' exact text for A/B/C), delivered alongside this report for your own inspection before running anything.

No `backend/` or `prototype/` production file was read for editing and none was changed.

## How to run it

```powershell
$env:PYTHONPATH='prototype'
& .\external\OmniVoice\.venv312\Scripts\python.exe `
    external\OmniVoice\benchmark_one_sentence_chunk_configs.py
```

It will print the Phase-0 result again (should match the table above exactly — if it doesn't, something about the corpus or `core/long_text.py` has changed since I wrote this and you should stop and tell me), then run 5 generations of the single representative config, then mirror into B/C, then build the blind manifest. Defaults: `--runs 5`, corpus/DB paths at their real repo locations, artifacts under `external/OmniVoice/artifacts/`.

## Exact fields requested

- **Status**: BLOCKED (GPU execution) — the script itself will report `REVIEW_READY` once you run it and it completes, or `BLOCKED` with a clear message if CUDA isn't visible when you run it (it refuses to silently fall back to CPU and call the result comparable).
- **Exact commands executed**: none against the GPU. Locally: `ast.parse` syntax check; the Phase-0 pre-check function; `load_profile_from_db`/`verify_reference_checksum` against your real staged DB and reference file; `mirror_into_label_dir`/`build_blind_manifest` against synthetic ffmpeg-generated WAVs. All shown above.
- **Exact effective chunk configurations**: one — `target_chars=100/120/140` (all three, since they produce identical output), `max_chars=160`, `max_sentences_per_chunk=1`, on this corpus.
- **Whether A/B/C produced different chunks**: **No — proven identical**, with a code-level explanation (not just an empirical coincidence): `max_sentences_per_chunk=1` makes `target_chars` unreachable.
- **Number of GPU generations actually required**: 5 (1 effective config × 5 runs), not 15.
- **Technical result table**: not available — no run happened yet.
- **Artifact directory**: `external/OmniVoice/artifacts/` (created by the script on first run).
- **Blinded human-review manifest path**: `external/OmniVoice/artifacts/REVIEW_MANIFEST.md`, generated at the end of a run.
- **Blind-ID mapping path**: `external/OmniVoice/artifacts/BLIND_MAPPING.json` — don't open this until the manifest is fully filled in.
- **Limitations**: no GPU here this turn (again); the 5-run number is smaller than the 15 the task specified only because the mandatory pre-check the task itself required proved 10 of those 15 would have been wasted GPU time reproducing byte-identical audio.
- **Confirmation production code was not changed**: confirmed — nothing under `backend/` or `prototype/` was modified. This script lives entirely under `external/OmniVoice/` and only *reads* `core.long_text`/`core.tts_manager`/`providers.omnivoice` and the real database.

## Once you run it

Send me `artifacts/BENCHMARK_SUMMARY.json` and your filled-in `REVIEW_MANIFEST.md` and I'll fold the real generation timing/RTF/VRAM numbers and your human-verified content-stability verdicts into a proper decision report — including whether this configuration (target≈100–140/max=160/1 sentence) actually eliminates the swallowed/missing/repeated-word defects on real audio, and what it costs in generation time relative to the current 240/320/3 production default.
