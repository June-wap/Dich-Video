# CP0.3B-1 — Application / FastAPI Backend Skeleton

STATUS:
PASS — checkpoint implementation and acceptance tests completed. This is not
production readiness or permission to start CP0.3B-2 automatically.

ARCHITECTURE:
- `backend.main.create_app()` assembles configuration, lifespan, middleware,
  exception handlers and routers.
- HTTP routes → SystemService → safe capability probing; provider/bootstrap
  integration is reserved for B-2. B-1 does not instantiate TTSManager or an
  OmniVoiceProvider.
- Typed direct success responses; one normalized JSON error envelope.
- Lifespan creates a lightweight service and logging, then releases service
  metadata on shutdown. Model/runtime packages are not imported on startup.
- System probing is lazy, cached per app and performed by a synchronous route
  in FastAPI's thread pool. GPU name comes from Torch; no hard-coded device.
- Existing hardware helper was inspected: its CUDA field reflects ONNX Runtime,
  and its version helper imports legacy providers. Reusing it would not answer
  the required Torch CUDA status correctly. It remains unchanged; B-1 adds only
  the Torch/OmniVoice capability probe, not duplicate CPU/RAM hardware scanning.

ENDPOINTS:
- GET `/api/health`: HTTP 200; process liveness, service and version.
- GET `/api/system/status`: HTTP 200; safe typed runtime metadata.
- `/docs`, `/redoc`, `/openapi.json`: local developer documentation.
- No inference, upload, job or file-serving route.

RUNTIME:
- Python: 3.12.10.
- Interpreter: `D:\Tool Dich Cho Khach\external\OmniVoice\.venv312\Scripts\python.exe`.
- FastAPI: 0.141.1.
- Uvicorn: 0.52.4.
- Pydantic baseline retained: 2.13.5.
- No venv or dependency modifications.
- Normal server startup: `scripts/run_backend.ps1` (also works outside repo cwd)
  or the exact official-interpreter Uvicorn command in `backend/README.md`.
- Default bind: 127.0.0.1:8000. No listener was found on 8000 before smoke.

SYSTEM STATUS:
- Real loopback HTTP smoke: PASS.
- CUDA: true, Torch 2.8.0+cu128.
- GPU: NVIDIA GeForce RTX 4050 Laptop GPU.
- OmniVoice available: true (real package import).
- Model loaded: false.
- Audio: 24000 Hz, mono.
- Runtime mode: local.
- `ready` means runtime capabilities, not model/inference readiness. If imports
  or CUDA are unavailable, status becomes `degraded` while liveness stays 200.

NO-MODEL-LOAD EVIDENCE:
- An isolated Python subprocess blocks imports of torch, omnivoice, providers
  and core. App import, lifespan startup, health and shutdown still pass.
- A system-service test gives model load/generate methods failing sentinels;
  capability probing does not call them.
- Real HTTP smoke confirms no AI imports after startup/health. After real system
  status, no provider or TTSManager module was imported, and Torch reports zero
  allocated CUDA tensor bytes. No inference or model download was run.
- External socket connections are blocked by the smoke runner. It owns only
  its loopback server and shuts it down gracefully; service metadata is released.
- Evidence: `reports/cp03b1_http_smoke.json`, `reports/cp03b1_http_smoke.log`.

CORS:
- Inspected Vite config/package scripts: no development port override.
- Explicit `http://localhost:5173`, `http://127.0.0.1:5173` defaults.
- Credentials disabled; GET and Content-Type allowed.
- `LOCAL_AI_CORS_ORIGINS` accepts explicit loopback origins only.
- Arbitrary origins receive no allow-origin header; their preflight gets 400.
- Host guard accepts only localhost, 127.0.0.1 and ::1.
- Authentication intentionally omitted per this checkpoint's explicit scope.
  The earlier general project authentication rule is superseded here by the
  user's B-1 instruction, not silently treated as implemented.

ERROR CONTRACT:
`{"ok":false,"error":{"code":"INTERNAL_ERROR","message":"Đã xảy ra lỗi trong quá trình xử lý."}}`
- INTERNAL_ERROR: 500, generic message; exception trace is server-side only.
- INVALID_REQUEST: 422 validation / 400 invalid Host.
- SERVICE_UNAVAILABLE: 503.
- NOT_FOUND: 404; METHOD_NOT_ALLOWED: 405.
- Validation never echoes original input or Pydantic exception context.
- CORS applies to unexpected-error responses for allowed clients.
- Middleware CORS preflight responses follow the standard CORS protocol, not
  the API JSON envelope; this exception is documented.

TESTS:
- Baseline existing core: **103 passed**, 1 warning, 2.92 s.
- Backend: **22 passed**, 2 warnings, 2.61 s.
- Targeted regression: **92 passed**, 1 warning, 2.40 s.
- Broader regression: **125 passed**, 3 warnings, 4.81 s (backend + all existing
  prototype/tests and tests; the pre-existing 103 tests remain intact).
- Backend tests cover import/startup without AI, health, typed system metadata,
  capability absence and CPU-only behavior, no model call, cache behavior,
  cleanup, 404/405/422/500/503, CORS allow/deny, local Host, config and OpenAPI.
- Real Uvicorn HTTP: startup, health, system, OpenAPI, CORS, cached response,
  zero CUDA tensor allocation and graceful shutdown all PASS.
- Logs: `cp03b1_baseline_tests.log`, `cp03b1_backend_tests.log`,
  `cp03b1_targeted_tests.log`, `cp03b1_broader_tests.log` under `reports/`.
- No live TTS test was needed or run.

FILES CREATED:
- `backend/__init__.py`, `backend/main.py`, `backend/config.py`,
  `backend/logging_config.py`, `backend/README.md`.
- `backend/api/{__init__,router,health,system}.py`.
- `backend/schemas/{__init__,common,system}.py`.
- `backend/services/{__init__,system_service}.py`.
- `backend/dependencies/__init__.py`.
- `backend/errors/{__init__,handlers}.py`.
- `backend/tests/{__init__,test_backend}.py`.
- `scripts/run_backend.ps1`, `scripts/smoke_backend.py`.
- This report, four test logs, and HTTP smoke JSON/log listed above.

FILES CHANGED:
- `docs/backend_runtime.md`: replace future module placeholder with the actual
  B-1 launcher and link detailed backend instructions.
- No existing core/provider, upstream, frontend or dependency file changed.

DEPENDENCIES:
None installed, upgraded, downgraded or removed. CP0.3B-0 contract reused.
Existing httpx supports TestClient. No new logging framework or settings package.

REPOSITORY / INSPECTION:
- Root workspace is NOT A GIT REPOSITORY; no root branch/diff is fabricated.
- Read user checkpoint, existing Rule/RULES.txt and empty Rule/AGENTS.md,
  CP0.3B-0 runtime documentation/report and dependency contracts, core manager,
  provider/base contracts and hardware helper. No root README/Master Prompt
  found. Frontend inspection limited to Vite config and package scripts.
- Implementation scope consists of the new backend/scripts/evidence and the
  runtime documentation edit listed above. No user changes were removed.

LOGGING / SECURITY / PRIVACY:
- Console logger records lifecycle and failures consistently and avoids duplicate
  backend handlers. It does not log request body/query/headers or customer data.
- Generic errors hide exception text and paths from clients. No arbitrary
  filesystem or command endpoint exists. No secrets are required or returned.
- Binding is loopback by default. CORS/Host controls do not constitute auth.
- Existing license/dependency status is unchanged; no binaries were bundled.

LIMITATIONS:
- Capability snapshot is refreshed only by restarting the application. The first
  system request incurs Torch/OmniVoice import latency; health does not.
- No model readiness, inference quality, provider bootstrap, persistence or
  frontend integration is claimed. `model_loaded=false` is specific to B-1.
- Installed test stack reports Starlette/httpx and AnyIO deprecation warnings;
  pydub has the existing audioop warning. All tests pass; dependencies unchanged.
- The official interpreter may require approved outside-sandbox execution under
  Codex, as established in B-0. Normal host execution passed.
- No authentication, as explicitly required for this local prototype checkpoint.

NEXT:
CP0.3B-2 — OmniVoice Primary Provider Bootstrap.
STOP. B-2 has not been started.
