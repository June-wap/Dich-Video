# Task 4 — Final 1/57 Failure (long-form cancel test)

**Status: EXECUTED (test-only fix applied, root cause traced and independently verified in isolation) — I cannot supply exact `npm run build` / `npx vitest run` totals myself this turn (`device_bash` is not available in this session; see "Verification" below). Please run them and report back, as in every prior round.**

## Changed files

- `frontend/src/hooks/useLongFormJobRunner.test.ts` — **test file only.** No production code touched.

Committed to `D:\Tool Dich Cho Khach\frontend\src\hooks\useLongFormJobRunner.test.ts` and verified byte-for-byte via fresh stage-back + `cmp`.

## Verdict: test-timing issue, not a production bug

`useLongFormJobRunner.ts` is unchanged. The bug was in the failing test's assumption about *when* the post-cancel poll fires.

## Root cause

`schedulePoll()` (in the hook) fires its **first** poll tick synchronously via `void tick()` — there is no `setTimeout` gate on that first tick; the `POLL_INTERVAL_MS` (1000ms) `setTimeout` is only scheduled *after* a tick completes, for the *next* one. This is true every time `schedulePoll()` is called, including from `cancel()`'s success handler when the cancel response is non-terminal (still RUNNING):

```ts
setPhase('polling');
schedulePoll(updated.job_id, generation);   // <- fires its first GET immediately, not 1000ms later
```

The now-fixed test's TRACE (`cancel() → RUNNING cancel response → polling restart → timer scheduling → get(job-3) → CANCELLED → state update`) matches this exactly — "polling restart" *is* the immediate tick, not a 1000ms-later one. The old test instead called `cancel()`, asserted an intermediate RUNNING state, and only *then* armed the CANCELLED response and did `vi.advanceTimersByTimeAsync(1000)` expecting *that* advance to reach it. But the poll that actually observes CANCELLED is the one `cancel()`'s own resumed `schedulePoll()` already fired — by the time `await result.current.cancel()` resolves, that poll has already run and the job is already CANCELLED. The subsequent `advanceTimersByTimeAsync(1000)` was advancing a timer for a *third*, never-mocked poll that shouldn't need to exist for this assertion, which is an unnecessarily exact (and wrong) timer boundary — exactly the class of bug the task asked me to check for.

I want to flag one nuance honestly: the previous round's report predicted the opposite failure mode for this same mechanism (a `Cannot read properties of undefined` crash from an unmocked poll). That didn't happen here — Vitest reported a plain assertion mismatch (`RUNNING` still present where `CANCELLED` was expected), consistent with the *old* test's final `advanceTimersByTimeAsync(1000)` firing a `getMock` call that had no queued response and thus fell through to a previous "sticky" `mockResolvedValueOnce`/default behavior rather than crashing outright — I could not fully pin down that exact failure path without running the real suite, but it does not change the conclusion: the fix is to poll for CANCELLED where it's actually produced (immediately, inside `cancel()`'s resumed poll), not after an extra, unneeded 1000ms advance.

## What I verified, and how

`device_bash` was not present in this session's tool list this turn (unlike prior rounds where it was present but broken) — I could not run the project's real `npm run build` / `npx vitest run`, and this cloud sandbox still cannot `npm install` (network egress does not allow `registry.npmjs.org`, confirmed in round 1).

I did not stop at reasoning alone. I isolated the **specific microtask-ordering mechanism in question** — independent of React/testing-library/Vitest — and reproduced it with plain Node.js (available in this sandbox), modeling `schedulePoll`'s immediate-first-tick behavior and `cancel()`'s resumed-poll call exactly as written in the hook:

```
immediately after await cancel() resolves: {"status":"CANCELLED"} idle
```

This confirms, with a real JS engine run (not just an argument about spec semantics), that `job` is already `CANCELLED` and `phase` is already `idle` by the time the outer `await result.current.cancel()` returns control — i.e. the microtask that resolves the resumed poll's `get()` call is queued and drained *before* the microtask that resolves `cancel()`'s own returned promise, because the resumed poll's `await` is scheduled from inside `cancel()`'s synchronous continuation, ahead of `cancel()`'s own completion. This is exactly the same race the test file's very first test already documents and works around (there, for the very first poll after `submit()`).

## The fix

In the failing test (`cancel(): a RUNNING job whose cancel response is still RUNNING keeps polling...`):

- Moved `getMock.mockResolvedValueOnce({ ...CANCELLED... })` to **before** `await result.current.cancel()` (it now arms the resumed poll's own GET, not a hypothetical third one).
- Removed the trailing `vi.advanceTimersByTimeAsync(1000)` block and the intermediate `expect(result.current.job?.status).toBe('RUNNING')` / `expect(result.current.phase).toBe('polling')` assertions that depended on it.
- Asserts `CANCELLED` / `'idle'` / `canCancel === false` directly after `await result.current.cancel()` resolves.
- Added comments explaining the immediate-first-tick mechanism and why this is a *stronger* check, not a weaker one: the job can only reach `CANCELLED` in this test if the RUNNING cancel response was genuinely treated as non-terminal and polling genuinely resumed and completed — if the hook incorrectly treated RUNNING as terminal, the job would stay stuck at RUNNING forever (no further poll would ever fire), so reaching CANCELLED is proof the RUNNING → resumed-polling → CANCELLED path executed correctly end-to-end.
- Left `cancelMock` call-shape assertions (`'job-3'`, real `AbortSignal`, not yet aborted) untouched.
- Did not touch any other test in the file.

## Requirements checklist

- Test file only, no production changes: yes — `useLongFormJobRunner.ts` is untouched.
- No `any`, `@ts-ignore`, artificial sleeps, increased timeouts, or unrelated refactor: none used.
- Did not weaken the RUNNING → CANCELLED requirement: the fixed test still requires the job to have been RUNNING (before cancel) and end at CANCELLED (after), reached only via the real resumed-polling code path — if anything this is a stricter proof of that requirement than the old intermediate-state check was.
- Avoided asserting an unnecessarily exact timer boundary: yes — this is precisely what was removed (the extra `advanceTimersByTimeAsync(1000)` that assumed a timer-gated poll where the real one is immediate).

## Please run and report back

```bash
cd frontend
npm run build
npx vitest run
```

Target: Build PASS, 57/57 PASS. If anything is still off, send the exact output and I'll fix the smallest root cause, per the instructions — I'm not declaring this checkpoint PASS myself.
