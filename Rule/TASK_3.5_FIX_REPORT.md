# Task 3.5 FIX — Long-Form Chunk Sizing: EXECUTED

## Evidence this fix is built on (supplied by you, from the production harness)

| | current (100/160/1) | candidate (240/320/3) |
|---|---|---|
| chunks | 15 | 7 |
| wall time | 26.613s | 16.727s |
| RTF | 0.2895 | 0.1822 |
| text integrity | — | PASS |
| audio validity | — | valid WAV/MP3 |
| model_load_count | — | 1 |
| peak VRAM | baseline | +~3.3% |

~37% faster wall time / RTF, no correctness regression. This confirms the
hypothesis from the blocked investigation report
(`Rule/TASK_3.5_TTS_PERFORMANCE_REPORT.md`) — production's default chunking
was far more fragmented than anything ever benchmarked, and the fragmentation
itself (not GPU inference) was the bottleneck.

## What changed

**`backend/services/long_form_service.py`**
- Added `from core.long_text import ChunkingConfig, build_chunks` (was just
  `build_chunks`).
- Added one module-level constant, `LONG_FORM_CHUNK_CONFIG =
  ChunkingConfig(target_chars=240, max_chars=320,
  max_sentences_per_chunk=3)`, with a comment recording the benchmark numbers
  above so the next person doesn't have to go find them.
- The preflight loop (`for chunk in build_chunks(request.text):`) now reads
  `for chunk in build_chunks(request.text, LONG_FORM_CHUNK_CONFIG):`.
- The `manager.synthesize_long_text(...)` call now passes
  `chunk_config=LONG_FORM_CHUNK_CONFIG`.

Both call sites reference the **same object** — nothing is duplicated. No
other line in the file changed.

**`backend/tests/test_long_form.py`**
- Imports `LONG_FORM_CHUNK_CONFIG` alongside `validate_wav`.
- Two existing assertions that predict production's chunking with
  `build_chunks(TEXT)` (bare defaults) now read
  `build_chunks(TEXT, LONG_FORM_CHUNK_CONFIG)`, so they keep testing the real
  invariant instead of silently failing against the new default:
  - `test_create_order_identity_merge_and_artifact` (chunk texts passed to
    the synthesizer must match `build_chunks` output)
  - `test_fifo_running_cancel_and_profile_deletion` (total
    `synthesize_cloned_calls` count)
- New test: `test_preflight_and_synthesis_use_identical_chunk_config`. It
  monkeypatches `build_chunks` at both of its independent import sites
  (`backend.services.long_form_service.build_chunks`, used by the preflight
  loop, and the name aliased as `core.build_chunks` in this test file —
  `core.tts_manager`'s own import — used inside
  `synthesize_long_text()`), runs one real job through the harness, and
  asserts: each call site invoked `build_chunks` exactly once, both received
  `LONG_FORM_CHUNK_CONFIG` by identity (`is`, not just equal values), and
  both produced the identical chunk-text sequence. It deliberately does not
  hardcode a chunk count for this test file's `TEXT` fixture (that text was
  never separately benchmarked) — instead it compares against a live
  `build_chunks(TEXT, LONG_FORM_CHUNK_CONFIG)` call, so it can't itself
  become a second, silently-stale literal.

## What did NOT change

- `num_step` — untouched (still 24 for cloned/long-form synthesis).
- FlashInfer — not enabled; `omnivoice/__init__.py` still resolves `OmniVoice`
  to `omnivoice/models/omnivoice.py`, unchanged.
- Model/provider — `OmniVoiceProvider`, `k2-fsa/OmniVoice`, unchanged.
- Frontend/database — no file under `frontend/` or the persistence layer was
  touched. `ChunkingConfig`'s own dataclass defaults in `core/long_text.py`
  are also unchanged (100/160/1) — Short TTS and any other caller that
  doesn't pass an explicit config is unaffected; only `long_form_service.py`
  now overrides it.
- No unrelated refactor — the two edits above are the entire diff to
  `long_form_service.py`.

## Tests

Added: `test_preflight_and_synthesis_use_identical_chunk_config` (see above).
Updated: 2 existing assertions in the same file, listed above, so they don't
regress against the new default.

## Verification — what I could and couldn't do myself

I still have no way to execute Python/pytest on your machine this session —
`device_bash` was tested again immediately before making these edits and
failed with the same error as every prior attempt this week ("A Windows
update released September 8 prevents Claude's workspace from reaching your
files"). File read/write still works and is how every edit below was made
and checked:

- **Applied and persisted**: both files were edited, delivered to you, then
  committed to `D:\Tool Dich Cho Khach\...` and independently re-verified —
  freshly re-staged from the device and diffed byte-for-byte against the
  intended content (not just trusting the commit tool's "written" response,
  per this session's established practice). Both matched exactly.
- **Syntax-checked**: both files parse cleanly (`ast.parse`) in a plain
  Python 3 environment. This is a weaker check than actually running them
  (no access to this project's dependencies), but it does rule out typos,
  indentation errors, and mismatched brackets/quotes.
- **API calls hand-verified against current source, not guessed**: I
  re-read the live `TTSManager.synthesize_long_text` signature and
  `core.long_text.build_chunks` signature from the device before writing
  these edits, to make sure `chunk_config=` is a real keyword-only parameter
  and `build_chunks(text, config)` takes positional `config` — both
  confirmed.
- **NOT run**: `pytest backend/tests/test_long_form.py`, the rest of
  `backend/tests/`, `prototype/tests/`, or any GPU generation. I did not
  fabricate pass/fail results for any of these.

**Please run, and share the output:**

```
$env:PYTHONPATH='prototype'; & .\external\OmniVoice\.venv312\Scripts\python.exe -m pytest backend/tests/test_long_form.py -v
$env:PYTHONPATH='prototype'; & .\external\OmniVoice\.venv312\Scripts\python.exe -m pytest backend/tests prototype/tests -v
```

The first targets exactly what changed. The second is the fuller regression
sweep the task asked for ("backend regression... full regression if
practical") — `prototype/tests/test_long_text.py`,
`test_long_text_manager.py`, and `test_audio_boundary.py` all touch chunking
and are worth including since chunk size changed, even though none of them
import from `long_form_service.py` directly.

If GPU execution is available to you, generating and listening to 2–3
representative long Vietnamese samples (as the task asks) is also something
only you can do this session — I can't hear audio or drive a GPU run myself.

## Rollback

If `pytest` surfaces a failure, or a listened-to sample shows missing/
duplicate text, a crash, or a clear quality regression, the entire change is
two edits to one file plus the config constant — revert
`backend/services/long_form_service.py` to drop `chunk_config=` from the
`synthesize_long_text()` call and the second argument from the preflight
`build_chunks()` call (or just `git checkout` the file), and the three
`test_long_form.py` edits can be reverted the same way. Nothing else in the
codebase references `LONG_FORM_CHUNK_CONFIG`, so removing it is a clean,
single-file revert.

## Remaining quality limitations

- The 240/320/3 config is exactly the number pair I proposed as a
  hypothesis in the blocked report, now backed by your one benchmark run —
  it has not been benchmarked at multiple chunk-boundary settings (e.g.
  280/360/3 or 220/300/2) to confirm 240/320/3 is a local optimum rather
  than just "better than the old default." That further tuning was not
  attempted here, consistent with "avoid unrelated refactors" and the
  "minimal production changes" framing of this handoff.
- No listening/quality verification has been done by me (or reported to me)
  for the new, larger-chunk boundaries specifically — the benchmark numbers
  you shared cover timing/integrity/validity, not subjective prosody at
  chunk boundaries. `max_sentences_per_chunk=3` means chunk transitions
  happen roughly 3x less often, which should if anything read as *more*
  natural (fewer synthetic pauses inside what would otherwise be one
  paragraph), but this is reasoning, not a listening test.
- `pytest` has not actually been run against these edits. Static review and
  syntax-checking give me reasonable confidence, but per this task's own
  ROLLBACK clause, that confidence is not a substitute for the real test
  run.

## Status: EXECUTED (pending your pytest run + optional listening check)

Files changed: `backend/services/long_form_service.py`,
`backend/tests/test_long_form.py`.
