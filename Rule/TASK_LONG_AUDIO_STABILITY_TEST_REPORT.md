# Task — Run Automated Long-Audio Stability Test

**Status: BLOCKED for actual execution / EXECUTED for everything achievable without it.**

`device_bash` failed again this turn with the identical error every prior round in this session has hit:

```
sandbox-helper: no Plan9 drive shares mounted under /mnt/.virtiofs-root/shared
```

(the Windows Sept-8-update Plan9-drive issue). I re-tested it at the start of this task specifically to confirm before writing this report — still broken. `device_list_dir` / `device_stage_files` / `device_commit_files` still work, which is the only reason the rest of this task could be done for real rather than guessed at.

**I did not run the 5 jobs.** I have no GPU here and no working shell on your machine this turn. What follows is everything I could do honestly without either: a real voice profile identified from your actual database, a complete runner script built against your actual production API (not a bypass harness), and real, executed unit tests of every piece of that script that doesn't require FastAPI/PyTorch/a GPU.

## Voice profile used

Queried directly from your real `prototype/outputs/api/metadata.sqlite3` (staged and read, not assumed). There is exactly **one** profile in the database — no ambiguity to report:

| field | value |
|---|---|
| profile_id | `585337d3-1122-48b1-bd55-bbf31ff14374` |
| name | Thanh Huyền |
| provider | omnivoice |
| reference duration | 12.853 s |
| sample rate / channels | 44100 / 1 |
| use_count so far | 2 |
| active_jobs | 0 |

The script defaults to this profile ID; `--profile-id` overrides it if you've added others since.

## What I inspected first (per the task's "before running" instructions)

Before writing anything I read, for real, the actual production surface rather than reusing the Task 3.5/4.1 bypass-harness style benchmarks:

- `backend/api/long_form.py` — `POST /tts/long-form` (submit, 202), `GET /tts/long-form/{job_id}` (poll), `DELETE .../{job_id}` (cancel).
- `backend/schemas/long_form.py` — `LongFormRequest` (`text`, `language`, `profile_id`, `speed` must equal `1.0`, `format` wav/mp3) and `LongFormStatus` (`job_id`, `status`, `progress_percent`, `audio_url`, `error`).
- `backend/main.py` — `create_app()` factory; confirmed the CORS/host-allowlist middleware rejects any hostname not in `{"localhost","127.0.0.1","::1"}`, which matters for how the script has to construct its test client (below).
- `backend/services/long_form_service.py` — confirmed `LONG_FORM_CHUNK_CONFIG = ChunkingConfig(target_chars=240, max_chars=320, max_sentences_per_chunk=3)` is untouched, and that `_run()` calls `manager.synthesize_long_text(..., max_retries=0, ...)` without `keep_temp=True` — i.e. **production always deletes per-chunk WAVs** after a successful merge (`prototype/core/tts_manager.py`, `if not keep_temp: shutil.rmtree(job_dir, ...)`).
- `prototype/core/tts_manager.py` — confirmed `job_dir = self.temp_dir / f"long_{uuid.uuid4().hex}"`, chunk files are named `chunk_0000.wav`, `chunk_0001.wav`, ... inside it, and the per-chunk text is available inside `synthesize_long_text()`'s internal `chunks` list but is **not** re-exposed through `LongFormTTSService.diagnostics()` (which only carries `chunk_count`, `completed_chunks`, `elapsed_seconds`, and a few other scalars) or through the HTTP status schema.

I reused this existing infrastructure rather than duplicating it: the script imports `LONG_FORM_CHUNK_CONFIG` and `build_chunks`/`core.long_text` by reference (same objects production uses, not re-typed literals), and drives the real `backend.main.create_app()` FastAPI app through `fastapi.testclient.TestClient` — the same production route → `LongFormTTSService` → `TTSManager` → `OmniVoiceProvider` call chain a real running server would use, with real job IDs, without needing you to separately start `uvicorn` first.

## Two things worth flagging before you run it

**1. Per-chunk WAVs conflict with "don't modify production code."** Production's own `keep_temp=False` default means chunk WAVs are deleted immediately after merge. Preserving them (which the task requires) without editing any production file only works by intercepting that deletion from outside — so the script monkeypatches `shutil.rmtree` **in its own process only**, and only for directories matching TTSManager's own internal naming pattern (`long_<32 hex chars>`), copying `chunk_*.wav` out immediately before letting the real, unmodified `shutil.rmtree` run. No production file is touched. This is disclosed at the top of the script itself and I tested the interception for real (see below) — but it's the one deliberately clever piece of an otherwise straight-line script, and it's easy to rip out if you'd rather accept "no per-chunk WAVs, final audio only" for a given run.

**2. Chunk-text reconstruction is verified by re-derivation, not by capturing the live result.** The HTTP/diagnostics surface never exposes per-chunk text, so the script independently recomputes `build_chunks(corpus_text, LONG_FORM_CHUNK_CONFIG)` itself — the exact same deterministic function and exact same config object production uses internally — and checks that reassembling it reproduces the normalized corpus exactly. It also cross-checks the recomputed chunk count against `diagnostics()["chunk_count"]` and against however many `chunk_*.wav` files actually got captured, and flags a warning if any of the three disagree. This is an honest, documented substitute for something the API doesn't expose — not a fudge — and it mirrors the same integrity check `tts_manager.py` already runs internally (so if a run technically COMPLETED rather than failing with `CHUNKING_FAILED`/`TEXT_INTEGRITY_FAILED`, production's own check already agreed).

## What I actually executed and verified (real, not claimed)

I can't run FastAPI/PyTorch/a GPU in this sandbox, so I could not exercise the HTTP/inference path itself. I could, and did, run every piece of the script that doesn't depend on those, with the real production values wired in:

- **Path resolution**: simulated the real deployed directory layout (`external/OmniVoice/run_long_audio_stability_test.py` two levels under repo root) and confirmed the script's `REPO_ROOT`/`PROTOTYPE_DIR` computation resolves to the correct real paths, matching the same convention `benchmark_production_long_form.py` and `trace_chunking.py` already use in this repo.
- **The `shutil.rmtree` capture mechanism**: created a real temp directory named exactly like a production job workspace (`long_<uuid4().hex>`) with three real `chunk_0000.wav`/`chunk_0001.wav`/`chunk_0002.wav` files in it, ran it through the actual `ChunkCapture` class, and confirmed all three files were copied out *before* the directory was actually deleted, and that an unrelated directory name is correctly **not** captured (regex guard tested against a real job-shaped name and two deliberately-similar-but-wrong names).
- **WAV duration measurement**: generated a real 2.5-second WAV with `ffmpeg` and confirmed `wav_duration_seconds()` reads exactly `2.5` from it — this is what RTF gets computed from.
- **Manifest generation**: ran `write_manifest()` against two synthetic run records (one COMPLETED, one FAILED) and confirmed it produces per-run sections with every required blank human-review field (PASS/FAIL, missing speech, repeated speech, swallowed/cut words, bad boundary/pause, voice/prosody issue, timestamp, notes) and correctly surfaces a FAILED run's status rather than hiding it.
- **JSON serialization**: confirmed `RunResult` round-trips through `dataclasses.asdict()` → `json.dumps()` cleanly, which is what the per-run `run_metadata.json`/`SUMMARY.json` files depend on.

Syntax-checked the full file with `ast.parse` as well. What I could **not** do: submit a real job, generate real audio, or observe a real `chunk_count`/RTF/timing number — those need your GPU.

## Files delivered

Committed to `D:\Tool Dich Cho Khach\external\OmniVoice\run_long_audio_stability_test.py`, byte-verified via fresh stage-back + `cmp` (identical). No existing production file was changed.

## How to run it

Same venv/PYTHONPATH convention as every other benchmark script already in `external/OmniVoice/`:

```powershell
$env:PYTHONPATH='prototype'
& .\external\OmniVoice\.venv312\Scripts\python.exe `
    external\OmniVoice\run_long_audio_stability_test.py
```

Defaults: 5 runs, the "Thanh Huyền" profile above, `--format wav` (lossless, so you're never mistaking an MP3 artifact for a model defect while reviewing), corpus at `long_audio_stability_test_vi.txt` in the repo root, output under `long_audio_stability_results\batch_<timestamp>\`. Override any of these with `--runs`, `--profile-id`, `--format`, `--corpus`, `--results-dir`, `--poll-interval`, `--timeout-seconds`.

Each run gets its own subfolder (`run_1` … `run_5`, never overwritten across batches since each invocation gets a fresh `batch_<timestamp>` directory) containing:
- `final.wav` — the merged output, downloaded through the real `/api/audio/{id}` route
- `chunks/chunk_0000.wav`, `chunk_0001.wav`, ... — preserved per-chunk audio (see caveat #1 above)
- `run_metadata.json` — run number, job ID, status, elapsed/pipeline time, audio duration, RTF, chunk counts, any error
- `text_integrity.json` — the independently recomputed chunk list, per-chunk text, and the integrity verdict

At the end: `SUMMARY.json` (all 5 runs) and `REVIEW_MANIFEST.md` — the human-review template, with every perceptual field left blank exactly as instructed. **Nothing in this script auto-marks perceptual quality PASS; it only checks technical completion and text integrity.**

## Fields the task asked for

- **Voice profile used**: `585337d3-1122-48b1-bd55-bbf31ff14374` ("Thanh Huyền") — only one exists.
- **5-run result table**: not available — no run was executed.
- **Average/min/max generation time, average RTF**: not available — needs real runs.
- **Artifact directory**: will be `D:\Tool Dich Cho Khach\long_audio_stability_results\batch_<timestamp>\` once you run it (created by the script on first run; nothing was pre-created since I have no confirmed run to seed it with real data).
- **Review manifest path**: `...\batch_<timestamp>\REVIEW_MANIFEST.md`, generated by the script at the end of a batch.
- **Technical failures**: none yet — none of the 5 runs happened.

## Exact instructions for you

1. Run the PowerShell command above from the repo root, on the machine with the GPU and the `omnivoice` model.
2. Wait for it to print `RUN 1/5` through `RUN 5/5` and finish (5 long-form jobs, sequential, each generating the full ~7.8k-character corpus — expect this to take a while; `--timeout-seconds` defaults to 45 minutes per job, well above what any prior benchmark number in this project has needed).
3. Open `REVIEW_MANIFEST.md` in the resulting `batch_<timestamp>` folder.
4. Listen to each `run_N/final.wav` in full, in order, and fill in every blank field per run (PASS/FAIL, missing speech, repeated speech, swallowed/cut words, bad boundary/pause, voice/prosody issue, timestamp of any issue, notes), plus the overall "5/5 human-reviewed PASS?" line at the bottom.
5. If you want to send me the completed manifest plus `SUMMARY.json` afterward, I can turn that into a proper written report and, if a real defect shows up, use it as the evidence base for an actual fix — which is exactly the evidence Task 4.1 said was still missing.
