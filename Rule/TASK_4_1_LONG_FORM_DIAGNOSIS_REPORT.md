# Task 4.1 — Diagnose Long-Form Missing/Repeated Speech

**Status: PARTIALLY EXECUTED / PARTIALLY BLOCKED.** Stage 1 (chunking) was actually run, in this sandbox, against the real production chunking code — that part is EXECUTED with real evidence, not reasoning. Stages 2–4 (inference, merge, and any listening/ASR verdict) require the real OmniVoice model on your GPU machine, which I could not reach this turn: `device_bash` failed with the same "Windows update Sept 8 / Plan9 drive" error as every prior round in this session (re-tested at the start of this task, and again just now — the device bridge itself briefly dropped entirely mid-task and then reconnected, but the shell itself never came back). File read/write (`device_list_dir`/`device_stage_files`/`device_commit_files`) still worked throughout, which is how everything below was delivered and verified. Those stages are honestly **BLOCKED**, not guessed at.

No production file was touched. `backend/services/long_form_service.py`'s `LONG_FORM_CHUNK_CONFIG` is unchanged, `max_retries=0` is unchanged, nothing under `num_step`/FlashInfer/frontend/voice-profile/model code was touched.

## Files delivered (all new, none overwrite production code)

Committed to `D:\Tool Dich Cho Khach\external\OmniVoice\` (same directory as the existing Task 3.5 `benchmark_production_long_form.py`, same conventions) and byte-verified via fresh stage-back + `cmp`:

- `trace_chunking.py` — **executed** in this sandbox (pure Python, real `core.long_text` module, no GPU needed). Produces `trace_chunking_result.json`.
- `trace_chunking_result.json` — the full, real output of that run (all chunk texts, integrity checks, oversized-sentence detection) for configs A/B/C.
- `benchmark_long_form_diagnostic.py` — **not yet executed** (needs your GPU). Ready to run; extends the Task 3.5 harness with per-chunk WAV preservation, per-chunk vs. merged-audio WER (if you have local ASR), and merge-boundary trim diagnostics. See "How to run it" below.

## 1. Trace: input → normalized → build_chunks() → exact text per TTS call

Executed against the **same fixed Vietnamese corpus** already established in `benchmark_production_long_form.py` (1738 characters, 7 paragraphs), so results are directly comparable to the Task 3.5 numbers already on record.

| Config | target/max/sentences | chunk_count | chars min/avg/max | exact text integrity | oversized sentences forced to hard-split |
|---|---|---|---|---|---|
| **A — current production** | 240/320/3 | **7** | 185 / 246.6 / 280 | ✅ exact | **0** |
| **B — sentence-first balanced** | 200/260/2 | **10** | 105 / 172.3 / 251 | ✅ exact | **0** |
| **C — strict one-sentence baseline** | 100/160/1 | **15** | 46 / 114.5 / 159 | ✅ exact | **2** |

`exact_text_integrity_ok` and `normalized_text_integrity_ok` are both `True` for all three configs — reconstructing the chunk texts (stripped of whitespace) reproduces the normalized input exactly, character for character, for A, B, and C. **Chunking-stage text loss is not the mechanism on this corpus, for any of the three configs.** This confirms (independently, not just by re-trusting it) the same integrity check `long_form_service.py` and `tts_manager.py` already run in production.

**A genuine surprise, worth flagging directly:** it is config **C** (the old, strict single-sentence baseline) that forces 2 sentences to be hard-split mid-sentence at a comma (via `split_long_sentence`), not A. Configs A and B never trigger a forced mid-sentence cut on this corpus — every natural sentence already fits inside one chunk at those thresholds. The two forced splits in C:

- `[para 0]` (162 chars): *"Những hệ thống trí tuệ nhân tạo ngày càng được ứng dụng rộng rãi trong nhiều lĩnh vực khác nhau, từ giáo dục, y tế, sản xuất nội dung cho tới nghiên cứu khoa học."* → cut into `"...từ giáo dục, y tế,"` / `"sản xuất nội dung cho tới nghiên cứu khoa học."`
- `[para 6]` (185 chars): *"Nếu kết quả ổn định, bước tiếp theo sẽ là kiểm tra văn bản dài hơn nữa, kiểm tra nhiều kiểu nội dung khác nhau và so sánh chất lượng với các mô hình chuyển văn bản thành giọng nói khác."* → cut into `"...kiểm tra văn bản dài hơn nữa,"` / `"kiểm tra nhiều kiểu nội dung khác nhau..."`

This directly **complicates** the "smaller chunks are always safer" intuition I gave you before actually running this trace — on this specific corpus, going smaller (C) is what introduces mid-sentence cuts, not going larger (A). All 7 of A's chunks are naturally 1–2 whole sentences (never actually reaching the configured max of 3 — `max_chars=320` is the binding constraint here, not `max_sentences_per_chunk=3`), so in practice **A behaves like "1–2 full sentences, ≤280 chars," not "3 sentences."**

Every chunk's exact text for all three configs is in `trace_chunking_result.json` (`configs[].chunks[]`) for direct inspection.

## 2. A second, code-grounded mechanism I hadn't surfaced before — merge-stage boundary trimming

Reading `prototype/core/tts_manager.py`'s merge step and `prototype/core/audio_utils.py::merge_segments`/`_trim_segment_safely` closely for this task turned up something relevant that my earlier conversational answer missed:

`merge_segments()` runs `_trim_segment_safely()` on **every chunk**, trimming up to `max_trim_ms=250ms` off each chunk's leading/trailing edge whenever a 5ms probe window there reads ≤ `-48.0 dBFS` (`BoundaryDSPConfig` defaults). This exists to strip real silence gaps — but if a word right at a chunk boundary is spoken quietly (very plausible, since that word used to be mid-sentence in the original continuous text and is now isolated at the very start/end of an independent TTS call), it can be misclassified as silence and clipped. This would look exactly like "the model dropped a word," but the defect would actually be introduced **after** generation, at merge time.

This matters directly for your question: **this mechanism runs once per chunk boundary**, so it happens *more often*, not less, with *smaller* chunks — config C has 14 boundaries, A has 6. If boundary-trim clipping turns out to be a real contributor, that argues in the **opposite direction** from the "shorter chunks are safer" instinct, and in the opposite direction from the forced-hard-split finding above pointing at C too. I do not have evidence yet that this is actually happening — I'm flagging it because it's a second, equally plausible, code-real mechanism, and `benchmark_long_form_diagnostic.py` is built specifically to test it (it compares each chunk's own isolated pre-merge transcript against the final merged transcript at the same boundary).

## 3. Stages 2–4 (inference, merge, timing/RTF) — BLOCKED

I could not generate a single second of audio this turn — no GPU, no model weights, no `device_bash`. Everything below that would require that is explicitly not claimed:

- **Failing chunk(s) and exact text**: none identified — I have no generated audio to inspect. `trace_chunking_result.json` has every chunk's exact text ready for when audio exists; the two hard-split sentences under config C above are the ones I'd prioritize listening to first, since they're the only case where the chunker itself hands the model an incomplete-feeling sentence fragment.
- **A/B/C quality observations (listening/ASR)**: not run.
- **Timing/RTF**: only chunk *counts* are known (7 / 10 / 15) since that's chunking-only and needs no GPU. Wall-clock time and RTF need real inference. Task 3.5's prior numbers exist for A and C specifically (15 chunks/26.613s/RTF 0.2895 for something close to C's shape, 7 chunks/16.727s/RTF 0.1822 for A) — but per `TASK_3.5_VERIFICATION_BLOCKED.md` and `TASK_3.5_FIX_REPORT.md` (both already in this project), those numbers were reported *to* a prior round of this session by you, not measured by me, and — importantly — **no listening or content-quality check was ever done on them**, only timing and character-level text integrity. B has no prior numbers at all; it's new.
- **Whether 240/320/3 correlates with the issue**: **not proven either way.** The one proxy I could measure without a GPU (forced mid-sentence hard-splitting) argues *against* A being uniquely risky on this corpus — it has zero such splits, while the old C baseline has two. But that proxy only covers the chunking stage; it says nothing about per-call generation length stressing the model (A's calls are 2–3x longer per call than C's) or about the boundary-trim mechanism in §2, both of which point the other way and remain untested. I'm not going to force these into a conclusion — that's exactly why the task asked for actual audio evidence before changing anything.

## Recommendation

**Do not change `LONG_FORM_CHUNK_CONFIG` yet — the evidence to justify a specific change doesn't exist.** What the chunking-only analysis rules out (text loss during chunking itself, for A/B/C, on this corpus) is real and useful, but it can't tell you which of two plausible-and-opposite mechanisms (longer per-call generation vs. more frequent boundary trims) is actually responsible, or whether it's something else entirely (e.g. model-level hallucination independent of chunk size).

Next step: run `benchmark_long_form_diagnostic.py` on your machine (GPU + `external/OmniVoice/.venv312`, same as every prior benchmark this session):

```powershell
$env:PYTHONPATH='prototype'; & .\external\OmniVoice\.venv312\Scripts\python.exe external\OmniVoice\benchmark_long_form_diagnostic.py --runs 3
```

Optional but strongly recommended: `pip install faster-whisper` inside `external\OmniVoice\.venv312` first (benchmark-only, never imported by `backend/`/`prototype/` production code) so the script can compute WER between each chunk's isolated pre-merge audio and its exact text, and between the final merged audio and the full input — that's what actually distinguishes "inference dropped/repeated a word" from "merge trimmed a word" from "no defect detected," per chunk, per run, per config. Without ASR installed, the script still runs and gives you chunk counts, timing/RTF, VRAM, and preserved WAVs for manual listening (`benchmark_long_form_diagnostic_work/<label>/run_<n>/chunk_0000.wav`, etc. — `keep_temp=True` is set specifically so these survive; production deletes them).

Once you have that output (or even without ASR — the preserved per-chunk WAVs alone would let you manually spot-check config A's 7 chunks vs C's 15 by ear across 3 runs each), send me the JSON/your listening notes and I'll turn it into an actual root-cause fix, per this task's own instruction not to guess.

## Requirements checklist

- Preserve sentence boundaries whenever possible — unchanged, this is `build_chunks()`'s own existing behavior; not modified.
- Verify reconstructed chunk text equals normalized input exactly — done for stage 1 (real, executed check, all three configs pass); the diagnostic script re-asserts this before generating any audio, so a future chunking regression can never be misread as an inference regression.
- Record per chunk (index, exact text, chars, synthesis time, WAV duration/status) — implemented in `benchmark_long_form_diagnostic.py`, not yet run.
- Preserve per-chunk WAVs — implemented via `keep_temp=True` (production's default deletes them); not yet run.
- Determine chunking vs. inference vs. merge — chunking is ruled out with real evidence (§1); inference vs. merge needs the benchmark run (§2–3).
- Run each config multiple times — `--runs` (default 3) in the diagnostic script; not yet run.
- Measure total time/RTF/chunk count — chunk counts done (chunking-only); time/RTF needs the benchmark run.
- ASR for benchmark diagnostics only, no production dependency — implemented as a guarded, optional `faster_whisper` import inside the standalone script only.
- No production `LONG_FORM_CHUNK_CONFIG`/retry/num_step/FlashInfer/frontend/model changes — none made.

## Files changed and test results

No `backend/` or `prototype/` (production) file was changed. New files only: `external/OmniVoice/trace_chunking.py` (executed, output attached), `external/OmniVoice/trace_chunking_result.json` (real output), `external/OmniVoice/benchmark_long_form_diagnostic.py` (not executed — needs your GPU). "Test results": stage-1 chunking trace ran cleanly with `exact_text_integrity_ok=True`/`normalized_text_integrity_ok=True` for A, B, and C — that is the one thing in this report backed by an actual run rather than a request for one.
