# Decision Report — One-Sentence Chunk Config Benchmark (A/B/C)

**Verdict: A/B/C (proven identical: target_chars=100/120/140, max_chars=160, max_sentences_per_chunk=1) FAIL the task's decision rule. Do not promote this configuration to production as-is.**

This closes out "TASK: Benchmark three one-sentence long-form chunk configurations for Vietnamese speech-content stability," combining the real GPU run you executed on your machine with your independent human review of each completed run.

## 1. Pre-GPU check (executed here, real result)

`build_chunks()` against the real corpus produces byte-identical chunk lists for A, B, and C (113 chunks, same SHA-256 fingerprint) — confirmed before any GPU time was spent. Cause: with `max_sentences_per_chunk=1`, a chunk always closes after exactly one sentence, so `target_chars` is never consulted. One effective configuration, not three. Full detail: `precheck_chunk_identity_result.json` (already delivered).

## 2. Real GPU execution (run on your machine)

5 runs submitted, 4 technically completed:

| Run | Status | Wall time | Audio duration | RTF |
|---|---|---|---|---|
| 1 | COMPLETED | 456.75s | 366.64s | 1.2458 |
| 2 | COMPLETED | 453.15s | 366.21s | 1.2374 |
| 3 | COMPLETED | 454.21s | 367.28s | 1.2367 |
| 4 | **FAILED** | 372.32s (aborted) | — | — |
| 5 | COMPLETED | 461.38s | — | 1.2632 |

Mean RTF ≈ 1.245, peak VRAM ≈ 2.115 GB, `model_load_count=1` (no unexpected reloads), `text_integrity_ok=True` on every completed run. Far better than the historical CP0.3B-5.2 number (RTF 35.57 for 1-sentence chunks) — almost certainly because that older measurement was dominated by warm-up cost on a 2-chunk sample; here, amortized over 113 chunks with a single model load, real steady-state RTF is ~1.25, i.e. about 6-7x slower than the current production 240/320/3 default (RTF ≈ 0.18), not 190x slower.

### Run 4's failure — root cause identified, reproducible

```
error: CHUNK_FAILED: index=91 CHUNK_GENERATION_FAILED
```

Chunk 91's exact text: **`"chỉnh."`** — 6 characters. This is the tail fragment of Part Seven's deliberately-long test sentence (564 chars, already flagged in the pre-check as one of 5 sentences forced to hard-split under `max_chars=160`). The hard-split cut landed in the middle of the compound word *"hoàn chỉnh"*: chunk 90 ends "...và hoàn", chunk 91 is just "chỉnh." — an orphaned single-word fragment with no sentence context. That fragment crashed generation outright in run 4 (`GENERATION_FAILED: Cloned synthesis failed`), while the identical fragment synthesized without a hard crash in runs 1, 2, 3, and 5 — i.e., a real, reproducible, intermittent failure mode, not a fluke.

**Root cause: `split_long_sentence`'s hard-split logic can produce near-empty orphan fragments, and those fragments are the least reliable input the pipeline generates.** With `max_retries=0` (matches production), one such crash aborts the entire job.

## 3. Human review — confirmed independent, and consistent

You confirmed you listened to each of the 4 completed runs separately, and reported the same quality and defects in each. That's a materially different (and more informative) result than a copy-paste duplicate would have been: **the content-fidelity defects recur consistently across independent generations of the same chunking, not randomly.** Reported verdict across all 4: `missing_word=FAIL`, `swallowed_word=FAIL`, `repeated_word=FAIL`, `missing_sentence=FAIL`; `repeated_sentence`, `boundary_issue`, `pronunciation_issue`, `voice_consistency_issue` = PASS. Notes: errors concentrate most at chunk starts.

One timestamp check, done against real per-chunk duration data for `sample_01` (= run_03): your reported **0:17** lands almost exactly on a real chunk boundary (chunk 4 ends at 17.20s, chunk 5 starts there) — chunk 4's text is itself the sentence describing "cắt âm ở cuối câu" (audio cut at sentence end), chunk 5 is "PHẦN MỘT." This corroborates your own observation that defects cluster at chunk boundaries, with an exact, checkable location for follow-up listening (`run_03/chunks/chunk_0004.wav` and `chunk_0005.wav`, preserved via `keep_temp=True`, vs. the same position in `run_03/final.wav`).

### Follow-up: chunk 5 isolated to the RAW file — confirms inference stage; strong evidence for a second failure class

You listened to `chunk_0005.wav` (the isolated, pre-merge file) specifically and confirmed: content missing, mispronounced, present in the raw file itself — **not introduced by merge/DSP**. This rules out the trim hypothesis for this specific case and confirms the defect originates at OmniVoice inference, same failing stage CP0.3B-5.1 identified originally.

What's new: chunk 5's text is `"PHẦN MỘT."` — 9 characters, a two-word section header. CP0.3B-5.1/5.2's original finding was that chunks *exceeding* ~140-150 characters cause omission (the model runs out of duration-alignment budget on long input). Chunk 5 is nowhere near that — it's extremely short — yet it still failed at the same raw-inference stage. Real per-run data for this chunk across all 4 completed runs:

| Run | Chars | Generation time | Output audio duration |
|---|---|---|---|
| 1 | 9 | 5.718s | 1.40s |
| 2 | 9 | 5.894s | 1.39s |
| 3 | 9 | 5.913s | 1.39s |
| 5 | 9 | 6.031s | 1.34s |

Generation time (~5.7-6.0s) is disproportionate to the tiny output (~1.4s) — an implied per-chunk RTF of ~4.2, more than 3x the corpus-wide average (~1.25), for a chunk that's stable in output length run to run. Combined with chunk 91 ("chỉnh.", 6 chars, outright crashed in run 4), there are now two independent, reproducible cases of very short/minimal-context chunks failing at raw inference — one as a silent content defect (chunk 5), one as a hard crash (chunk 91).

**Correction to an earlier draft of this report** (per a second, independent read-through against the codebase): calling this a "confirmed mechanism" overstated what two data points support. What's actually established: **a strong evidence / confirmed failure class** — very short or minimal-context chunks are strongly associated with raw-inference failure in two independent, reproducible cases, distinct from CP0.3B-5.1's original "chunk too long" mechanism. What's *not* yet established: that shortness itself is the causal variable, as opposed to some other property both chunks happen to share (e.g. lacking normal sentence syntax, being a title/fragment rather than a full clause, or something specific to these two strings). Treat "short chunk → inference failure" as the leading hypothesis to fix toward and re-test, not a proven causal law.

## 4. Decision-rule check

| Criterion | Result |
|---|---|
| 5/5 (or achievable N/N) human content-stability PASS | **FAIL** — every reviewed run reported real defects |
| Zero missing sentences | **FAIL** |
| Zero repeated sentences | PASS |
| Zero clearly swallowed/missing words | **FAIL** |
| Technical completion | 4/5 — 1 run crashed on a reproducible hard-split edge case |

**A/B/C do not satisfy the criteria to be recommended as a production replacement.** This also overturns, for this specific corpus, the older CP0.3B-5.2 conclusion that 1-sentence/chunk eliminates content defects — on a much larger, harder corpus (113 chunks with an intentionally very long sentence, several edge-case paragraphs), it does not, and it introduces a new failure mode of its own.

## 5. What this does and doesn't rule out

Not ruled out: whether some *other* chunk size or a targeted fix would work. Ruled out, with real evidence: this exact family of config (rigid 1-sentence, 160-char cap, no minimum-fragment handling) is not a safe drop-in replacement for 240/320/3.

Two concrete, evidence-grounded next steps, in priority order — revised after confirming chunk 5's defect lives in the raw file (see above), which upgrades this from an untested hypothesis to a strongly supported failure class (not a proven causal mechanism — see correction above):

1. **Add a general minimum-chunk-length rule to chunking, not just for hard-split remainders.** The original plan (merge only hard-split trailing fragments below a threshold) was too narrow — chunk 5 is a *naturally short sentence* (a section header), not a hard-split remainder, and it failed the same way chunk 91 did. The fix needs to be general: in `build_chunks()`/`ChunkingConfig`, if any chunk (regardless of why it's short — a natural short sentence, a hard-split remainder, whatever) ends up below a minimum character count, merge it into the adjacent chunk (previous or next) rather than emitting it standalone. This addresses both observed failures (chunk 91's crash, chunk 5's silent content loss) with one change, and needs no model/provider/num_step change.
2. **Merge-boundary DSP trim remains a live, separate hypothesis for the *other* boundary-clustered defects** your review reported (not chunk 5 specifically, which is now confirmed inference-stage) — still worth checking against other flagged timestamps in the same way, since short output chunks generally (even ones above the future minimum-length threshold) lose a larger *fraction* of their content to the fixed 250ms trim budget than long chunks do (250ms off a 1.4s chunk is ~18% one-sided, ~36% if both edges trim to the max; the same 250ms off an 8s chunk is ~3%). This is now a secondary, chunk-*duration*-proportional risk rather than a chunk-*count* one.

Neither of these requires abandoning the "smaller chunk" direction — they're prerequisites for testing it fairly. I'd recommend implementing #1 (the general minimum-length rule) first, since it's now backed by two independent, reproducible failures rather than one, then re-running this exact same benchmark script (it needs no changes beyond whatever fixes `build_chunks`) before drawing a final conclusion on chunk size.

### Recommended fix scope (cross-checked against the codebase, not yet implemented)

Confirmed by re-reading the relevant files directly:

- The right patch surface is **`prototype/core/long_text.py`** (`ChunkingConfig`, `split_long_sentence()`, `build_chunks()`) — not `backend/services/long_form_service.py`. Production's `LONG_FORM_CHUNK_CONFIG = 240/320/3` (line 45 of that file) is passed identically into both the preflight check and the actual synthesis call, so a chunker-level fix requires no change there and no risk of the two call sites drifting apart.
- `split_long_sentence()` should become more word-safe: prefer a valid boundary (space/punctuation) over a raw character cut, and rebalance so a hard split never leaves a near-empty tail like `"chỉnh."` — this is what actually produced the mid-word cut of *"hoàn chỉnh"*.
- The minimum-length invariant belongs in `build_chunks()` (or an assembly helper it calls): never emit a standalone chunk below the threshold if merging with a neighbor doesn't break `max_chars`/`max_sentences_per_chunk`.
- Treat the minimum-length threshold (20-30 chars was floated earlier) as a **tunable candidate to test, not a hardcoded constant to trust outright**.
- Add regression tests for exactly these two reproduced cases: a compound word like *"hoàn chỉnh"* must never be split across chunks, and a short standalone header like *"PHẦN MỘT."* must never ship as its own chunk when it could legally merge with a neighbor. Existing coverage (`prototype/tests/test_long_text.py`, `backend/tests/test_long_form.py`) checks hard-max, Unicode handling, text integrity, and that production uses one shared config — but not either of these two cases.
- After the fix: re-run `benchmark_one_sentence_chunk_configs.py` unchanged on the same corpus/profile/`max_retries=0`, with production's `240/320/3` still untouched, to see whether the short/minimal-context failure class actually shrinks or disappears — that result is what would upgrade this from "strongly supported failure class" to something closer to confirmed.

## Production status

Unchanged. `LONG_FORM_CHUNK_CONFIG = 240/320/3` in `backend/services/long_form_service.py` was not touched by this benchmark or this report.
