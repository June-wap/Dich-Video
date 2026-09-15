# CP0.3B-0 — Runtime Contract & Environment Stabilization

STATUS:
PASS — implementation evidence satisfies the runtime acceptance criteria.
This is an implementation/test result, not production certification or automatic
approval to begin another checkpoint.

OFFICIAL RUNTIME:
- Python: 3.12.10, Windows AMD64 (contract: Python 3.12.x).
- Interpreter: `D:\Tool Dich Cho Khach\external\OmniVoice\.venv312\Scripts\python.exe`.
- Venv: `D:\Tool Dich Cho Khach\external\OmniVoice\.venv312`.
- Base interpreter: `C:\Users\GIGABUYTE\AppData\Local\Programs\Python\Python312\python.exe`.
- pip: 26.2.1; pytest: 9.1.1; both module CLIs work.
- Global Python is not the backend selector. Inside the initial sandbox,
  `where.exe python` returned `C:\Python314\python.exe`, and `py -0p` listed
  only 3.14. Normal execution resolved `python --version` to 3.12.10 and
  `py -0p` listed 3.14 (launcher default), 3.12 and 3.11. The recorded
  `backend_sys_executable` is authoritative in every backend command.

CUDA:
- Torch: 2.8.0+cu128.
- Torchaudio: 2.8.0+cu128.
- CUDA: available, PyTorch build 12.8.
- GPU: NVIDIA GeForce RTX 4050 Laptop GPU.
- VRAM: 6.0 GB.
- Real small CUDA kernel: PASS (four ones multiplied by two, sum = 8).
- Torch wheels, driver and CUDA toolkit were not changed.

OMNIVOICE:
- Import: PASS, including real upstream runtime imports (not mocks).
- Source: `D:\Tool Dich Cho Khach\external\OmniVoice\omnivoice\__init__.py`.
- Version: 0.2.1.
- Installed editable from the existing local checkout; `direct_url.json` and
  `_editable_impl_omnivoice.pth` confirm that relationship.
- Upstream commit: `08be0b4ccbac3e13e374e86fbfead4b4cac343e2`.
- No duplicate installation or upstream source/pyproject changes.
- Source SHA256 values are recorded in the runtime snapshot.

BACKEND DEPENDENCIES:

| Package | Audited version | Import |
| --- | --- | --- |
| numpy | 2.5.3 | PASS |
| soundfile | 0.14.0 | PASS |
| librosa | 1.0.0 | PASS |
| pydub | 0.25.1 | PASS |
| transformers | 5.17.0 | PASS |
| accelerate | 1.15.0 | PASS |
| gradio | 6.27.0 | PASS |
| fastapi | 0.141.1 | PASS |
| uvicorn | 0.52.4 | PASS |
| pydantic | 2.13.5 | PASS |
| psutil | 7.2.2 | PASS |
| tensorboardX | 2.6.5 | PASS |
| webdataset | 1.0.2 | PASS |
| pytest | 9.1.1 | PASS |

`requirements-backend.txt` declares one editable local OmniVoice dependency and
pins its direct dependencies plus the application/test dependencies to the
existing environment. `constraints-backend.txt` protects the exact CUDA wheels.
Torch install commands use the CUDA index separately; pip is not expected to
understand upstream's uv index configuration. `pip check` reports no broken
requirements. The audit also compares every checked-in exact pin with installed
distribution metadata. No new package was selected from an unverified latest
release; these are observed, working versions.

FFMPEG:
- `ffmpeg -version`: PASS.
- `ffprobe -version`: PASS.
- Resolved executables: `C:\ffv2\bin\ffmpeg.exe`, `C:\ffv2\bin\ffprobe.exe`.
- Both version 2025-06-02-git-688f3944ce-full_build-www.gyan.dev.
- `where.exe` also lists a second installation under
  `C:\FFmpeg\ffmpeg-master-latest-win64-gpl-shared`; the first PATH entry wins.
- PowerShell and Python subprocess lookup work without application hard-coded
  binary paths. No bundle or PATH change was made.

ENVIRONMENT CHANGES:
- None to installed packages, pyvenv.cfg, base Python, activation internals,
  registry, machine PATH, ACLs, GPU drivers or models.
- Added a project activation helper that changes only the current PowerShell
  environment: venv activation, prototype PYTHONPATH and offline variables.
- Corrected current documentation to identify one official runtime.
- Initial startup failure was sandbox access denial, not a broken venv:
  the sandbox returned `Unable to create process` through the venv launcher,
  while direct base Python execution returned `Access denied`; `Test-Path`
  confirmed the executable existed. Outside-sandbox execution immediately
  returned Python 3.12.10 and successful pip/pytest versions without a repair.
- Consequently, the earlier analysis that the OmniVoice interpreter could not
  start must be read as sandbox-specific, not a host-wide environment failure.

PACKAGES INSTALLED:
None. No upgrades, downgrades or reinstallations.

TESTS:
- Targeted: **92 passed**, 1 warning, 1.75 s.
- Broader: **103 passed**, 1 warning, 2.04 s.
- Both used the exact official interpreter and `PYTHONPATH=prototype`.
- Targeted scope: provider, cloning, languages, long_text,
  long_text_manager and audio_boundary test files listed in the user request.
- Broader scope: `prototype/tests tests`; no expensive `run_*.py` benchmark.
- Runtime audit: required package/core imports, exact dependency pins,
  pip/pytest CLIs, pip check, CUDA kernel, FFmpeg and FFprobe.
- Activation helper: actually executed, verified sys.executable, imported
  TTSManager, OmniVoiceProvider, FastAPI and Uvicorn. No server started.
- PowerShell script parser: PASS.
- GPU smoke: **REUSED** historical `reports/cp02a_omnivoice_smoke.json`.
  Prior Python 3.12.10 / Torch 2.8.0+cu128 / RTX 4050 matches this runtime;
  no environment packages were changed in this checkpoint. Both existing WAVs
  were reread now with the official runtime: finite, nonempty, mono, 24 kHz,
  nonzero peaks, durations 3.46 s and 3.01 s. Current hashes were recorded.
  No new model inference was run. Historical audio validation is not a new
  model-cache or perceptual-quality certification.

FILES CREATED:
- `requirements-backend.txt`
- `constraints-backend.txt`
- `docs/backend_runtime.md`
- `scripts/activate_backend.ps1`
- `scripts/audit_backend_runtime.py`
- `reports/cp03b0_runtime_contract.md`
- `reports/cp03b0_runtime_versions.txt`
- `reports/cp03b0_runtime_audit.log`
- `reports/cp03b0_installed_packages.json`
- `reports/cp03b0_targeted_tests.log`
- `reports/cp03b0_broader_tests.log`
- `reports/cp03b0_gpu_smoke_reuse.json`

FILES CHANGED:
- `prototype/README.md`: replace competing current runtime instructions with
  the official runtime contract; distinguish legacy app/provider behavior.
- `prototype/requirements.txt`: comments only, explicitly mark the historical
  legacy provider snapshot; preserve all existing dependency entries.
- `prototype/providers/OMNIVOICE.md`: link current runtime authority and label
  old checkpoint commands as historical.

RUNTIME DECISION:
**REUSE_EXISTING_VENV** — `external/OmniVoice/.venv312`.
No second official backend environment was created or selected.

REPOSITORY STATE / INSTRUCTIONS:
- Root workspace: **NOT A GIT REPOSITORY**. No root commit/diff is fabricated.
- Nested `external/OmniVoice` is a Git checkout at the commit above. Its tracked
  diff is empty. Existing untracked venv, benchmark outputs/scripts and sample
  audio were retained; no staging or commits were performed. Scoped Git
  `safe.directory` was supplied on read-only commands to inspect the checkout;
  global Git configuration was not modified.
- Read: user CP0.3B-0 attachment, `Rule/RULES.txt`, `Rule/AGENTS.md` (empty),
  prototype requirements/README, upstream pyproject, provider documentation and
  prior CP0.2A runtime/smoke evidence. No Master Prompt file was found in the
  repository file inventory.
- Baseline: interpreter blocked only in sandbox; unchanged host runtime passed
  imports, dependency checks and all targeted/broader tests before documentation
  and launcher completion. No production failure was repaired or hidden.
- Added runtime audit checks rather than changing model/core tests. Reviewed
  created scripts, dependency pins and edited documentation. Root Git diff is
  unavailable; scope is listed explicitly above.

SECURITY / PRIVACY / LICENSE IMPACT:
- No customer text/audio is logged by the new runtime audit. Evidence contains
  requested executable/package paths and versions, no environment-variable dump
  or credential values. Reused artifacts contain existing synthetic smoke text.
- No downloads, telemetry, network service, model modifications or generated
  model/audio binaries were added. FastAPI is imported only.
- No new library/binary was installed or bundled. Pinning existing distributions
  is not commercial-license or redistribution approval. Existing FFmpeg build
  and upstream licensing still require the product's release review.

LIMITATIONS:
- Codex sandbox execution may require the approved outside-sandbox path because
  the base Python directory is inaccessible to the sandbox identity. A normal
  PowerShell session uses the existing runtime successfully.
- pydub emits the known audioop deprecation warning for Python 3.13 removal;
  this contract intentionally remains on Python 3.12.
- A clean-machine install and a complete reproducible transitive lock have not
  been tested. The requirements are audited direct pins, plus editable upstream
  source. The installed package inventory is evidence, not a universal lockfile.
- No fresh speech-model load/synthesis or model-cache identity test was run;
  optional GPU inference evidence is explicitly historical. Current CUDA kernel
  execution and real upstream imports passed.
- Optional legacy Sherpa/ORT/VieNeu live inference and old app.py startup are
  not acceptance criteria here and are not certified by these core/OmniVoice
  checks. The old default provider registration remains unchanged.
- No API skeleton, routes, persistence, job queue or UI changes were made.

NEXT:
CP0.3B-1 — Application/FastAPI Backend Skeleton.
STOP. Not started automatically.
