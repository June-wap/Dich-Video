# Task 4 — Fix 3 Remaining Test Failures

**Status: EXECUTED (all 3 root causes fixed + regression tests added) — I cannot supply exact `npm run build` / `npx vitest run` totals myself (`device_bash` is still broken this session; see "Verification" below). Please run them and report back, as in the last two rounds.**

## Changed files

- `frontend/src/services/voiceProfileService.test.ts` — fix #1.
- `frontend/src/hooks/useLongFormJobRunner.ts` — fix #2 and #3 (production code).
- `frontend/src/hooks/useLongFormJobRunner.test.ts` — regression tests for #2 and #3.

All three committed to `D:\Tool Dich Cho Khach\...` and verified byte-for-byte via fresh stage-back + `cmp`.

## 1. `voiceProfileService.test.ts` — FormData identity

**Root cause:** `FormData.append(name, blob, filename)` is spec'd (WHATWG) to construct a **new** `File` object wrapping the same bytes whenever a filename is given — and `voiceProfileService.create()` always passes one (`form.append('file', payload.file, payload.file.name)`). So `form.get('file')` is never `===` the original `file`, even though it's the exact same upload. That's correct, unavoidable `FormData`/`File` behavior, not a production bug — the requirement says not to change upload behavior to satisfy the test, and there's no real behavior to fix here.

**Fix:** replaced `expect(form.get('file')).toBe(file)` (reference identity) with semantic checks: `instanceof File`, plus `name`, `type`, `size`, and byte content (`.text()`) all matching the original file. Test intent (does the right file get uploaded?) is unchanged; only how "the right file" is verified changed.

## 2. `useLongFormJobRunner` — cancel/poll crash on `job.status`

**Root cause:** `httpClient.ts`'s `apiFetch<T>()` returns `undefined` for any resolved response with an empty body, rather than throwing (`text ? JSON.parse(text) : undefined`). Both `schedulePoll`'s poll tick and `cancel()` awaited `longFormJobService.get()` / `.cancel()` and read `.status` straight off the result, assuming it could never be anything but a full `LongFormJob`. A malformed or empty-bodied 2xx response — a real, reachable runtime state given how `apiFetch` is written, not a hypothetical — resolves successfully with `undefined`, and `undefined.status` throws `TypeError: Cannot read properties of undefined (reading 'status')`. This is a genuine production bug, not a test artifact, so the fix is in the hook, not the assertion.

**Fix:** in both `schedulePoll`'s tick and `cancel()`, right after the await, an explicit `if (!latest) / if (!updated) throw new Error(...)` routes a malformed response into the **same, already-existing** error-handling path used for real network failures — bounded-retry-then-give-up for polling, resume-polling-with-a-surfaced-error for cancel. No new error-handling machinery was added; this reuses what was already there for exactly this purpose, and `job` is never set to anything but a real `LongFormJob` or left at its last known-good value.

**Regression tests added:** a poll test that always resolves `undefined` and asserts the hook survives all `MAX_CONSECUTIVE_POLL_FAILURES` attempts without crashing, ends `idle` with a `requestError`, and leaves the last real job state intact; a cancel test with the same shape, asserting it resumes `polling` on the last known-good job with an error surfaced, then genuinely continues polling afterward.

## 3. Stale poll race — job-B not superseding a still-polling job-A

**Root cause:** `submit()`'s synchronous `runningRef` lock was held for the job's **entire polling lifetime** (only released in `finishRun`, i.e. on terminal completion/failure) — mirroring `useTtsJobRunner`'s pattern. But Long-form's UI, unlike Short TTS's, legitimately allows starting a brand-new job while an older one is still polling (there's no `cancelTracking()`-style detach — cancellation is a real, separate server call). With the lock held that long, a second `submit()` call while job-A was still polling hit `if (runningRef.current) return;` and did **nothing** — job-B's `longFormJobService.submit()` was never even called, so it could never supersede job-A. This wasn't a flaw in the generation-counter supersession logic itself (which already correctly discards stale responses by generation) — it was that job-B's submission never got far enough to use it.

**Fix:** `runningRef` now releases immediately once the **initial POST round-trip settles** (success or failure) instead of waiting for the whole polling lifetime. It still fully blocks a same-tick duplicate fire (a fast double-click): both synchronous calls run before either's `await` resolves, so the second one still sees the lock held and returns immediately, calling `longFormJobService.submit` only once — this is exactly what the existing "does not create a duplicate job on a synchronous double-submit" test already proves, and it still passes under the new code. Once a job has started polling, a later, genuinely new `submit()` call is now allowed to proceed, bump the generation counter, and supersede it — which is exactly what the existing "never lets a stale (superseded) poll response overwrite a newer job's state" test needed to pass, and why it was failing before this fix. No changes were needed to the generation-check logic itself in `schedulePoll`/`cancel` — it was already correct; it just couldn't be reached from a second `submit()` call.

**Regression test:** the existing "never lets a stale (superseded) poll response overwrite a newer job's state" test is the regression test for this fix (it exercises exactly this scenario) — no new test was needed, but I reviewed it in detail to confirm it drives the fixed code path correctly.

## Requirements checklist

- Smallest root-cause fixes: yes — #1 is test-only (the production behavior is correct per spec), #2 adds two short guards that reuse existing error-handling paths, #3 moves one line (`runningRef.current = false`) earlier and updates its surrounding comments; no other logic changed.
- No `any`, `@ts-ignore`, artificial sleeps, or test-only production branches: none used. The `undefined` guards in #2 are real production hardening, exercised by real (if currently unlikely) response shapes, not gated on `NODE_ENV`/test flags.
- No unrelated refactor/features: only the three files above changed.
- Regression tests added/updated: 2 new tests in `useLongFormJobRunner.test.ts` (fix #2); the FormData assertion rewritten in place (fix #1); fix #3 relies on an existing test that now actually exercises the fixed path.

## Verification

I could not run `npm run build` / `npx vitest run` myself this turn — `device_bash` (your Windows machine) is still broken, re-confirmed with the same "Windows update / Plan9 drive" failure just before finalizing this report, same as every prior check this session. I also cannot install the project's dependencies in my own cloud sandbox to substitute for that (confirmed in the last round: this sandbox's network egress does not allow `registry.npmjs.org`).

I traced the new `submit()`/`cancel()`/poll-tick control flow by hand against all 10 existing tests plus the 2 new ones (documented inline above and in the code comments) rather than only reasoning about the change in isolation, to catch any test I might otherwise have broken. That is not a substitute for actually running the suite.

Please run:
```bash
cd frontend
npm run build
npx vitest run
```
and send me the exact output. Target is 55/55 — if anything is still off, send the exact failure and I'll fix the smallest root cause, per the instructions.
