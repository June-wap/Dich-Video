# Task 4 — Frontend Integration (Voice Cloning + Long-form TTS)

**Status: EXECUTED — implementation complete. Build/test execution is NOT VERIFIED (see "What I could not verify" below).**

## Context / handoff note

The HANDOFF — TASK 4 message was received truncated (it cuts off mid-sentence at "* Do" in the REQUIREMENTS list, with no further text). Per RULES.txt's checkpoint discipline and this session's standing instruction to proceed on best judgment rather than block on a question no one may be there to answer, I implemented the full scope described by the visible GOAL/VOICE CLONE/LONG-FORM sections and all requirements that *were* visible, using the Task 3 architecture (services + job-runner hooks + thin pages) as the mandatory pattern to mirror. If the cut-off bullet specified something not covered below, flag it and I'll do a follow-up pass.

## What changed

New files:
- `frontend/src/services/voiceProfileService.ts` — real client for `POST/GET/DELETE /api/voices/profiles`, `POST /api/voices/profiles/{id}/test`.
- `frontend/src/services/longFormJobService.ts` — real client for `POST/GET/DELETE /api/tts/long-form`.
- `frontend/src/hooks/useVoiceProfiles.ts` — shared profile-list loader used by both pages.
- `frontend/src/hooks/useLongFormJobRunner.ts` — submit → poll → terminal job-runner hook, plus a real `cancel()`.
- `frontend/src/services/voiceProfileService.test.ts`, `frontend/src/services/longFormJobService.test.ts`, `frontend/src/hooks/useLongFormJobRunner.test.ts` — regression tests (vitest, mirrors the existing `ttsJobService.test.ts` / `useTtsJobRunner.test.ts` style).

Edited files:
- `frontend/src/services/httpClient.ts` — `apiFetch` now passes a `FormData` body through unchanged (no `JSON.stringify`, no `Content-Type` override) for the one real multipart call in the app, `voiceProfileService.create()`. Existing JSON-body behavior is untouched; `httpClient.test.ts`'s existing assertions still hold.
- `frontend/src/hooks/index.ts` — exports the two new hooks.
- `frontend/src/pages/VoiceCloningPage.tsx` — rewritten for the real flow.
- `frontend/src/pages/LongFormPage.tsx` — rewritten for the real flow.

All 11 files were committed to `D:\Tool Dich Cho Khach\...` and verified byte-for-byte via a fresh stage-back + `cmp` diff after every write (the standing practice this session, since `device_commit_files`'s own "written" response is not trusted alone).

## Voice Cloning — real flow

`reference audio → create/load profile → generate test audio → playback/download`, all real:

- File input (no more auto-filled sample file) validates extension (.wav/.mp3) and size (≤15MB, mirrors `REFERENCE_AUDIO_TOO_LARGE`) client-side; the backend remains authoritative and its `ApiError` (e.g. `INVALID_REFERENCE_AUDIO`, `INVALID_REFERENCE_TRANSCRIPT`) is surfaced verbatim on failure.
- Duration is deliberately **not** decoded client-side before upload — the UI states it will be validated server-side, and once a profile is returned, its real `reference.duration_seconds/sample_rate/channels` are displayed.
- "Create Voice Profile" calls `POST /api/voices/profiles` (multipart) directly — no job/poll cycle, since the backend does this synchronously.
- A new "Hoặc dùng hồ sơ đã có" panel lets the user skip creation and jump straight to the preview/test step with any existing profile from `GET /api/voices/profiles` (via `useVoiceProfiles`).
- "Tạo bản thử" calls `POST /api/voices/profiles/{id}/test`, which is also synchronous (no polling) — result renders through `AudioPlayer`'s real `src`/`format` props (native `<audio controls>`, real `<a download>`).
- The Human Review accept/reject UI is unchanged (it's a legitimate manual QA gate, not mock data) and gates the final "Xong — Xem trong Voice Library" action, which just navigates to `/voices` since the profile is already persisted server-side at creation time — there is no separate "save" step to fake.
- Removed: the auto-fill "Điền nhanh mẫu test" button, "Simulate Failure" button, and the fake 5-30s duration claim (corrected to the real 3-60s range).

## Long-form — real flow

`submit → persisted job → poll progress/status → cancel → completed audio → playback/download`, all real, via the new `useLongFormJobRunner` hook:

- Submit sends exactly `{text, language, profile_id, speed: 1.0, format}` to `POST /api/tts/long-form` — `LongFormRequest` has `extra="forbid"`, so no idempotency key or other extra field is included.
- The voice picker is sourced from real profiles (`useVoiceProfiles`); Long-form has no default-voice concept, so submission is blocked with an `EmptyState` pointing to `/clone` if no profile exists yet.
- Polling uses the job's real `progress_percent` (no simulated timers) and stops on `COMPLETED`/`FAILED`/`CANCELLED`, per the requirement, via the same generation-counter + self-rescheduling-`setTimeout` pattern as `useTtsJobRunner`, adapted with a 1000ms interval.
- Cancel calls the real `DELETE /api/tts/long-form/{job_id}`. Per the actual backend contract, that response can still report `RUNNING` (cancellation is only checked between chunks) — the hook does **not** treat that as terminal; it resumes polling on the same job until the status is actually terminal. Covered by a dedicated test.
- Completed audio plays/downloads through `AudioPlayer`'s real `src`.
- The text limit is 100,000 characters (`LongFormRequest.text` `max_length=100000`), explicitly not the Short TTS 2,000-char limit, and the character counter/validation reflects that.
- Task 3.5's chunk config (240/320/3) is untouched — Task 4 did not modify `backend/services/long_form_service.py` or any chunking logic.
- Removed: the fake "Quality" select (no backend equivalent), the fake file-import tab, the fake "Lưu dự án" button (no backing endpoint), and the Developer Mode screen-jump buttons that simulated PROCESSING/COMPLETED/ERROR states. "Tên dự án" is kept as a purely local, non-submitted label (there is nowhere to send it — `LongFormRequest` has no such field) used only to title the processing/completed cards.
- A `CANCELLED` screen state was added (distinct from the generic error screen) so a user-initiated cancel doesn't read as a system failure.

## Known backend contract limitations carried into the UI (not bugs)

- There is no `GET /api/tts/long-form` list endpoint, so — unlike Short TTS's history table — Long-form has no persisted job history in this build. Not implemented, because there is nothing to call.
- A voice profile's `language` is not a stored property (`VoiceProfile` has no `language` field); the language picker in the clone-test step is described as applying per-test-call, not to the profile itself.

## What I could not verify

`device_bash` is broken this entire session (confirmed broken again immediately before this final commit — same "Windows update / Plan9 drive" failure as every previous check). I could not run:
- `npx tsc --noEmit` (type-check)
- `npm run build`
- `npx vitest run` (including the new and existing test files)
- the dev server, to click through the real flows against a running backend

Everything above was verified by direct source-level review against the exact backend schemas/routes (`backend/schemas/{long_form,voices,tts}.py`, `backend/api/{long_form,voices}.py`, `backend/services/voice_profile_service.py`) and by mirroring the already-working Task 3 patterns (`ttsJobService.ts` / `useTtsJobRunner.ts` / `TTSPage.tsx`) field-for-field and structurally. File persistence to the device was verified byte-for-byte. **Type correctness and actual test pass/fail results are NOT VERIFIED — please run the commands below and report back if anything fails.**

```bash
cd frontend
npm run build        # or: npx tsc --noEmit
npx vitest run
npm run dev           # then manually exercise /clone and /long-form against a running backend
```

If `tsc`/`vitest` surface anything, send me the exact output and I'll fix it — per RULES.txt, I'm not declaring this checkpoint PASS myself; this report is evidence for review, not a self-certified pass.
