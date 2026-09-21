# Task 3.5 — Verification: BLOCKED

**Status: BLOCKED, not VERIFIED_PASS, not FAILED.** No test was run, no
benchmark was run, no audio was generated or listened to. None of the five
RUN steps could be executed this turn. Nothing was modified — per the
"DO NOT modify code unless verification exposes a regression" instruction,
and since no verification happened, nothing was touched.

## Exact evidence

`device_bash` — the only way this session can run Python/pytest on your
machine — was tested at the start of this turn and failed with the same
error as every attempt across this entire session:

```
sandbox-helper: no Plan9 drive shares mounted under /mnt/.virtiofs-root/shared
[Note: mnt/Tool Dich Cho Khach failed to mount and cannot be reached from
this shell. Those connected folders are still reachable via device_list_dir
/ device_stage_files / device_commit_files, by their paths on this device.]
A Windows update released September 8 prevents Claude's workspace from
reaching your files. We're tracking this issue. Claude Code is unaffected.
```

File read/write access (`device_list_dir` / `device_stage_files` /
`device_commit_files`) still works — I can confirm the two files changed in
the previous turn are still correctly on disk (spot-checked, unchanged since
last commit), but confirming *code is present* is not the same as
confirming *tests pass*, and I have not conflated the two.

## What each RUN step needs, and why I can't do it from here

| # | Step | Blocker |
|---|---|---|
| 1 | Targeted long-form tests | Needs `pytest` execution — `device_bash` down |
| 2 | Full backend tests | Same |
| 3 | Full regression suite | Same |
| 4 | Production benchmark run | Needs Python + GPU execution — same, plus GPU access this session never had |
| 5 | Generate 2-3 long-form samples | Same execution blocker, plus: even with execution restored, I have no audio-playback capability in this session — "sound acceptable" / "no obvious voice/prosody regression" is a human-listening judgment I cannot make myself under any circumstance here. At most I could programmatically inspect a generated WAV for gross anomalies (silence gaps at chunk boundaries, clipping, discontinuities) as a partial automated proxy — that is not the same as listening, and I'd say so explicitly rather than present it as equivalent. |

## What's ready to run, the moment execution is available (to you, or to me)

Everything needed for items 1-4 already exists on disk from the prior two
turns, untouched:

```powershell
# 1. Targeted
$env:PYTHONPATH='prototype'; & .\external\OmniVoice\.venv312\Scripts\python.exe -m pytest backend/tests/test_long_form.py -v

# 2. Full backend
$env:PYTHONPATH='prototype'; & .\external\OmniVoice\.venv312\Scripts\python.exe -m pytest backend/tests -v

# 3. Full regression (backend + prototype)
$env:PYTHONPATH='prototype'; & .\external\OmniVoice\.venv312\Scripts\python.exe -m pytest backend/tests prototype/tests -v

# 4. Production benchmark with the applied 240/320/3 config
$env:PYTHONPATH='prototype'; & .\external\OmniVoice\.venv312\Scripts\python.exe external\OmniVoice\benchmark_production_long_form.py
```

Item 4's script (`external/OmniVoice/benchmark_production_long_form.py`,
delivered in the prior turn) runs the `current_default` (100/160/1) and
`proposed` (240/320/3) configs back-to-back against the real
`TTSManager`/`OmniVoiceProvider` path and writes
`benchmark_production_long_form_result.json` with wall time, RTF, chunk
count, chunk-overhead breakdown, peak VRAM, text-integrity, and audio-validity
for both. Since 240/320/3 is now the config actually wired into
`long_form_service.py`, running it a second time on the real corpus is what
item 4 is asking for — I have not run it, so I have no fresh number to
report beyond the one you already supplied last turn (15→7 chunks,
26.613s→16.727s, RTF 0.2895→0.1822).

For item 5, run the existing app end-to-end (submit 2-3 real long Vietnamese
texts through the long-form API/UI, or via the harness script's own output
WAVs under `external/OmniVoice/benchmark_production_long_form_work/*/`) and
listen yourself, or send me the resulting WAV files/a description of what
you hear and I'll factor that in.

## Nothing was modified

No source file was touched this turn. `backend/services/long_form_service.py`
and `backend/tests/test_long_form.py` are exactly as committed and verified
in the prior turn (spot-checked below).

## Spot-check of prior turn's state (read-only, no changes)

`device_list_dir` on `backend/services/` and `backend/tests/` (no staging,
no edits — just a listing) shows both files at exactly the size and mtime
this session committed them at last turn:

- `backend/services/long_form_service.py` — 15,213 bytes, mtime 1789491934441
- `backend/tests/test_long_form.py` — 19,049 bytes, mtime 1789491935182

Both match the prior turn's verified commit exactly. No drift, no
out-of-band edit, nothing for me to have accidentally clobbered.

## Answer to the VERIFY checklist

Every item on the VERIFY list requires either running code or listening to
audio, neither of which is possible from here right now:

- all tests PASS — **not run**
- production uses 240/320/3 — **confirmed by source inspection** (see spot-check above; this one I *can* answer: `LONG_FORM_CHUNK_CONFIG = ChunkingConfig(target_chars=240, max_chars=320, max_sentences_per_chunk=3)` is still the object referenced by both call sites in `_run()`, unchanged since last turn)
- no missing/duplicated text — **not run** (would come from the text-integrity assertions in the test suite or a fresh benchmark run, neither executed)
- valid WAV/MP3 — **not run**
- chunk boundaries sound acceptable — **not run**, and not something I can determine myself even with execution restored (see table above)
- no obvious voice/prosody regression — **not run**, same limitation
- no crash/OOM — **not run**
- performance near ~0.18 RTF / ~37% — **not run**; the only number I have is the one you supplied last turn, which I'm not re-reporting as if it were freshly measured this turn

## RETURN

**BLOCKED.** Not VERIFIED_PASS (nothing was verified), not FAILED (nothing
failed either — nothing ran). Re-run this verification once `device_bash`
reaches your machine again (I have no way to predict when, and retrying it
repeatedly this turn would not change the outcome — it's the same
Windows-update-level issue that's persisted all session), or run the four
commands above yourself and share the output, plus a listening pass on 2-3
generated samples, and I'll fold the real results into the verification
report immediately.
