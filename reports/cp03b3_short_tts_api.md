# CP0.3B-3 — Short TTS API + Real OmniVoice Inference

STATUS:
PASS_WITH_LISTENING_REQUIRED — Technical pipeline, FastAPI routes, lazy loading, error handling, security boundaries, and real CUDA inference smoke pass. Subjective human voice quality listening evaluation remains pending.

ARCHITECTURE:
- Layered execution model:
  POST /api/tts → TTSService → ProviderService.ensure_primary_provider_loaded() → OmniVoiceProvider.synthesize() → CUDA → Audio Validation → HTTP response.
- Route handlers contain no provider inference logic; provider lifecycle is strictly managed by ProviderService.
- TTS generation is offloaded to the threadpool via `run_in_threadpool`, keeping the FastAPI asynchronous event loop responsive.
- Concurrency protection: ProviderService Condition guards model loading state transitions, while OmniVoiceProvider internal RLock prevents concurrent GPU state corruption.

ENDPOINTS:
POST /api/tts
- Synchronous short-text TTS synthesis.
- Accepts JSON payload, validates inputs, ensures provider is loaded, invokes synthesis, validates audio output, exports MP3 if requested, and returns artifact metadata.

GET /api/audio/{artifact_id}
- Safe delivery of generated audio files (.wav or .mp3).
- Strict regex and path traversal security guards; only serves backend-generated UUID artifacts from the designated artifact storage directory.

INPUT CONTRACT:
```json
{
  "text": "string (non-empty, non-whitespace, max 2000 characters)",
  "language": "string (canonical verified ID: vi, en, zh, ja, es, pt, it, fr, hi)",
  "voice_id": "string (default: 'omnivoice_auto', validated against provider.list_voices)",
  "speed": "float (default: 1.0, range: [0.5, 2.0], currently 1.0 for OmniVoice)",
  "format": "string (default: 'wav', allowed: 'wav', 'mp3')"
}
```

OUTPUT CONTRACT:
```json
{
  "ok": true,
  "data": {
    "generation_id": "8ab9d7e1-b856-41dc-83b5-a416336bc0f5",
    "status": "completed",
    "provider": "omnivoice",
    "language": "vi",
    "voice_id": "omnivoice_auto",
    "duration_seconds": 3.53,
    "sample_rate": 24000,
    "channels": 1,
    "format": "wav",
    "audio_url": "/api/audio/8ab9d7e1-b856-41dc-83b5-a416336bc0f5.wav"
  }
}
```

PRIMARY PROVIDER:
OmniVoice (registered ID: `omnivoice`, device: `cuda:0`)

LAZY LOAD:
Before first request:
- provider_state: NOT_LOADED
- loaded: false
- model_load_count: 0
After first request:
- provider_state: READY
- loaded: true
- model_load_count: 1
After second request:
- provider_state: READY
- loaded: true
- model_load_count: 1 (model reused, no reload)
Model load count: 1 across sequential requests.

REAL GPU SMOKE:
- Script: `scripts/smoke_short_tts_api.py`
- Environment: Python 3.12.10, PyTorch 2.8.0+cu128, CUDA 12.8, NVIDIA GeForce RTX 4050 Laptop GPU (6 GB VRAM)
- Request 1:
  - Text: "Xin chào. Đây là bài kiểm tra hệ thống tổng hợp giọng nói." (length: 58)
  - Wall time (including cold model load): 19.19 s
  - Synthesis time: 2.90 s
  - Audio duration: 3.53 s
  - Generation ID: `8ab9d7e1-b856-41dc-83b5-a416336bc0f5`
- Request 2 (model reuse):
  - Text: "Đây là câu thứ hai nhằm xác nhận mô hình được tái sử dụng mà không cần nạp lại." (length: 79)
  - Wall time: 0.908 s (warm inference)
  - Synthesis time: 0.89 s (RTF = 0.19)
  - Audio duration: 4.65 s
  - Generation ID: `41889441-ec24-4ea6-9bb1-530a51ec4c3a`
- Evidence: `reports/cp03b3_short_tts_smoke.json`

AUDIO VALIDATION:
Sample rate: 24000 Hz
Channels: 1 (mono)
Duration: 3.53 s (req 1), 4.65 s (req 2)
Finite: True (all samples finite, no NaN, no Inf)
Decodable: Verified with `soundfile` and `wave`

ERROR CONTRACT:
- INVALID_TEXT (422): "Văn bản không hợp lệ." (null, empty, whitespace)
- TEXT_TOO_LONG (422): "Văn bản vượt quá giới hạn của chế độ TTS ngắn." (>2000 chars)
- LANGUAGE_NOT_SUPPORTED (422): "Ngôn ngữ không được hỗ trợ." (outside 9 verified IDs)
- VOICE_NOT_FOUND (422): "Không tìm thấy giọng đọc được chọn."
- INVALID_SPEED (422): "Tốc độ đọc không hợp lệ. Vui lòng chọn trong khoảng 0.5 đến 2.0."
- INVALID_FORMAT (422): "Định dạng âm thanh không được hỗ trợ." (not wav/mp3)
- PROVIDER_UNAVAILABLE (503): "Bộ máy tạo giọng hiện không khả dụng."
- PROVIDER_LOAD_FAILED (503): "Không thể nạp bộ máy tạo giọng. Vui lòng kiểm tra runtime và model."
- GENERATION_FAILED (500): "Quá trình tạo giọng nói thất bại."
- AUDIO_EXPORT_FAILED (500): "Không thể xuất file âm thanh." (MP3 failure retains valid WAV)
- ARTIFACT_NOT_FOUND (404): "Không tìm thấy file âm thanh."

SECURITY:
Path traversal:
- Strict UUID4 regex verification (`^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(wav|mp3)$`)
- Path resolution verification (`target_file.is_relative_to(output_dir)`)
- Attacks such as `../../secret.txt` or absolute paths return 404 ARTIFACT_NOT_FOUND without escaping directory.
Filesystem exposure:
- No absolute filesystem paths in response body or headers.
- Safe generated UUID4 filenames used for all artifacts.
Logging privacy:
- Server logs generation_id, provider, language, voice_id, format, duration, gen_time, text_length.
- Full customer text is never logged.
- Internal exception stack traces are never sent to clients.

TESTS:
Backend: 86 passed (test_backend: 22, test_provider_service: 27, test_tts_service: 37)
Targeted: 92 passed (test_omnivoice_provider, test_omnivoice_cloning, test_omnivoice_languages, test_long_text, test_long_text_manager, test_audio_boundary)
Broader: 189 passed in 4.55 s
GPU smoke: PASS (`scripts/smoke_short_tts_api.py`) and bootstrap smoke PASS (`scripts/smoke_backend.py`)

FILES CREATED:
- `backend/schemas/tts.py`
- `backend/services/tts_service.py`
- `backend/api/tts.py`
- `backend/api/audio.py`
- `backend/tests/test_tts_service.py`
- `scripts/smoke_short_tts_api.py`
- `reports/cp03b3_short_tts_smoke.json`
- `reports/cp03b3_listening/short_tts_01.wav`
- `reports/cp03b3_listening/short_tts_02.wav`
- `reports/cp03b3_short_tts_api.md`

FILES CHANGED:
- `backend/errors/__init__.py`: Added TTS error codes.
- `backend/errors/handlers.py`: Added TTS error messages and HTTP status mappings.
- `backend/config.py`: Added output_dir configuration and LOCAL_AI_OUTPUT_DIR support.
- `backend/dependencies/__init__.py`: Added get_tts_service dependency.
- `backend/api/router.py`: Included tts and audio routers.
- `backend/main.py`: Injected TTSService in lifespan; updated CORS allow_methods to include POST.
- `backend/tests/test_backend.py`: Updated openapi paths test to reflect B-3 routes.
- `scripts/smoke_backend.py`: Updated openapi paths assertion to reflect B-3 routes.

PRODUCTION BEHAVIOR CHANGES:
- FastAPI backend now exposes POST /api/tts and GET /api/audio/{artifact_id}.
- Model loading remains lazy; backend starts without loading model weights into VRAM.
- First request loads OmniVoice onto CUDA; subsequent requests reuse the loaded model instance.
- No changes to prototype core inference algorithms or voice semantics.
- No SQLite database created.
- No frontend changes made.

HUMAN LISTENING:
Generated listening files available at:
- `reports/cp03b3_listening/short_tts_01.wav` (3.53s, 24kHz mono PCM 16-bit)
- `reports/cp03b3_listening/short_tts_02.wav` (4.65s, 24kHz mono PCM 16-bit)
Technical audio validity confirmed (non-empty, finite, 24kHz, 1 channel). Subjective listening verification pending human evaluator review.

LIMITATIONS:
- Short TTS only: hard limit of 2000 characters. Long text chunking and stitching will be addressed in CP0.3B-5.
- Voice selection currently restricted to "omnivoice_auto" per existing OmniVoice baseline contract.
- VoiceProfile and cloning API are not yet exposed (scheduled for CP0.3B-4).
- Artifacts are stored on the local filesystem without persistent DB metadata.

NEXT:
CP0.3B-4 — VoiceProfile / Clone API
