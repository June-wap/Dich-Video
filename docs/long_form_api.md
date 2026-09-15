# CP0.3B-5 — Long-form job API

Run the existing single-worker backend with `scripts/run_backend.ps1`. Create
one voice profile with the B-4 upload API first. All jobs require its profile ID.

## Contract

`POST /api/tts/long-form` accepts:

```json
{
  "text": "Văn bản dài cần đọc…",
  "language": "vi",
  "profile_id": "UUID returned by the profile API",
  "speed": 1.0,
  "format": "wav"
}
```

HTTP 202 returns immediately after validation and queue admission:

```json
{"job_id":"UUID","status":"QUEUED","progress_percent":0}
```

`GET /api/tts/long-form/{job_id}` returns only `job_id`, `status`,
`progress_percent`, and optional `audio_url` or safe `error`. No source text,
chunk details, filesystem paths, CUDA state or conditioning data are exposed.
States are QUEUED → RUNNING → COMPLETED / FAILED / CANCELLED. A queued job can
transition directly to CANCELLED. Terminal states are immutable. Progress is
monotonic; 100 means the final validated artifact has been published.

`DELETE /api/tts/long-form/{job_id}` cooperatively cancels a queued/running job.
Queued cancellation is immediate. Running cancellation returns RUNNING until
the current native operation finishes; poll GET for CANCELLED. Generation is
checked between chunks and before merge. A late cancel during merge/export
discards staged output. A chunk failure takes precedence over cancellation and
remains FAILED. Repeated DELETE on a terminal job returns its existing state.

Final audio uses the existing `GET /api/audio/{artifact_id}` UUID filename route.
The output is always validated 24 kHz mono WAV first. For format `mp3`, a
successful encoding adds MP3; if encoding fails the job completes with a WAV
audio URL instead. Consumers should use the returned URL's extension.

## Validation and ownership

- Nonblank string text, up to 100,000 characters per request; no extra fields.
- Only canonical verified languages, native speed 1.0, and wav/mp3 formats.
- A valid existing profile is mandatory; unavailable profiles never fall back
  to an automatic voice.
- A profile reservation is acquired atomically once at submission and retained
  while queued/running. DELETE profile returns HTTP 409 / PROFILE_IN_USE until
  every reserving job has terminated. Cancellation/failure releases reservations.
- One FIFO worker owns long-form jobs; one shared application inference lock
  excludes short TTS, profile preparation and clone tests during the whole job.
  Internal unload also uses this lock. Model/provider/profile objects are reused.
- Lifespan shutdown cancels outstanding jobs, waits for the worker, then unloads
  the provider. It does not interrupt a native CUDA operation mid-chunk.

## Reuse and integrity

`LongFormTTSService` invokes `TTSManager.synthesize_long_text` with a clone
callback bound to the existing provider and exact profile object. The legacy
core voice selector only resolves that provider; the callback never calls
normal/automatic voice synthesis or creates conditioning.

Chunking uses `core.long_text` and existing defaults (220 target characters,
340 maximum, 2 sentences). Sentence splitting retains decimals and closing
quotes. Paragraph/line whitespace is normalized; ordered non-whitespace source
characters must be identical before inference. This verifies source delivery,
not whether the generated speech audibly pronounced every word.

Each chunk is decoded and validated before it can enter the merge list. There
are no retries in this API: any generation/validation failure fails the job,
and missing chunks never reach merge. Ordered merge uses existing CP0.2E pause
and boundary settings, without changed inference steps or conditioning.

Staging and chunk files are inside a private subdirectory that the UUID-only
audio route cannot address. Only validated final artifacts move into the public
output directory. Terminal jobs release their full source text/profile references.

## Limits

Job registry and profiles are process-local; restarting loses job/profile state.
One backend worker/process is required. There is no persistence, resume,
recovery, cross-process coordination or automatic retry. The in-memory registry
has no eviction/queue quota in this checkpoint. Long requests can delay short
TTS and profile preparation. Cancellation/shutdown must wait for native work.

The real B-5 smoke uses one 308-word Vietnamese job and the B-4 verified
reference. It does not establish 10,000-word or million-word capacity or
perceptual speaker consistency. Human listening is required; use the untouched
checklist in `reports/cp03b5_listening`.

CP0.3B-6 (Persistence / Resume / Recovery) is not implemented.
