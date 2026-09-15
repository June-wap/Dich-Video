# CP0.2C — Multilingual provider validation

STATUS: PASS.

## Implemented

- Canonical IDs/display/native names in prototype/core/languages.py.
- Existing text_utils.LANGUAGE_NAMES is a compatibility export; manager ordering and OmniVoice capabilities use the canonical IDs.
- Exactly vi,en,zh,ja,es,pt,it,fr,hi accepted for normal and cloned TTS.
- Both modes share strict validation and exact runtime propagation; no casing/whitespace/region/name aliases, None or language-agnostic fallback.
- VERIFIED = existing CUDA normal short-TTS baseline; EXPERIMENTAL-UPSTREAM = known pinned upstream ID, not enabled; UNSUPPORTED = unknown/malformed input. Experimental inputs return normalized LANGUAGE_NOT_SUPPORTED with their classification preserved in diagnostics.
- Upstream IDs are a metadata snapshot with source SHA256, not an implicit expansion of accepted languages.
- Diagnostics include provider, language/status, device, model dtype, audio dtype, generation time, duration, RTF, mode and status. Unknown/unloaded model dtype stays null. Dtype is captured during the protected model operation.
- No production verification claim for upstream or CPU. Real clone validation remains Vietnamese; nine-language VERIFIED is explicitly scoped to normal-TTS baseline.

## Tests

33/33 automated tests PASS (7 CP0.2C + 26 prior tests). New tests cover all nine IDs in both modes, exact propagation/prompt reuse, no fallback, three status categories, capability metadata, dtype/RTF diagnostics, invalid-input diagnostics and agreement with existing benchmark evidence.

Targeted real CUDA smoke PASS; no nine-language benchmark rerun:

| Mode | Language | Model dtype | Audio dtype | Audio duration | Generation | RTF |
|---|---|---|---|---:|---:|---:|
| Normal | en | float16 | float32 | 2.04 s | 2.795 s | 1.3701 |
| Cloned | vi | float16 | float32 | 2.09 s | 1.840 s | 0.8804 |

Both use cuda:0 and canonical 24000 Hz mono output. Offline flags and socket-connect blocking were enabled. The smoke verifies core diagnostics; final additional verification-scope annotation and dtype snapshot placement are covered by the final automated suite. No historical smoke output was edited.

Evidence: cp02c_tests.log, cp02c_smoke.log, cp02c_smoke.json.
Audio: prototype/outputs/cp02c_en_normal.wav and cp02c_vi_cloned.wav.

## Files changed

Added:
- prototype/core/languages.py
- prototype/core/omnivoice_upstream_languages.json
- prototype/tests/test_omnivoice_languages.py
- prototype/tests/run_omnivoice_language_smoke.py

Modified:
- prototype/core/text_utils.py
- prototype/core/tts_manager.py (canonical language ordering only)
- prototype/providers/omnivoice.py
- prototype/providers/OMNIVOICE.md

Reports/output artifacts added separately. No external engine/model changes, UI redesign or long-text implementation.

## Limitations / NEXT CP0.2D

VERIFIED does not certify pronunciation, similarity, CPU or production readiness. Experimental upstream IDs remain disabled. Upstream catalog reflects its recorded local snapshot, not future upstream releases. Performance numbers are measurements, not guarantees.

CP0.2C complete. Await CP0.2D requirements; no next-checkpoint implementation started.
