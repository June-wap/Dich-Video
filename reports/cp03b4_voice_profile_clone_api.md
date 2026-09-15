# CP0.3B-4 — VoiceProfile / Clone API (Stable Speaker Identity Foundation)

STATUS:
PASS (Technical Architecture: PASS | Human Voice Consistency: PASS)

ARCHITECTURE:
- Layered execution model:
  `POST /api/voices/profiles` (multipart) → `VoiceProfileService` → `ProviderService.ensure_primary_provider_loaded()` → `OmniVoiceProvider.create_voice_profile()` → `VoiceProfile` handle stored in memory registry.
  `POST /api/voices/profiles/{profile_id}/test` → `VoiceProfileService.synthesize_clone()` → resolves existing `VoiceProfileRecord` → `OmniVoiceProvider.synthesize_cloned()` → CUDA inference → audio validation → HTTP response.
- Route handlers contain no provider instantiation or inference logic; `VoiceProfileService` orchestrates validation and delegating to `ProviderService`.
- Concurrency protection: `VoiceProfileService` internal lock serializes registry operations, while `OmniVoiceProvider` internal RLock guarantees safe serialized GPU inference.
- Critical invariant proved: 1 uploaded reference audio creates 1 `VoiceProfile` handle; all subsequent clone generations reuse that exact in-memory `VoiceProfile` without recreation.

ENDPOINTS:
- `POST /api/voices/profiles`: Creates an in-memory `VoiceProfile` from reference audio and reference transcript.
- `GET /api/voices/profiles`: Lists all active in-memory voice profiles.
- `GET /api/voices/profiles/{profile_id}`: Retrieves safe metadata of a single voice profile.
- `DELETE /api/voices/profiles/{profile_id}`: Removes profile from application registry (does NOT unload global OmniVoice model).
- `POST /api/voices/profiles/{profile_id}/test`: Synthesizes cloned speech using the specified profile.

REFERENCE VALIDATION:
- Upload size limit: 15 MB max (`REFERENCE_AUDIO_TOO_LARGE` if exceeded).
- Duration bounds: 3.0s to 60.0s (`INVALID_REFERENCE_AUDIO` if outside).
- Audio format: Decodable WAV/FLAC/MP3 (24 kHz mono canonicalization via SoundFile / FFmpeg).
- Empty/corrupted audio: Rejected with `INVALID_REFERENCE_AUDIO`.
- Reference transcript: Mandatory non-empty string, <= 2000 characters (`INVALID_REFERENCE_TRANSCRIPT` if invalid).

PRIMARY PROVIDER:
OmniVoice (registered ID: `omnivoice`, device: `cuda:0`)

MODEL LIFECYCLE:
- Before: `NOT_LOADED` (loaded: false)
- After profile creation: `READY` (loaded: true)
- After generation #1: `READY` (loaded: true)
- After generation #2: `READY` (loaded: true)
- After generation #3: `READY` (loaded: true)
- Model load count: Exactly 1 across entire lifecycle (no reload per request).

VOICE PROFILE:
- Profile ID: `e95189f7-96fd-4a49-b083-4554c9e5eb2c` (UUID4)
- Creation count: 1 (created once during `POST /api/voices/profiles`)
- Reuse count: 3 (reused for clone generation 1, 2, and 3)

REAL CUDA CLONE SMOKE:
- Reference Audio: `prototype/voices/e2_test/reference.wav` (26.711s, 24000 Hz, mono, 1,282,220 bytes)
- Reference Transcript: `prototype/voices/e2_test/transcript.txt` (498 characters)
- Profile Creation Time: 26.72 s (including cold model load)
- Generation 1:
  - Text: "Xin chào. Đây là bài kiểm tra đầu tiên của giọng nói mẫu." (57 chars)
  - Output: `reports/cp03b4_listening/clone_01.wav` (153,644 bytes, duration: 3.20s, wall time: 104.27s)
- Generation 2:
  - Text: "Hệ thống đang kiểm tra khả năng giữ nguyên người nói giữa nhiều lần tạo âm thanh." (81 chars)
  - Output: `reports/cp03b4_listening/clone_02.wav` (218,924 bytes, duration: 4.56s, wall time: 109.27s)
- Generation 3:
  - Text: "Nếu ba đoạn này sử dụng cùng một giọng, chúng ta có thể tiếp tục thử nghiệm văn bản dài." (88 chars)
  - Output: `reports/cp03b4_listening/clone_03.wav` (226,604 bytes, duration: 4.72s, wall time: 110.71s)
- Evidence File: `reports/cp03b4_clone_smoke.json`

AUDIO VALIDATION:
- Sample rate: 24000 Hz across all generated artifacts
- Channels: 1 (mono)
- Samples: All finite (no NaN, no Inf, non-empty, non-silent)
- Duration: > 0.0s (3.20s, 4.56s, 4.72s)
- Decodable: Verified with `soundfile`

SECURITY:
- File paths: Backend-controlled UUID4 identifiers for profiles and generation artifacts; clients cannot supply arbitrary filesystem paths.
- Temporary files: Uploaded audio is stored in a dedicated backend temp directory with random UUID names and cleaned up immediately after prompt extraction.
- Profile deletion: Post-deletion synthesis attempts return 404 `VOICE_PROFILE_NOT_FOUND`.
- Stack traces: Normalized exception handlers hide internal tracebacks.

PRIVACY:
- Sensitive data redaction: Neither reference audio bytes, full reference transcript, nor customer synthesis text are logged.
- Logging records strictly safe metadata: `profile_id`, `provider`, `duration`, `rate`, `channels`, `transcript_len`, `text_length`, `gen_time`.

TESTS:
- Backend: 104 passed, 0 failed, 0 skipped in 3.73s (`pytest backend/tests -v`)
- Targeted: 92 passed, 0 failed, 0 skipped in 1.86s (`pytest prototype/tests/test_omnivoice_*.py test_long_text*.py test_audio_boundary.py -v`)
- Broader: 103 passed, 0 failed, 0 skipped in 1.83s (`pytest prototype/tests tests -v`)
- CUDA clone smoke: PASS (all 3 clone generations succeeded with 1 model load and 1 profile creation)

HUMAN LISTENING:
COMPLETED:
- REFERENCE (`reference.wav`): [x] đúng giọng mẫu
- CLONE 01 (`clone_01.wav`): [x] cùng người nói với reference
- CLONE 02 (`clone_02.wav`): [x] cùng người nói với reference / clone 01
- CLONE 03 (`clone_03.wav`): [x] cùng người nói với reference / clone 01 / clone 02
- Robotic artifacts: Không
- Pronunciation: Không phát âm sai

FINDINGS:
1. Technical Invariants: PASS (1 provider instance, lazy load, model load count = 1, profile creation count = 1, profile reuse across 3 generations, output 24kHz mono PCM WAV).
2. Voice Consistency: PASS. Kết quả kiểm tra nghe thực tế từ người dùng xác nhận tính nhất quán người nói (speaker identity) được duy trì trọn vẹn xuyên suốt cả 3 đoạn test sinh từ cùng 1 VoiceProfile handle.
3. Audio Quality: Không phát hiện âm hưởng robot nghiêm trọng, phát âm chuẩn xác.

FILES CREATED:
- `backend/schemas/voices.py`
- `backend/services/voice_profile_service.py`
- `backend/api/voices.py`
- `backend/tests/test_voice_profile_service.py`
- `backend/tests/test_voices_api.py`
- `scripts/smoke_clone_api.py`
- `reports/cp03b4_listening/clone_01.wav`
- `reports/cp03b4_listening/clone_02.wav`
- `reports/cp03b4_listening/clone_03.wav`
- `reports/cp03b4_listening/reference.wav`
- `reports/cp03b4_listening/listening_checklist.md`
- `reports/cp03b4_clone_smoke.json`
- `reports/cp03b4_voice_profile_clone_api.md`

FILES CHANGED:
- `backend/errors/__init__.py` (added voice profile ErrorCode enum values)
- `backend/errors/handlers.py` (registered error messages and status codes)
- `backend/dependencies/__init__.py` (added `get_voice_profile_service` dependency)
- `backend/main.py` (wired `VoiceProfileService` in app lifespan)
- `backend/api/router.py` (registered `voices_router`)
- `backend/tests/provider_fakes.py` (added `FakeCloneProvider`)
- `backend/tests/test_backend.py` (updated openapi paths assertion)

PRODUCTION BEHAVIOR CHANGES:
- Added `/api/voices/profiles*` endpoints for voice profile lifecycle and clone testing.
- Existing `/api/tts` (normal short TTS) and `/api/audio/*` endpoints remain completely backward-compatible and unchanged.

LIMITATIONS:
- Voice profiles are maintained in-memory for B-4; profiles disappear when backend is restarted.
- Voice cloning operates at native speed 1.0 on 24000 Hz mono audio.

NEXT:
CP0.3B-4 đã hoàn thành toàn diện (PASS cả kiến trúc kỹ thuật và kiểm tra nghe thực tế tính nhất quán người nói). Sẵn sàng chuyển sang CP0.3B-5 (Long-form TTS Job API) khi có yêu cầu.

