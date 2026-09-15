# Independent Verification Report — CP0.3B-3: Short TTS API + Real OmniVoice CUDA

STATUS:
PASS_WITH_LISTENING_REQUIRED

RUNTIME:
- Python: 3.12.10 (tags/v3.12.10:0cc8128) [MSC v.1943 64 bit (AMD64)]
- Interpreter: `D:\Tool Dich Cho Khach\external\OmniVoice\.venv312\Scripts\python.exe`
- PyTorch: 2.8.0+cu128
- CUDA: 12.8 (CUDA available: True)
- GPU: NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)
- OmniVoice: 0.2.1 (editable install from `external/OmniVoice`)
- FastAPI: 0.141.1

ARCHITECTURE:
- Call path: `POST /api/tts` → `TTSService` → `ProviderService` → `OmniVoiceProvider`
- Route handler (`backend/api/tts.py`) does NOT instantiate `OmniVoiceProvider` or call it directly; execution is offloaded via `run_in_threadpool`.
- `ProviderService` strictly owns provider lifecycle and registration.
- Exactly one primary `OmniVoiceProvider` instance is registered during app lifespan and reused across requests.
- `TTSService` owns input validation, provider orchestration, audio validation, and safe MP3 export.
- No `OmniVoiceProvider()` instantiation occurs per HTTP request.

TESTS:
- Backend (`backend/tests`): 86 passed, 0 failed, 0 skipped in 2.63s
- Targeted Core Regression (`prototype/tests/test_omnivoice_*.py`, `test_long_text*.py`, `test_audio_boundary.py`): 92 passed, 0 failed, 0 skipped in 1.93s
- Broader Regression (`prototype/tests tests`): 103 passed, 0 failed, 0 skipped in 2.68s

BACKEND SMOKE:
- Backend launcher: `scripts/run_backend.ps1`
- Host/Port: 127.0.0.1:8000 (strictly loopback)
- `GET /api/health` → HTTP 200 `{"status":"ok","service":"local-ai-voice-api","version":"0.3.0-dev"}`
- `GET /api/system/status` → HTTP 200 (all hardware and runtime fields valid, `omnivoice_model_loaded: false`)
- `GET /api/providers/status` → HTTP 200

PROVIDER BEFORE INFERENCE:
- primary: omnivoice
- state: NOT_LOADED
- loaded: false
- model_load_count: 0
- Invariant confirmed: Fresh startup of FastAPI did not trigger eager model loading.

REQUEST 1:
- Mode: Cold inference (triggered initial model load)
- Text: "Xin chào. Đây là bài kiểm tra hệ thống tổng hợp giọng nói bằng OmniVoice."
- Language: vi
- Voice ID: omnivoice_auto
- Speed: 1.0
- Format: wav
- Status: HTTP 200 OK
- Generation ID: `f6be4900-8c3d-4090-9f74-6567ddaa2866`
- Wall time: 31.46 s (including weight loading to GPU)
- Synthesis time (backend): 3.95 s
- Duration: 4.48 s
- Sample rate: 24000 Hz, Channels: 1 (mono)

REQUEST 2:
- Mode: Warm inference (model reuse verification)
- Text: "Hệ thống đang thực hiện yêu cầu thứ hai để xác minh mô hình được tái sử dụng."
- Language: vi
- Voice ID: omnivoice_auto
- Speed: 1.0
- Format: wav
- Status: HTTP 200 OK
- Generation ID: `52bc7e21-4f4e-4792-9e83-23f153c2eba3`
- Wall time: 2.04 s
- Synthesis time (backend): 2.02 s
- Duration: 4.53 s
- Sample rate: 24000 Hz, Channels: 1 (mono)

MODEL REUSE:
- Provider state after Request 1: `READY` (loaded: true)
- Provider state after Request 2: `READY` (loaded: true)
- Model load count: Exactly 1 across all sequential requests.
- Latency comparison: Cold = 31.46 s vs Warm = 2.04 s (Speedup: 15.4x, Warm RTF = 0.45).
- Log inspection confirms `provider_transition state=LOADING` occurred only once during Request 1; Request 2 executed without reloading weights.

AUDIO VALIDATION:
- File 01 (`reports/cp03b3_verification/listening_01.wav`):
  - Size: 215,084 bytes
  - Sample rate: 24000 Hz, Channels: 1
  - Duration: 4.48 s
  - Finite samples: True, NaN: False, Inf: False
  - Media type: `audio/wav`
- File 02 (`reports/cp03b3_verification/listening_02.wav`):
  - Size: 217,484 bytes
  - Sample rate: 24000 Hz, Channels: 1
  - Duration: 4.53 s
  - Finite samples: True, NaN: False, Inf: False
  - Media type: `audio/wav`
- File MP3 (`reports/cp03b3_verification/listening_mp3.mp3`):
  - Size: 77,804 bytes
  - Sample rate: 24000 Hz
  - Duration: 3.81 s
  - Decodable: True
  - Media type: `audio/mpeg`

INPUT VALIDATION:
- 9 negative test cases tested against `POST /api/tts`:
  - `empty_text` (""): 422 `INVALID_TEXT` (PASS)
  - `whitespace_text` ("   "): 422 `INVALID_TEXT` (PASS)
  - `oversized_text` (>2000 chars): 422 `TEXT_TOO_LONG` (PASS)
  - `unsupported_language` ("de"): 422 `LANGUAGE_NOT_SUPPORTED` (PASS)
  - `invalid_voice` ("nonexistent_voice"): 422 `VOICE_NOT_FOUND` (PASS)
  - `speed_too_low` (0.4): 422 `INVALID_SPEED` (PASS)
  - `speed_too_high` (2.1): 422 `INVALID_SPEED` (PASS)
  - `speed_not_one` (1.5): 422 `INVALID_SPEED` (PASS)
  - `invalid_format` ("ogg"): 422 `INVALID_FORMAT` (PASS)
- All responses returned standardized `{"ok": false, "error": {"code": ..., "message": ...}}`.
- No stack traces or internal object representations exposed.

SECURITY:
- Tested audio artifact delivery route (`GET /api/audio/{artifact_id}`):
  - `nonexistent_uuid`: 404 `ARTIFACT_NOT_FOUND` (PASS)
  - `path_traversal_relative` (`../../secret.txt`): 404 (PASS)
  - `path_traversal_parent_wav` (`../reference.wav`): 404 (PASS)
  - `absolute_windows_path` (`C:/Windows/system32/calc.exe`): 404 (PASS)
  - `unix_passwd` (`/etc/passwd`): 404 (PASS)
  - `non_uuid_filename` (`not-a-uuid.wav`): 404 (PASS)
  - `exe_extension` (`3b9b6972-2774-4c04-8bbd-fa078a76409a.exe`): 404 (PASS)
- Output filenames and artifact IDs are strictly controlled via UUID4 generated on the server.
- No arbitrary file system access is possible.

LOG PRIVACY:
- Injected privacy test marker: `CP03B3_PRIVACY_MARKER_92841`
- Server console/stream log audited: 0 occurrences of marker or customer text.
- Logging strictly records metadata: `generation_id`, `provider`, `language`, `voice_id`, `format`, `duration`, `text_length`, and `gen_time`. Full customer text is never logged.

SHUTDOWN:
- Backend terminated cleanly.
- Port 8000 released without socket hanging.
- No orphaned background python processes left running.

FINDINGS:
- None. No implementation defects or regressions detected. All automated invariants hold.

HUMAN LISTENING:
- REQUIRED.
- Listening files saved in `reports/cp03b3_verification/`.
- Subjective checklist template generated in `reports/cp03b3_verification/listening_checklist.md`.

FILES CREATED:
- `scripts/verify_cp03b3_independent.py`
- `reports/cp03b3_verification/verification.json`
- `reports/cp03b3_verification/listening_01.wav`
- `reports/cp03b3_verification/listening_02.wav`
- `reports/cp03b3_verification/listening_mp3.mp3`
- `reports/cp03b3_verification/listening_checklist.md`
- `reports/cp03b3_independent_verification.md`

FILES CHANGED:
- None (production codebase unmodified).

VERDICT:
- PASS_WITH_LISTENING_REQUIRED

NEXT:
- Human listening evaluation of `listening_01.wav`, `listening_02.wav`, and `listening_mp3.mp3` using `reports/cp03b3_verification/listening_checklist.md`.
- After human subjective confirmation, close CP0.3B-3 and proceed to CP0.3B-4.
