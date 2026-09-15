# CP0.3B-5 — Long-form TTS Job API Report

STATUS:
PASS_WITH_LIMITATIONS

ARCHITECTURE:
- Layered execution:
  `POST /api/tts/long-form` → `LongFormTTSService.submit()` (validates request, atomically reserves VoiceProfile via `VoiceProfileService.reserve_profile()`, registers immutable queued snapshot, pushes `job_id` to FIFO queue, returns HTTP 202).
- Background worker (`_worker` thread) acquires `ProviderService.inference_lock` (shared with short TTS and clone test/creation) to guarantee single-consumer GPU access on the 6 GB RTX 4050.
- Worker executes `TTSManager.synthesize_long_text()` configured with a bound clone synthesizer closure capturing the pre-existing `VoiceProfile` object and verifying provider identity and model object identity.
- On completion, generated chunks are validated and merged sequentially via existing conservative boundary DSP (`merge_segments`).
- Final 24 kHz mono WAV is validated and published to backend output storage under a random UUID artifact identifier, accessible via `GET /api/audio/{artifact_id}`.
- In-memory job registry tracks job state monotonically without SQLite (persistence deferred to CP0.3B-6).

ENDPOINTS:
- `POST /api/tts/long-form`: Submits long-text job. Returns HTTP 202 with `job_id` and initial status `QUEUED`.
- `GET /api/tts/long-form/{job_id}`: Retrieves public status (`status`, `progress_percent`, and `audio_url` on completion or `error` on failure).
- `DELETE /api/tts/long-form/{job_id}`: Issues cooperative cancellation. If queued, transitions immediately to `CANCELLED`. If running, signals cooperative cancellation so current provider call finishes safely before stopping.
- `GET /api/audio/{artifact_id}`: Serves final published audio artifacts.

JOB MODEL:
- States: `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`.
- Transitions:
  - `QUEUED` → `RUNNING` → `COMPLETED`
  - `QUEUED` → `RUNNING` → `FAILED`
  - `QUEUED` → `CANCELLED`
  - `QUEUED` → `RUNNING` → `CANCELLED`
- Monotonic progress: 0% → 95% (during chunk generation) → 100% (upon successful publication).
- Privacy: Public responses expose only high-level status, progress percentage, and final audio URL or error body; no internal chunk paths, CUDA telemetry, or customer synthesis text.

SCHEDULING:
- In-memory FIFO queue (`queue.Queue`) processed by a single daemon worker thread (`long-form-tts`).
- Device serialization: Execution holds `ProviderService.inference_lock` during the entire job.
- Short TTS (`POST /api/tts`) and clone tests serialize behind the active long-form job through the same shared lock, preventing VRAM collisions on the 6 GB RTX 4050.
- Exactly one inference job active at a time; subsequent requests wait safely in `QUEUED` state.

TEXT INTEGRITY:
- Text integrity check verified before generation: normalized text of all planned chunks exactly matches normalized original text (`"".join(text.split()) == "".join("".join(chunk.text.split()) for chunk in chunks)`).
- Full Vietnamese diacritics, decimal numbers (e.g. `3.14`), currency (`12.500`), punctuation marks (`“...”`, `;`, `:`, `?`, `!`), and paragraph line breaks are preserved in the chunk plan without loss, duplication, or reordering.
- Missing text at backend orchestration layer: 0
- Duplicate text at backend orchestration layer: 0
- Order errors: 0

CHUNK ENGINE:
- Reused proven `prototype/core/long_text.py` (`build_chunks`, `normalize_paragraphs`, `split_sentences`).
- Sentence-aware and paragraph-aware chunking preserving natural punctuation boundaries.
- Conservative chunk targets: target_chars=220, max_chars=340, max 2 sentences per chunk.
- Chunks maintain strict index sequencing: input order == generation order == merge order.

VOICE PROFILE:
Profile ID: 94b37349-e0ed-4aad-b42f-e196c82aad0e
Profile creation count: 1 (created once via `POST /api/voices/profiles` prior to job)
Profile creation during job: 0 (zero preparation calls inside chunk loop)
Unique profiles used: 1
Chunk reuse count: 8 (all 8 chunks used the exact same in-memory VoiceProfile object)
Active profile leasing: `reserve_profile` increments `active_jobs`; deletion of active profile rejected with HTTP 409 `PROFILE_IN_USE`.

MODEL:
Provider instances: 1
Model load count: 1 (loaded once, retained in `READY` state, zero reloads across chunks)

BOUNDARY PROCESSING:
- Reused `prototype/core/audio_utils.py` (`merge_segments`, `select_pause_ms`, `BoundaryDSPConfig`).
- Punctuation-aware pause insertion (comma: 120-180ms, semicolon: 200-280ms, colon: 220-300ms, period: 300-400ms, question: 400-500ms, exclamation: 350-450ms, paragraph: 500-700ms).
- Conservative boundary DSP: 3 ms edge fade, silence trim, crossfade disabled by default, loudness gain disabled by default.

REAL CUDA LONG-FORM SMOKE:
Words: 308
Characters: 1393
Chunks: 8
Generation time: 2228.29 s (wall time: 2228.59 s)
Final duration: 76.30 s
RTF: 29.208
Hardware: NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)
Interpreter: Python 3.12.10 (`external/OmniVoice/.venv312/Scripts/python.exe`)
PyTorch: 2.8.0+cu128, CUDA: 12.8

CHUNK VALIDATION:
Successful: 8
Failed: 0
Missing: 0
Duplicates: 0
Order violations: 0

FINAL AUDIO:
Sample rate: 24000 Hz
Channels: 1 (mono)
Duration: 76.30 s
Finite: True (no NaN, no Inf)
Decodable: True (verified via SoundFile full sample decode)

PERFORMANCE:
- Total words: 308
- Total characters: 1393
- Total chunks: 8
- Total generation time: 2228.29 s
- Final audio duration: 76.30 s
- Real-Time Factor (RTF): 29.208 (OmniVoice flow matching on laptop RTX 4050)
- VRAM stability: Steady within 6 GB VRAM budget throughout all 8 chunks without OOM.

SECURITY:
- Random UUID4 generation for all job IDs and final artifact IDs.
- Path traversal protection: Client cannot supply arbitrary filesystem paths; private staging (`long_form_private/<job_id>`) isolated from audio serving directory.
- Temporary cleanup: Private staging directory deleted immediately upon job completion, failure, or cancellation.
- Profile deletion race protection: Active profile cannot be deleted while jobs are queued or running (`PROFILE_IN_USE`).

PRIVACY:
- Customer text redaction: Full long-form synthesis text and reference transcripts are never written to server logs.
- Safe logging only: `job_id`, `profile_id`, `language`, `chunk_count`, `duration`, `status`, error codes.
- Exception normalization: Internal tracebacks and provider error messages are masked behind standard application error codes (`GENERATION_FAILED`, etc.).

TESTS:
Backend: 145 passed, 0 failed in 7.31s (`pytest backend/tests -v`)
Targeted: 92 passed, 0 failed in 1.63s (`pytest prototype/tests/test_omnivoice_*.py prototype/tests/test_long_text*.py prototype/tests/test_audio_boundary.py -v`)
Broader: 242 passed, 0 failed in 13.53s (`pytest backend/tests prototype/tests -v`)
CUDA long-form: PASS (8/8 chunks generated, 1 model load, 1 profile, 0 creations during job, RTF 29.208, final WAV 76.3s)

HUMAN LISTENING:
COMPLETED:
- Speaker Consistency: PASS
  - REFERENCE: Đúng giọng mẫu
  - BEGINNING: Cùng người nói với reference
  - MIDDLE: Cùng người nói với reference và beginning
  - END: Cùng người nói với reference, beginning và middle
  - Voice switch: Không có
- Content:
  - Nuốt câu: Có (mô hình acoustic bỏ sót câu ở một số chunk)
  - Lặp câu: Không
  - Thiếu từ: Có (hiện tượng nuốt chữ trong câu)
  - Phát âm: Có phát âm sai từ ngữ tiếng Việt
- Quality:
  - Robotic: Không
  - Ngắt câu bất thường: Không
  - Click/pop: Không
  - Méo tiếng: Có (xuất hiện biến dạng âm thanh cục bộ)

FILES CREATED:
- `backend/schemas/long_form.py`
- `backend/services/long_form_service.py`
- `backend/api/long_form.py`
- `backend/tests/test_long_form.py`
- `scripts/smoke_long_form_api.py`
- `reports/cp03b5_long_form_smoke.json`
- `reports/cp03b5_cuda_smoke.log`
- `reports/cp03b5_listening/long_form.wav`
- `reports/cp03b5_listening/beginning.wav`
- `reports/cp03b5_listening/middle.wav`
- `reports/cp03b5_listening/end.wav`
- `reports/cp03b5_listening/input.txt`
- `reports/cp03b5_listening/listening_checklist.md`
- `reports/cp03b5_long_form_tts_job_api.md`

FILES CHANGED:
- `backend/api/router.py` (registered `long_form_router`)
- `backend/main.py` (initialized `LongFormTTSService` lifecycle and clean shutdown)
- `backend/services/voice_profile_service.py` (profile reservation leasing `reserve_profile` / `release_profile` and `PROFILE_IN_USE` check)

PRODUCTION BEHAVIOR CHANGES:
- New long-form TTS job submission, polling, and cooperative cancellation APIs are available at `/api/tts/long-form`.
- Active VoiceProfiles are leased during long-form jobs, preventing premature deletion during inference.
- Shared provider inference lock serializes short TTS and long-form jobs safely.

LIMITATIONS:
- Upstream OmniVoice acoustic synthesis limitations: While backend orchestration preserves 100% of chunk texts and guarantees 0 missing/duplicate chunks and strict speaker identity consistency, the upstream OmniVoice 0.2.1 flow-matching generation exhibited word/sentence skipping ("nuốt câu", "thiếu từ"), Vietnamese mispronunciation, and audio distortion ("méo tiếng").
- In-memory registry only: Active and queued jobs are lost upon backend restart (persistence and crash recovery deferred to CP0.3B-6).
- Single GPU worker: Serialized execution to respect the 6 GB VRAM ceiling.

NEXT:
CP0.3B-6 — Persistence / Resume / Recovery
