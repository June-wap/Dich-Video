# Local AI Voice API — CP0.3B-2

Application skeleton plus OmniVoice primary-provider lifecycle. No TTS endpoint,
inference, profile upload, database or job queue is implemented.

## Run

Use the sole official Python 3.12 runtime established in
[backend_runtime.md](../docs/backend_runtime.md). From any PowerShell directory:

```powershell
& 'D:\Tool Dich Cho Khach\scripts\run_backend.ps1'
```

The helper sets absolute repository/prototype PYTHONPATH entries and offline
variables, verifies Python 3.12, and calls `python -m backend.main`. It does not
import Torch, activate another venv, install dependencies or start the frontend.
Stop with Ctrl+C. Default address: `http://127.0.0.1:8000`.

Equivalent explicit Uvicorn command from the repository root:

```powershell
Set-Location 'D:\Tool Dich Cho Khach'
$env:PYTHONPATH = (Get-Location).Path + [IO.Path]::PathSeparator + (Join-Path (Get-Location).Path 'prototype')
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
& .\external\OmniVoice\.venv312\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

`python -m backend.main`/the helper use `LOCAL_AI_HOST`, `LOCAL_AI_PORT` and
`LOCAL_AI_LOG_LEVEL` for the server. When calling Uvicorn directly, its command
line host/port/log flags control binding instead. Do not run two servers on the
same port. Checkpoint smoke stops its own server after verification.

## Structure and lifecycle

`api/` maps HTTP to `services/`; `schemas/` defines the public payloads;
`config.py`, `logging_config.py` and `errors/` centralize cross-cutting behavior.
`dependencies/` retrieves the app-scoped service. `create_app()` supports service
injection for tests. Lifespan owns one ProviderService with one registered
OmniVoiceProvider, selected as primary. No TTSManager is created.

Lifespan initializes a lightweight provider object, SystemService and logging.
The adapter constructor imports NumPy/canonical language metadata; it does not
import Torch or the upstream OmniVoice runtime, load a model or allocate model
VRAM. Health and provider status do not trigger any runtime/model load. First
system status probes Torch/CUDA in a worker thread and caches only hardware
metadata. Provider state is fetched live from ProviderService on every request,
so a load/unload/error is immediately reflected even after hardware is cached.
The first system-status response can take several seconds for cold Torch imports;
health remains independent. Restart to refresh hardware/package-discovery metadata.

The existing `prototype/core/hardware.py` was inspected. Its CUDA flag refers to
ONNX Runtime providers, and its version helper imports legacy engines. Neither
accurately represents the Torch CUDA contract required here. The service probes
Torch directly; OmniVoice availability/state comes from ProviderService. It does
not duplicate CPU/RAM/nvidia-smi probes or modify the legacy helper.

## Primary provider and lifecycle

The single-worker backend owns one provider instance for its lifespan. Repeated
requests retrieve the same object. No uncontrolled module singleton, per-request
provider creation, legacy provider registration or provider fallback is used.
Applications/tests may inject their own service factory; run one app/lifespan
per backend process as in the documented launcher.

Internal application methods (not public HTTP routes):

```python
provider = service.get_primary_provider()  # object only, no model load
provider = service.ensure_primary_provider_loaded()  # future inference entry
service.unload(provider.provider_name())
# Only an intentional retry clears a previous load error:
provider = service.ensure_primary_provider_loaded(retry=True)
```

Normal transitions: `NOT_LOADED → LOADING → READY → UNLOADING → NOT_LOADED`.
Load failure enters `ERROR` and returns `PROVIDER_LOAD_FAILED`. A normal ensure
call keeps that error; an explicit `retry=True` permits a new attempt. Concurrent
waiters share the completed load/failure without starting repeated load attempts.
An explicit unload/cleanup can also clear error state after successful cleanup.

One application Condition synchronizes the state machine and closes admission
during shutdown. Provider operations run outside that Condition and retain the
adapter's existing model RLock; status can observe LOADING/UNLOADING immediately.
Shutdown waits for an in-flight load/unload, then unloads READY/ERROR entries.
NOT_LOADED is a safe no-op. Cleanup errors are logged and remain ERROR; shutdown
does not crash or claim successful GPU release after failed cleanup.

All future loads/unloads must go through ProviderService. Do not call model
lifecycle methods directly after retrieving an adapter; that bypasses application
state tracking. This checkpoint does not implement inference leases, scheduling,
timeouts or cancellation of a native model load. B-3 must integrate inference
with this ownership instead of creating another provider instance.

## Endpoints and success convention

Success responses are **direct typed JSON**, without an `ok/data` envelope.
There is only one success convention for application endpoints.

`GET /api/health` returns HTTP 200:

```json
{"status":"ok","service":"local-ai-voice-api","version":"0.3.0-dev"}
```

`GET /api/system/status` returns HTTP 200 with fields:

```json
{
  "status": "ready",
  "python_version": "3.12.10",
  "torch_version": "2.8.0+cu128",
  "cuda_available": true,
  "gpu_name": "NVIDIA GeForce RTX 4050 Laptop GPU",
  "omnivoice_available": true,
  "omnivoice_model_loaded": false,
  "primary_provider": "omnivoice",
  "provider_state": "NOT_LOADED",
  "audio": {"sample_rate": 24000, "channels": 1},
  "runtime_mode": "local"
}
```

The sample values above are the real smoke result, not hard-coded hardware.
`ready` means required runtime capabilities are available; it does not mean the
model or TTS is ready. Missing Torch/CUDA, unavailable provider or lifecycle
ERROR yields `degraded`; backend health can still be `ok`. Runtime-probe errors
are logged locally and never expose exception strings to the API.
`omnivoice_model_loaded` and `provider_state` are sourced from the registry's
verified lifecycle outcomes. Startup reports false/NOT_LOADED; internal load
success becomes true/READY, and successful unload becomes false/NOT_LOADED.

`GET /api/providers/status` returns direct typed JSON with `primary` and a
`providers` list. Each entry contains `id`, `available`, `state`, `loaded`,
`device`, `languages`, `language_metadata`, `experimental_languages_enabled`,
`production_ready` and a safe optional `error_code`. No model path, raw health
dictionary, provider/model object or traceback is returned.

`available=true` means the adapter is registered and Torch/OmniVoice packages
are discoverable at bootstrap, not that model artifacts are installed, runtime
imports are certified or the model is loaded. Missing packages produce
UNAVAILABLE and PROVIDER_UNAVAILABLE on internal ensure; broken imports/model
artifacts produce ERROR/PROVIDER_LOAD_FAILED when loading is explicitly attempted.
The verified runtime import audit remains in CP0.3B-0. B-2 avoids importing the
upstream runtime just to report status.

Languages and validation metadata are copied from `provider.capabilities()`:
nine VERIFIED languages only. Experimental upstream languages remain disabled;
`production_ready=false` and the narrow CUDA/cloned-language verification scope
are preserved. No language aliases, quality presets or fallback are introduced.

OpenAPI: `/openapi.json`; developer documentation: `/docs` and `/redoc`.
Only the three GET application routes appear in OpenAPI. There is no public
provider load/unload route; loading is reserved for the future inference path.

## Errors

Application/request errors use a stable envelope:

```json
{"ok":false,"error":{"code":"INTERNAL_ERROR","message":"Đã xảy ra lỗi trong quá trình xử lý."}}
```

| Code | HTTP status |
| --- | --- |
| INVALID_REQUEST | 422 for validation; 400 for invalid Host |
| NOT_FOUND | 404 |
| METHOD_NOT_ALLOWED | 405 |
| SERVICE_UNAVAILABLE | 503 |
| INTERNAL_ERROR | 500 |
| PROVIDER_NOT_FOUND | 404 |
| PROVIDER_UNAVAILABLE | 503 |
| PROVIDER_LOAD_FAILED | 503 |
| PROVIDER_NOT_READY | 503 |

Validation does not echo input, Pydantic context or raw error details.
Unexpected exceptions keep their traceback server-side and return a generic
message. Error responses for allowed browser origins carry CORS headers too.
Standard CORS preflight responses are middleware protocol responses; a rejected
preflight is HTTP 400 without an allow-origin header and is not the JSON API
error envelope. No arbitrary file paths, raw model state or customer data is
returned by the endpoints.

## Configuration and local access

Defaults are centralized in `backend/config.py`:

| Environment variable | Default |
| --- | --- |
| LOCAL_AI_APP_NAME | Local AI Voice API |
| LOCAL_AI_APP_VERSION | 0.3.0-dev |
| LOCAL_AI_API_PREFIX | /api |
| LOCAL_AI_HOST | 127.0.0.1 |
| LOCAL_AI_PORT | 8000 |
| LOCAL_AI_CORS_ORIGINS | http://localhost:5173,http://127.0.0.1:5173 |
| LOCAL_AI_LOG_LEVEL | INFO |
| LOCAL_AI_PRIMARY_TTS_PROVIDER | omnivoice |
| LOCAL_AI_OMNIVOICE_DEVICE | cuda:0 |

An unknown primary fails explicitly; only OmniVoice is currently registered.
The device must be an explicit `cuda:N`; CPU is not enabled in this backend.
The existing provider derives **float16** for CUDA. There is no dtype override
or extra argument passed to its constructor (its real API has no dtype option).
The adapter's existing 16 generation steps and behavior are unchanged.

Vite config has no port override; its normal development port is 5173. If it
moves to 5174 because 5173 is occupied, configure that explicit loopback origin.
Origins with wildcards, remote hosts, credentials or paths are rejected.
CORS allows GET, Content-Type and no credentials. Host headers are restricted
to localhost, 127.0.0.1 and ::1. There is no authentication in this checkpoint,
as explicitly requested; CORS is a browser policy, not authentication.

Logging is console-only with timestamp, level, logger and event text. It logs
start/stop and failures, with no request-body/query logging and no duplicate
backend handlers. The documented server commands disable Uvicorn access logs.

## Verification

```powershell
# From the repository root; same official interpreter for every test.
$env:PYTHONPATH = 'prototype'
& .\external\OmniVoice\.venv312\Scripts\python.exe -m pytest backend/tests -v
& .\external\OmniVoice\.venv312\Scripts\python.exe -m pytest backend/tests prototype/tests tests -v
& .\external\OmniVoice\.venv312\Scripts\python.exe scripts/smoke_backend.py
```

Backend: 49 passed (including 27 provider lifecycle tests). Existing targeted
core: 92 passed. Combined: 152 passed.
The live smoke binds 127.0.0.1:8000, uses real HTTP and real runtime probing,
blocks external socket connections, writes checkpoint evidence and gracefully
stops its own server. It fails if the port is occupied; it never stops another
process. Constructor/load guards prove exactly one provider and zero model-load
calls; status and Torch tensor allocation checks confirm the model stays unloaded.
Zero allocated model/tensor bytes is not a claim of zero CUDA driver/context
memory. No real load/unload model smoke, synthesis or download is performed.

Known non-blocking test warnings come from installed Starlette/httpx,
AnyIO BlockingPortal and pydub/audioop. No dependency was changed to suppress
them. Current report: [cp03b2_omnivoice_provider_bootstrap.md](../reports/cp03b2_omnivoice_provider_bootstrap.md).
# Current checkpoint: CP0.3B-5

Long-form job API: [contract and lifecycle](../docs/long_form_api.md).
The B-5 service adds POST/GET/DELETE `/api/tts/long-form` job routes and uses
the existing B-3 audio route and B-4 profile registry. The historical B-2
bootstrap notes below describe that checkpoint only; its route/test counts
are superseded by the B-5 report.
