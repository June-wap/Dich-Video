# Implementation Report — Fixing the Two Confirmed Short-Chunk Defects (CP0.4-1)

**Status: EXECUTED for items 1-3 (real code change, real tests, real evidence, delivered and byte-verified on your machine). NOT DONE for items 4-6, by deliberate choice, explained below. Item 7 (don't touch `LONG_FORM_CHUNK_CONFIG`) held throughout.**

This implements the fix plan from the previous message, against the two defects your benchmark run and listening review confirmed: chunk 91 (crashed, "chỉnh." orphan tail from a hard split) and chunk 5 (silent content loss, "PHẦN MỘT." shipped as a standalone 9-char chunk).

## 1-2. The code change

Both fixes live entirely in `prototype/core/long_text.py`. `backend/services/long_form_service.py` and `LONG_FORM_CHUNK_CONFIG` (still `240/320/3`) were not touched.

**Item 1 — `split_long_sentence()`'s hard-split fallback no longer produces orphan tails.** The old logic greedily filled each piece to `max_chars` before moving on, which is what left "chỉnh." isolated: a 564-char sentence split into a 158-char piece and a leftover 6-char piece. The new `_split_balanced()` helper computes how many pieces the remainder actually needs (`ceil(len / max_chars)`) and cuts near the *balanced* size instead, still preferring a word boundary, falling back to a hard cut only when no boundary exists at all (preserves the existing "a"*1000 → 10×100-char-pieces test exactly).

**Item 2 — a new, opt-in `min_chars` field on `ChunkingConfig`.** Default `0` = disabled, so no existing caller's behavior changes unless it explicitly sets it. When set, `build_chunks()` merges any fragment shorter than `min_chars` into an adjacent fragment (previous, else next) before it can ever ship as a standalone chunk — provided the merge doesn't exceed `max_chars`. This applies uniformly to natural short sentences (chunk 5's case) and any leftover split fragment, per your reviewer's instruction that the fix be general rather than narrowly targeted at hard-split remainders. Per their other instruction, the threshold is **not hardcoded** — it's a config value the caller chooses, not a constant baked into the algorithm.

One documented trade-off: when `min_chars` forces a merge, the resulting chunk can hold more sentences than `max_sentences_per_chunk` nominally allows (e.g. under a strict `1` cap). That's intentional — shipping an ultra-short fragment to inference standalone is the confirmed problem; occasionally exceeding the nominal per-chunk sentence count by one is the accepted cost of avoiding it. This is called out in the code's docstring, not hidden.

## 3. Regression tests — real, executed

Added 10 new tests to `prototype/tests/test_long_text.py` (appended after the existing suite, using the same imports/conventions already there):

- `test_hoan_chinh_hard_split_no_longer_produces_tiny_orphan_tail` — reproduces chunk 91's exact shape (38× filler word + "hoàn chỉnh.", tuned so the *old* algorithm's cutoff lands exactly between "hoàn" and "chỉnh.") and asserts the orphan never appears and piece sizes stay balanced.
- `test_hard_split_balances_piece_sizes_generally` — a second, independent balance check.
- `test_long_sentence_hard_fallback_still_never_exceeds_limit_no_whitespace` — the no-word-boundary edge case (matches the existing `"a"*1000` test) still holds.
- `test_min_chars_disabled_by_default_preserves_old_behavior` — documents that the bug still reproduces when `min_chars` isn't set, so the default staying `0` is a visible, deliberate choice, not an oversight.
- `test_short_header_merges_into_next_sentence_when_min_chars_enabled` — reproduces chunk 5's exact case ("PHẦN MỘT." + a following sentence) and asserts it no longer ships standalone.
- `test_short_trailing_sentence_merges_into_previous_when_no_next_exists`, `test_min_chars_merge_never_drops_or_duplicates_text`, `test_min_chars_never_produces_chunk_above_max_chars`, `test_invalid_min_chars_config` (×2 parametrized cases) — general correctness/safety coverage for the new field.

**No pytest available in my sandbox (no network to PyPI), so I wrote a small stdlib-only shim** (`pytest.raises`/`pytest.mark.parametrize`) and ran every test function for real — both the full original suite unmodified, and the new tests, against the fixed module. This is a test-harness workaround only; it is not shipped and doesn't change how your real `pytest` will run the suite.

```
PASSED: 47
FAILED: 0
```

37 original test cases (all of them, including the parametrized ones) + 10 new = 47/47, all real assertions, none skipped. I then re-staged the files fresh from your machine after committing them (see below) and reran the exact same check against what's actually on disk there — same result, 47/47.

## Real-corpus confirmation (this is the part I'd flag as most convincing)

Beyond the synthetic regression tests, I ran the fixed chunker against your real `long_audio_stability_test_vi.txt` — the same corpus that produced the actual crash and defect — and compared chunk-for-chunk against the pristine original:

**Chunk 91 (the crash), before vs. after, at the exact same source-text position:**

| | Before (original) | After (fixed) |
|---|---|---|
| chunk[90] | `"...và hoàn"` (158 chars) | `"...được ghép lại"` (80 chars) |
| chunk[91] | `"chỉnh."` (6 chars) — this is what crashed run 4 | `"...và hoàn chỉnh."` (84 chars) |

Same source text (164 chars combined either way), now split into two balanced pieces instead of one near-full piece plus a 6-char orphan. The exact defect is gone, confirmed on the real corpus, not just a synthetic test.

**Chunk 5 and the other 8 section headers, with `min_chars=25`:** all 9 `"PHẦN X."` headers (previously standalone 8-10 char chunks) now merge with their following sentence — e.g. chunk 5 becomes `"PHẦN MỘT. KIỂM TRA CÁC CÂU NGẮN."` (32 chars) instead of shipping alone. Verified on the real corpus: zero chunks under 25 chars, `max_chars` never exceeded, exact text integrity holds (reconstructed text == source, whitespace-normalized), and A/B/C (target_chars 100/120/140) remain byte-identical to each other with `min_chars` set, exactly as before — only the total chunk count changes (113 → 93, since 9 headers no longer count as separate chunks and the hard-split sentence no longer needs an extra tiny piece).

I did not fabricate or guess these numbers — they're from actually running `build_chunks()` against your real corpus file in this sandbox, both before and after the fix, and printing the output.

## What this does NOT include (deliberately, not an oversight)

**Item 4 — re-running `benchmark_one_sentence_chunk_configs.py` on GPU.** I can't run this myself; it needs your machine. The script itself needs no changes (it already calls the real `build_chunks()`/`TTSManager`), so once you're ready, running it again with `min_chars=25` wired into the configs (or as-is, to isolate the item-1 effect alone) is the next real test. I'm happy to prepare a small variant that sweeps `min_chars` if useful.

**Item 5 — enabling `max_retries > 0` in `backend/services/long_form_service.py`.** I did not make this change. Reasons: it's a real production behavior change (touches error semantics and latency-on-failure for every live long-form job), it's in a file I cannot import or test in this sandbox (module-level `soundfile` import), and I only ever framed it as "consider," not a committed line item. I'd rather flag it explicitly and get a clear yes than slip a production change through this round without being able to verify it. If you want it, tell me and I'll make the specific one-line change at the `manager.synthesize_long_text(...)` call site and report it the same way — as an unexecuted, un-tested-by-me change, clearly marked.

**Item 6 — the DSP-trim hypothesis for other boundary-clustered defects.** This is an investigation, not a code change, and needs specific chunk WAV files from your artifacts (raw pre-merge vs. final merged, at the other timestamps your review flagged) to actually check — I don't have new artifacts to investigate against this round.

**Item 7 — don't touch `LONG_FORM_CHUNK_CONFIG`.** Held: confirmed unchanged, still `240/320/3`, and the new `min_chars` field defaults to `0` so production's synthesis behavior is byte-for-byte identical to before this change, whether or not `LONG_FORM_CHUNK_CONFIG` is ever updated to use it.

## Delivered and verified

- `prototype/core/long_text.py` — written to your machine, then **re-staged fresh and `cmp`'d byte-for-byte identical** against what I sent.
- `prototype/tests/test_long_text.py` — same verification, byte-identical.

## Known limitation worth flagging

When `min_chars` forces a merge, the resulting `TextChunk.sentence_count` still counts the merged fragment as "1" (matching the existing, already-approximate convention where a hard-split fragment is also counted as "1" even though it's less than a full sentence). If any downstream code relies on `sentence_count` being an exact sentence count rather than an "expanded-fragment count," that's a pre-existing simplification this change doesn't worsen but also doesn't fix.

## Next step, your call

The fix is real, tested, and on your machine, but production (`240/320/3`) doesn't use `min_chars` and isn't affected. To actually resolve chunk 91/chunk 5-style defects for a `100/160/1`-style config, the next real test is re-running the GPU benchmark with `min_chars` set (item 4) — that's the step that would upgrade this from "fixes the two known cases, verified on paper and on the real corpus" to "verified end-to-end with real audio and a fresh human listening pass."
