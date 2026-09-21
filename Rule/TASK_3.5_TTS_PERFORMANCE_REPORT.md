# Task 3.5 — TTS Performance: Investigation Report

**Status: BLOCKED (investigation and diagnosis complete; no code changed; verification could not be executed this session)**

This is not an EXECUTED report. Per RULES.txt's testing/reporting discipline
("When environment prevents live verification, state: NOT VERIFIED and
explain why"; "Never convert BLOCKED into PASS by documenting the missing
requirement"), no source file has been modified, and no BEFORE/AFTER numbers
are reported for the production integration path, because this session's
`device_bash` (the only way to run Python/pytest on your machine from here)
is confirmed broken for the entire session — re-tested immediately before
writing this report, same failure as every earlier attempt:

> "A Windows update released September 8 prevents Claude's workspace from
> reaching your files. We're tracking this issue. Claude Code is unaffected."

File read/write access (`device_list_dir` / `device_stage_files` /
`device_commit_files`) still works and was used for 100% of this
investigation. No command could be executed, no benchmark could be run, and
no number below is fabricated or extrapolated as if it were measured by me
this session.

---

## 1. Repository State

Investigated via file read only (`D:\Tool Dich Cho Khach`, connected folder).
No files modified. Two new files are delivered alongside this report (not yet
committed to the repo — see §13):

- `external/OmniVoice/benchmark_production_long_form.py` — new benchmark
  harness (ready to run, not yet run)
- this report

## 2. Instructions Read

`Rule/RULES.txt`, full 1053 lines. Relevant sections: dev workflow/roles,
checkpoint governance, chunking rules (§17: prefer paragraph → sentence →
clause/word fallback; never unnecessarily regenerate completed chunks),
hardware rules (§22: GPU acceleration optional, no unsupported-hardware
claims), testing/reporting rules, PASS/BLOCKED policy. No section is specific
to TTS latency; the generic testing/reporting/PASS-BLOCKED rules governed how
this report is structured.

## 3. Baseline (pre-existing, on disk before this session touched anything)

Four real benchmark JSONs already existed under `external/OmniVoice/`, each
produced by a standalone script that talks to the vendored `omnivoice`
package **directly** — none of them exercise `prototype/core/tts_manager.py`,
`prototype/providers/omnivoice.py`, or the `backend/` FastAPI/job layer.
`test_long_vi.py` and `test_long_vi_chunked.py` (the v2 variant) each
re-implement their own local paragraph/sentence splitter rather than
importing `core.long_text.build_chunks` — confirmed by reading both scripts.

| Source | Scenario | Chars | Chunks | model_load_time_sec | avg/overall RTF | peak VRAM GB |
|---|---|---|---|---|---|---|
| `benchmark_results.json` | 9 languages, short single sentences | — | 1 each | 5.15 | 0.16–0.46 per language | ~1.94–1.96 |
| `long_vi_result.json` | Unchunked, single `generate()` call | 1738 | 1 | 5.09 | 0.1815 | 2.174 |
| `long_vi_chunked_result.json` | Chunked, max_chars≈280 | 1738 | 7 | 5.27 | 0.1366 | 3.35 |
| `long_vi_chunked_v2_result.json` | Chunked, target=220/max=340/≤2 sentences | 1738 | more than 7 | 5.58 | 0.1584 | 3.35 |

**No file anywhere in the repository shows a measured RTF anywhere close to
the task's RTF<15 target.** Every real number on disk is between 0.13 and
0.46 — 30–100× faster than the "first target." Whether that gap also holds
for the actual `backend/` + `prototype/` production integration path (job
queue, DB, multi-provider lock, per-chunk WAV re-validation, `shutil.copyfile`
to `persisted_chunks/`) has never been measured — no benchmark JSON in the
repo touches that layer. This is the central open question this task set out
to answer, and it remains open pending real execution (§9).

## 4. Files Inspected (this session)

Full reads: `Rule/RULES.txt`, `backend/services/provider_service.py`,
`backend/services/tts_service.py`, `backend/services/long_form_service.py`,
`prototype/providers/omnivoice.py`, `prototype/providers/base.py`,
`prototype/core/tts_manager.py` (in full, across several passes),
`prototype/core/long_text.py`, `prototype/core/audio_utils.py`,
`external/OmniVoice/omnivoice/__init__.py`, `external/OmniVoice/test_long_vi.py`,
`external/OmniVoice/test_long_vi_chunked.py` (partial — header/config/corpus).
Directory listings: `backend/`, `prototype/`, `external/OmniVoice/`
(recursive). No file was executed.

## 5. Findings — ruled out (evidence, not assumption)

Each of the following is a textbook TTS-latency bug. All were checked
directly against the current source and **none was found**:

- **Per-request model reload**: `OmniVoiceProvider.load()` returns
  immediately if `self._model is not None` (line-level idempotency check,
  `prototype/providers/omnivoice.py:126-141`). `ProviderService.ensure_loaded`
  / `ensure_primary_provider_loaded` only call `.load()` when state isn't
  already READY. Model load happens once per process lifetime.
- **Per-chunk voice-conditioning recomputation**: `create_voice_profile()`
  computes the clone prompt once and caches it in `self._profiles[profile_id]`
  (`omnivoice.py:179-199`); every `synthesize_cloned()` call reuses the cached
  prompt via `entry[1]` — never recomputed per chunk or per job.
- **Wrong precision / silent CPU fallback**: `dtype=torch.float16` on CUDA;
  `_load_model()` raises (`ValueError: CUDA unavailable; no automatic CPU
  fallback`) rather than silently degrading to CPU/fp32.
- **Subprocess-per-chunk / redundant model spin-up**: grepped
  `tts_manager.py` for `subprocess|ffmpeg|cuda|torch|resample` — zero
  matches. The only `subprocess` call in the whole provider is
  `_decode_reference()` (ffmpeg, decoding the reference clip for voice
  cloning), which runs exactly once per voice-profile creation, not per
  chunk or per synthesis call.
- **Repeated merge/export work**: `merge_segments()` and `export_mp3()` are
  each called exactly once per long-form job, after all chunks complete
  (`tts_manager.py`, "Merge" phase) — not per chunk.

## 6. Findings — the identified bottleneck candidate

**Production long-form chunking is far more fragmented than anything ever
benchmarked, and the only two configurations that were benchmarked show
smaller chunks costing more, per unit of audio, than larger ones.**

`backend/services/long_form_service.py` builds chunks and calls
`TTSManager.synthesize_long_text()` with **no `chunk_config` override**:

```python
for chunk in build_chunks(request.text):          # long_form_service.py:195
    ...
result = manager.synthesize_long_text(
    request.text, request.language, "omnivoice_auto",
    filename="final.wav", max_retries=0, chunk_synthesizer=synthesize,
    audio_validator=validate_wav, export_mp3_enabled=request.format == "mp3",
    on_progress=progress, is_cancelled=job.cancel.is_set)   # no chunk_config=
```

Both calls therefore fall through to `core.long_text.ChunkingConfig()`'s bare
defaults:

```python
target_chars: int = 100
max_chars: int = 160
max_sentences_per_chunk: int = 1
```

That is smaller — in every dimension — than **both** configurations that
exist as real benchmark evidence in this repo:

| Config | target_chars | max_chars | max_sentences | measured avg RTF |
|---|---|---|---|---|
| `long_vi_chunked_result.json` (v1) | — | ~280 | — | **0.1366** |
| `long_vi_chunked_v2_result.json` (v2) | 220 | 340 | 2 | 0.1584 (+16%) |
| **Production default (ships today)** | **100** | **160** | **1** | never measured |

The only two real data points available show a clean, directionally
consistent trend: going from v1's larger chunks to v2's smaller chunks
(fewer sentences per chunk, tighter target) made RTF measurably worse. The
production default pushes every one of those three knobs further in the same
direction (smaller target, smaller max, fewer sentences per chunk) than v2 —
for the 13-sentence, 1738-character fixed corpus, `max_sentences_per_chunk=1`
means roughly one chunk per sentence, i.e. close to double v1's chunk count.
Extrapolating a two-point trend to "production RTF will be worse than 0.1584"
is directionally reasonable but **is an extrapolation, not a measurement** —
flagged explicitly as such.

The mechanism this predicts is real and independently visible in the code,
not just correlational: smaller chunks mean more chunks for the same total
text, and every additional chunk pays fixed, non-GPU overhead that does not
shrink with chunk size:

- Two `torch.cuda.synchronize()` calls per chunk (`_synchronize()`, before
  and after `generate()` — by design, for accurate timing, but it is a real
  blocking barrier paid once per chunk regardless of chunk length).
- A full-file WAV decode + `np.isfinite` scan per chunk
  (`long_form_service.validate_wav`, called inside the `synthesize()`
  callback for every chunk) — and the *same* full scan runs **twice more**
  on the merged output (`tts_manager.py`'s `audio_validator(final_path)`,
  then `long_form_service.py`'s own `validate_wav(Path(result["wav_path"]))`
  after the manager returns). More, smaller chunks multiply the number of
  these full-buffer scans without reducing total audio decoded.
- A `shutil.copyfile()` to `persisted_chunks/<job_id>/` per chunk.
- Three DB writes per chunk (`PENDING` at chunk-build time, `GENERATING`
  before synthesis, `COMPLETED` after) via `self._db.chunk(...)`.
- A fixed `num_step` (24 for cloned/long-form synthesis) paid per `generate()`
  call regardless of how little text that call contains — shorter chunks pay
  the same per-call step budget for less audio output.

None of this is quantified with a real number by me, because I could not
execute the harness that would quantify it (§9). It is reported as a
structural finding with a plausible, code-grounded mechanism plus a
consistent (if two-point) empirical trend, not as a proven regression.

## 7. Findings — investigated and not recommended for change now

- **`omnivoice/models/omnivoice_flashinfer.py`** (26KB) exists in the
  vendored package alongside `omnivoice/models/omnivoice.py` (68KB, the one
  actually in use). Confirmed via `omnivoice/__init__.py`:
  `from omnivoice.models.omnivoice import (OmniVoice, ...)` — the flashinfer
  variant is not imported anywhere, by the package's own `__init__.py` or by
  `prototype/providers/omnivoice.py`. This may be a faster inference backend,
  but I have no evidence it's installed, compatible with the RTX 4050 Laptop
  GPU in the existing benchmarks, or numerically equivalent in output
  quality. Per the task's own scope ("do not change model/provider unless
  current engine is proven to be the main blocker", "evaluate... only when
  measurable") and given I cannot measure anything this session, this is
  flagged as a candidate for a **future**, separately-scoped investigation —
  not touched here.
- **`num_step` (24 for cloned synthesis, 16 for short)**: a real
  quality/speed knob, but changing it changes audio quality, and "only when
  measurable" applies directly — no measurement was possible this session,
  so left untouched.

## 8. Changes Made

**None.** No source file under `prototype/` or `backend/` was modified. Per
RULES.txt and the task's own VERIFY clause ("Do not accept optimizations
causing... clear quality regression" — which requires actually verifying),
shipping an unverified change was judged worse than reporting BLOCKED with a
concrete, ready-to-run path to verification.

One new file was authored and is ready to add to the repo (not yet
committed — pending your go-ahead, see §13):

- `external/OmniVoice/benchmark_production_long_form.py` — see §9.

## 9. The benchmark harness (ready to run, not yet run)

`external/OmniVoice/benchmark_production_long_form.py` calls the **real**
`TTSManager.synthesize_long_text()` and `OmniVoiceProvider` directly (same
classes `backend/services/long_form_service.py` uses), on the exact same
1738-character Vietnamese corpus already used in `long_vi_result.json` /
`long_vi_chunked_result.json` / `long_vi_chunked_v2_result.json` (copied
verbatim from `test_long_vi_chunked.py`), so its output is directly
comparable to the four existing JSONs. It does not modify any source file —
chunk size is varied only through the `chunk_config=` keyword
`synthesize_long_text()` already accepts.

In one process it:

1. Loads the model once, times it (`model_load_sec`), and records
   `provider._load_count`.
2. Creates one voice profile from `ref_vi.wav` (already in the repo), timing
   it separately (`voice_conditioning_sec`).
3. Runs `synthesize_long_text()` **twice**, reusing the same loaded model and
   voice profile both times, changing only `chunk_config`:
   - `current_default` = `ChunkingConfig(target_chars=100, max_chars=160,
     max_sentences_per_chunk=1)` — what ships today.
   - `proposed` = `ChunkingConfig(target_chars=240, max_chars=320,
     max_sentences_per_chunk=3)` — a starting hypothesis anchored on the v1
     evidence in §6, not a final recommendation.
4. For each run, measures and reports separately: chunk-build
   (`chunk_build_sec`), summed pure-inference time
   (`sum_inference_gen_time_sec`, from `result.gen_time` per chunk), summed
   per-chunk wall time including WAV validation/IO
   (`sum_chunk_wall_time_sec`), the difference as `chunk_overhead_sec`, merge
   time (`merge_sec`), MP3 export time (`export_mp3_sec`), end-to-end wall
   time and RTF, inference-only RTF, peak allocated VRAM, text-integrity
   (round-trip character check against the source), audio validity (full WAV
   decode/finite check on the merged output), and `model_load_count` (must
   read 1 across both runs — if it reads 2, something is silently reloading
   the model between configs, which would itself be a bug worth its own
   report).
5. Writes `benchmark_production_long_form_result.json`.

Run it with the same convention already established for this repo's tests:

```
$env:PYTHONPATH='prototype'; & .\external\OmniVoice\.venv312\Scripts\python.exe external\OmniVoice\benchmark_production_long_form.py
```

**I have not run this script.** Every API it calls (`TTSManager.__init__`,
`register_provider`, `synthesize_long_text`'s `chunk_config` /
`chunk_synthesizer` / `audio_validator` kwargs, `OmniVoiceProvider.load` /
`create_voice_profile` / `synthesize_cloned`) was checked line-by-line
against the current source (§4), but a real execution could still surface an
issue static reading can't catch. Treat the first run as a shakedown, not a
guaranteed clean pass.

## 10. Tests

No tests were added or run. No pytest suite exists for TTS latency/RTF —
the existing `backend/tests/` and `prototype/tests/` suites test correctness
(job state machine, chunk text-integrity, audio validity), not performance,
and were not touched. Running the existing regression suite
(`$env:PYTHONPATH='prototype'; & .\external\OmniVoice\.venv312\Scripts\python.exe -m pytest backend/tests prototype/tests -v`)
after any future chunk-config change is still recommended, since chunk size
interacts with `test_long_text.py` / `test_long_text_manager.py` /
`test_audio_boundary.py`, none of which I ran this session.

## 11. Test Results

**NOT VERIFIED** — no test or benchmark was executed this session
(`device_bash` broken, confirmed by direct test at the start of this turn:
`echo connectivity-test-ok` failed with the same September-8-Windows-update
error as every prior attempt).

## 12. Manual Verification

**NOT VERIFIED** — no audio was generated or listened to this session.

## 13. Security / Privacy Review

No new attack surface. The harness script reads only files already in the
repo (`ref_vi.wav`, the hardcoded corpus string) and writes only under
`external/OmniVoice/benchmark_production_long_form_work/` and a result JSON
next to itself — no network calls, no new dependencies, no change to what
data the production code paths log or persist. It is a local dev/benchmark
script, not something wired into any API route.

## 14. License Impact

None. No new dependency was added; the harness imports only modules already
used elsewhere in the repo (`torch`, `numpy`, `soundfile`, and the repo's own
`core`/`providers` packages).

## 15. Known Limitations

- **No production-path RTF number exists anywhere, before or after.** Every
  real benchmark in the repo tests the vendored package directly with
  locally-duplicated chunking logic, never `TTSManager` or the `backend/`
  job layer. The harness in §9 is built to close that gap but has not been
  run.
- **The chunk-size → RTF relationship in §6 is a two-point trend, not a
  controlled measurement of production code.** It is a reasonable basis for
  a hypothesis to test, not a conclusion.
- **`CONFIG_PROPOSED` in the harness is a starting point, not a
  recommendation.** Its exact numbers (`target_chars=240, max_chars=320,
  max_sentences_per_chunk=3`) were chosen to sit in the direction the
  existing v1/v2 evidence favors, not derived from a measurement of this
  specific corpus at that exact setting.
- **`device_bash` has been broken for this entire session** (every attempt,
  including one immediately before this report, fails with the same
  Windows-update message). I have no way to execute Python, pytest, or the
  vendored CLI/benchmark scripts from here. This is an environment
  limitation on my end, not evidence about the product's actual performance.
- Whether flashinfer (§7) or `num_step` tuning would help is unknown and
  explicitly out of scope for this report.

---

## Next Step

This is **BLOCKED**, not EXECUTED. To unblock:

1. Run `external/OmniVoice/benchmark_production_long_form.py` locally (or
   have me run it once file/shell access to your machine is restored) and
   share `benchmark_production_long_form_result.json`.
2. If it confirms `current_default` is meaningfully worse than `proposed`
   (and `proposed` shows no text/audio regression, `model_load_count_total`
   reads 1, and the existing regression suite still passes), the actual code
   change is a single line at `backend/services/long_form_service.py:239-243`
   — add `chunk_config=ChunkingConfig(target_chars=..., max_chars=...,
   max_sentences_per_chunk=...)` to the `manager.synthesize_long_text(...)`
   call — plus the matching `build_chunks(request.text, config=...)` call at
   line 195 so the pre-flight text-integrity check chunks the same way. That
   change is intentionally not made in this turn.
3. Per your own instructions: waiting for ChatGPT review before any further
   optimization or Task 4.
