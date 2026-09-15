# CP0.3B-2 — OmniVoice Primary Provider Bootstrap

STATUS:
PASS — implementation acceptance criteria verified. No automatic B-3 work or
production/inference readiness certification is implied.

PRIMARY PROVIDER:
OmniVoice, ID `omnivoice`. The default ID is centralized in backend/config.py.
`LOCAL_AI_PRIMARY_TTS_PROVIDER` selects the registered primary; unknown IDs fail
explicitly. Only OmniVoice is registered by the backend factory. No legacy,
CPU or mock fallback exists in the application.

ARCHITECTURE:
- Existing FastAPI bootstrap retained; app.state owns ProviderService and
  SystemService for the lifespan.
- ProviderService combines registry, primary selection, safe status snapshots,
  lazy loading, explicit retry and shutdown coordination in one application module.
- Lifespan creates exactly one actual OmniVoiceProvider object with `device=cuda:0`.
  Route/dependency calls reuse it; there is no provider construction per request.
- Registry supports explicit registration/selection without automatic fallback.
  Duplicate registration of the same object is idempotent; a different object
  with the same ID is rejected.
- Metadata/schema serialization uses an explicit allowlist; raw health_check
  dictionaries (including model paths) and provider/model objects are not exposed.
- SystemService caches RuntimeInfo hardware fields only. Each response obtains
  provider available/loaded/state from the same current registry snapshot.
- No TTSManager construction or modification. No upstream/adapter rewrite.

LIFECYCLE:
- NOT_LOADED → LOADING → READY.
- READY → UNLOADING → NOT_LOADED.
- Load failure → ERROR + PROVIDER_LOAD_FAILED.
- ERROR remains until intentional `ensure_primary_provider_loaded(retry=True)`
  or explicit successful unload/cleanup. Normal reads/ensure calls never erase it.
- Missing runtime packages → UNAVAILABLE; ensure raises PROVIDER_UNAVAILABLE.
- Unload failure → ERROR + PROVIDER_NOT_READY; known actual loaded state is
  checked and retained, rather than claiming successful GPU release.
- Shutdown closes new operation admission, waits for ongoing load/unload,
  cleans READY/ERROR providers, safely skips NOT_LOADED, and logs cleanup failure
  without crashing the lifespan. Repeated shutdown is idempotent.
- A SystemService construction failure also cleans the already-created registry.
- Registration, state transitions (load started/ready/error/unload started/unloaded)
  and failures are logged. No script, reference transcript, audio or model repr is logged.

STARTUP:
- provider_state: NOT_LOADED.
- model_loaded: false.
- provider_instance_count: 1.
- provider.load calls: 0.
- model_load_count: 0.
- model_vram: 0 bytes — no model constructed/loaded; real smoke also measured
  Torch allocated tensor bytes = 0 after status requests.
- Runtime: official Python 3.12.10 interpreter at
  `external/OmniVoice/.venv312/Scripts/python.exe`; Torch 2.8.0+cu128,
  CUDA available, NVIDIA GeForce RTX 4050 Laptop GPU.
- Startup imports the existing lightweight adapter/NumPy/language metadata.
  It does not import Torch or upstream OmniVoice. Health/provider status stay
  lightweight. First system status probes Torch/CUDA, not the OmniVoice model.
- Model VRAM/tensor allocation is distinct from CUDA driver/context memory;
  no claim of total GPU process memory being zero is made.

LAZY LOAD:
- Internal `get_primary_provider()` returns the same object without loading.
- Internal `ensure_primary_provider_loaded()` calls the existing `load()` only
  when admitted; subsequent READY calls return the same provider.
- Existing `load()`, `unload()`, `is_loaded()`, `capabilities()` and health-check
  signatures were inspected and reused. Load success is confirmed by is_loaded().
- CUDA dtype stays float16, as derived by the original provider; no unsupported
  dtype constructor parameter, quality preset or num_step change was introduced.
- `LOCAL_AI_OMNIVOICE_DEVICE` defaults to cuda:0 and accepts explicit cuda:N.
  CPU is rejected by backend configuration. Runtime failures do not select
  another device/provider.
- No HTTP load/unload endpoint exists. B-3 will call the internal lifecycle helper.

CONCURRENCY:
- One application Condition protects registry state and shutdown admission.
  This is required for observable LOADING/UNLOADING, shared failure results,
  explicit retry semantics and shutdown coordination that the adapter lock
  alone does not supply.
- Actual model operations run outside the Condition and retain the adapter's
  existing RLock. Provider status remains responsive during load/unload.
- Six simultaneous ensures returned the same fake adapter with exactly one load.
- Concurrent failed ensures shared one failed attempt; no implicit retry storm.
- Shutdown racing a load prevented new operations, waited for load completion,
  then unloaded once. The finishing loader received PROVIDER_NOT_READY after
  shutdown admission closed.

ENDPOINTS:
- GET `/api/health` retained.
- GET `/api/system/status` now includes primary_provider and provider_state;
  omnivoice_model_loaded is live lifecycle state rather than B-1's constant false.
- GET `/api/providers/status` added with direct typed JSON:
  `primary` plus `providers` list.
- Same direct success convention and normalized error envelope as B-1.
- OpenAPI lists exactly these three GET application routes. No TTS/cloning/
  long-form/manual model-loading route, frontend integration, DB or job engine.

CAPABILITIES:
- Nine language IDs/metadata come directly from OmniVoiceProvider.capabilities():
  vi, en, zh, ja, es, pt, it, fr, hi.
- VERIFIED scope is preserved with cloned_live_verified flags and
  production_ready=false. Experimental upstream languages remain disabled.
- Provider `available` means registered adapter plus discoverable Torch and
  OmniVoice packages at startup, not a new real-import/model-load certification.
  Missing packages mark UNAVAILABLE. Broken runtime imports/model artifacts
  surface as LOAD_FAILED/ERROR when an internal load is explicitly attempted.
- This narrower availability definition is documented. No upstream runtime
  import is needed merely to report provider status. CP0.3B-0 remains the real
  runtime import audit; B-2 does not reclassify package discovery as inference.

ERROR CONTRACT:
- PROVIDER_NOT_FOUND: HTTP 404.
- PROVIDER_UNAVAILABLE: HTTP 503.
- PROVIDER_LOAD_FAILED: HTTP 503.
- PROVIDER_NOT_READY: HTTP 503.
- Payload: `{"ok":false,"error":{"code":"PROVIDER_LOAD_FAILED","message":"...safe Vietnamese message..."}}`.
- Model/runtime exception strings and filesystem paths stay out of response
  metadata and error messages; technical traces are server-side only.

TESTS:
- Baseline: 125 passed, 3 warnings, 3.44 s.
- Provider tests: 27 passed, 2 warnings, 0.74 s.
- Backend full suite: 49 passed, 2 warnings, 2.06 s.
- Targeted existing regression: 92 passed, 1 warning, 1.89 s.
- Broader regression: 152 passed, 3 warnings, 3.16 s.
- All commands used the official interpreter with PYTHONPATH=prototype.
- Existing 22 backend tests were retained/adapted for provider-aware startup,
  DI and the third route; existing core tests were not changed.
- Real adapter load/unload contract was tested with _load_model replaced by an
  in-memory fake (no Torch/Hugging Face/model weights). Original adapter reuse
  and load_count=1 were verified without altering production code.
- Tests include single construction, initial NOT_LOADED, dynamic system status,
  repeated/concurrent ensure, sticky load failures/retry, missing provider/runtime,
  verified language scope, no fallback, transition visibility, unload, partial
  failure cleanup, shutdown race/cleanup failure, and safe normalized HTTP errors.
- Real bootstrap/HTTP smoke: PASS. Counts one actual adapter constructor, guards
  load() against any call, performs real localhost health/provider/system/OpenAPI
  requests, records CUDA tensor allocation, blocks external socket connections,
  and gracefully stops only its own server. Both app.state services are released.
- Logs/evidence: reports/cp03b2_baseline_tests.log, cp03b2_provider_tests.log,
  cp03b2_backend_tests.log, cp03b2_targeted_tests.log, cp03b2_broader_tests.log,
  cp03b2_http_smoke.json and cp03b2_http_smoke.log.

OPTIONAL REAL LIFECYCLE SMOKE:
NOT_RUN.
Result: no real model load/unload or inference. This optional check was skipped
because existing adapter evidence plus deterministic lifecycle tests suffice for
this checkpoint. The real startup/HTTP/VRAM smoke above was run separately and
must not be confused with loading actual model weights.

FILES CREATED:
- backend/services/provider_service.py.
- backend/schemas/providers.py.
- backend/api/providers.py.
- backend/tests/provider_fakes.py.
- backend/tests/test_provider_service.py.
- This report and seven cp03b2 test/smoke evidence files listed above.

FILES CHANGED:
- backend/main.py: lifespan registry construction, service injection and cleanup.
- backend/config.py: centralized primary ID and CUDA-device configuration.
- backend/services/system_service.py: cache hardware, read live provider state.
- backend/schemas/system.py: live model-loaded boolean and primary/state fields.
- backend/dependencies/__init__.py: app-scoped ProviderService dependency.
- backend/api/router.py: provider-status router.
- backend/errors/__init__.py and backend/errors/handlers.py: safe provider codes.
- backend/tests/test_backend.py: adapt B-1 assertions/contracts; retain coverage.
- scripts/smoke_backend.py: update to B-2 startup/instance/VRAM proof, write new
  cp03b2 evidence without overwriting historical B-1 files.
- backend/README.md and docs/backend_runtime.md: lifecycle, API, configuration,
  exact run/test commands and availability semantics.

PRODUCTION BEHAVIOR CHANGES:
- Backend startup now creates one unloaded primary OmniVoiceProvider object.
- Provider status is exposed; system status reflects managed lifecycle changes.
- No TTS generation behavior changed: num_step, dtype selection, chunking, DSP,
  VoiceProfile semantics, TTSManager and upstream OmniVoice remain untouched.
- No dependency installation, Torch/CUDA update, alternate venv, frontend edit,
  authentication, SQLite/database file, persistence or new public inference API.

REPOSITORY / INSPECTION / PRIVACY:
- Root workspace: NOT A GIT REPOSITORY. No fabricated root branch/commit/diff.
- Nested OmniVoice tracked diff remains empty. The upstream model source SHA256
  still equals the CP0.3B-0 snapshot:
  5b790ce64fb95e4ca87b7a9060af02d3d90b84166dc2771edf5ad0212809871f.
- Inspected current backend, base/OmniVoice provider API, TTSManager, language
  metadata, runtime docs and B-1 report; existing Rule/RULES.txt and empty AGENTS
  instructions remain applicable. Work stayed within B-2 scope.
- No secrets, customer text, reference audio, model object or private model path
  are added to public responses. Safe existing CORS/Host/error policy retained.
- Dependency/license impact: no packages or binaries added/redistributed; no
  change to earlier commercial review status.

LIMITATIONS:
- Availability is startup package discovery, not successful model-load proof.
- Actual model GPU release after real load was not re-measured in B-2.
- Managed callers must use ProviderService for load/unload; bypassing it can
  bypass state tracking. There is no inference scheduling/lease API yet.
- Shutdown waits for native load/unload completion; forced interruption and
  timeout policy are not implemented by this lifecycle checkpoint.
- One app/lifespan per backend worker is the supported run pattern. No global
  singleton enforces ownership across arbitrary multiple app factories in the
  same process; test factories remain intentionally injectable.
- Hardware/package discovery is cached for the lifespan; lifecycle state is live.
- Existing Starlette/httpx, AnyIO and pydub/audioop warnings are non-blocking.
- Official Python may need approved outside-sandbox execution in Codex, as
  documented in B-0; host execution and tests pass.

NEXT:
CP0.3B-3 — Short TTS API.
STOP. B-3 has not been started.
