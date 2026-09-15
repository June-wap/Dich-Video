# Backend runtime contract — CP0.3B-0

Decision: **REUSE_EXISTING_VENV**. The sole official backend runtime is
`external/OmniVoice/.venv312`, Python **3.12.x**, audited at **3.12.10, Windows x64**.
On this machine its interpreter is:
`D:\Tool Dich Cho Khach\external\OmniVoice\.venv312\Scripts\python.exe`.

This contract covers OmniVoice, prototype core, the regression suite, and the
future FastAPI application. Existing `.cp0` environments are historical research
environments, not alternative official backends. Python 3.14 is not supported
for this backend, even if selected by the global Python launcher.

## Use the existing installation

From PowerShell in the repository root:

```powershell
Set-Location 'D:\Tool Dich Cho Khach'
. .\scripts\activate_backend.ps1
python -c "import sys; print(sys.executable)"
python -m pip check
```

The helper activates the venv, sets `PYTHONPATH` to the absolute `prototype`
directory, enables Hugging Face/Transformers offline mode, and checks Torch/CUDA.
It starts no server and does not edit machine-wide environment variables.
Alternatively, activate manually:

```powershell
& .\external\OmniVoice\.venv312\Scripts\Activate.ps1
$env:PYTHONPATH = Join-Path (Get-Location).Path 'prototype'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
```

Activation is optional if every command uses the explicit official interpreter.
Use `python -m pip`, `python -m pytest`, and later `python -m uvicorn`; do not rely
on bare `pip`, `pytest`, or `uvicorn` resolving to the correct installation.

## Audit and sandbox diagnosis

```powershell
& .\external\OmniVoice\.venv312\Scripts\python.exe scripts\audit_backend_runtime.py
```

Add `--output reports\cp03b0_runtime_versions.txt` only when intentionally
refreshing the checkpoint snapshot. The audit imports dependencies/core,
checks the source checkout, runs pip consistency checks and a tiny CUDA kernel,
and tests FFmpeg/FFprobe. It does not load a speech model or download anything.

The initial Codex sandbox could not execute the base Python and reported
`Unable to create process`. Direct execution of that base interpreter returned
`Access denied`; the file existed. The same unmodified venv passed outside the
sandbox. **Do not repair pyvenv.cfg or reinstall Python in response to that
sandbox-only symptom.** Use a normal PowerShell session, or the approved
outside-sandbox command path. No ACL or global PATH change was made.

The venv depends on the existing Python 3.12.10 installation referenced by
`pyvenv.cfg`. It is not portable to another machine. On this host the global
Python command differed between sandbox and normal execution; the explicit
backend interpreter above is authoritative.

## Dependency ownership and versions

`requirements-backend.txt` owns the project baseline; `constraints-backend.txt`
protects the exact Torch/Torchaudio CUDA builds. `external/OmniVoice/pyproject.toml`
remains upstream-owned and unchanged. OmniVoice 0.2.1 is already installed
editable from `external/OmniVoice`; it imports from that source checkout, not a
second wheel installation. Its dependency declarations include Torch/Torchaudio
>=2.4, Transformers >=5.3.0, Accelerate, pydub, Gradio, tensorboardX, webdataset,
NumPy, SoundFile and librosa. Upstream uv configuration constrains Torch and
Torchaudio to 2.8.0 and selects the CUDA 12.8 index on Windows/Linux; pip does not
automatically interpret those uv settings.

Audited additions for application/tests are FastAPI 0.141.1, Uvicorn 0.52.4,
Pydantic 2.13.5, pytest 9.1.1 and psutil 7.2.2. All were already installed.
The complete checked import/version evidence is in
`reports/cp03b0_runtime_versions.txt`; the installed distribution inventory is
`reports/cp03b0_installed_packages.json` (evidence, not a portable lockfile).

`prototype/requirements.txt` is a legacy provider snapshot. Do not install it
over this environment or treat it as the backend installer. Sherpa, Japanese
ORT and VieNeu live inference are outside this checkpoint's accepted runtime
scope; their modules are lazy adapters and the default old `prototype/app.py`
still registers those providers rather than OmniVoice. This checkpoint does
not claim that legacy app can launch with all its optional engines installed.

## Installation on a new developer machine

No installation was needed on the audited machine. These commands document
provisioning on another Windows x64 machine with a working Python 3.12 and
compatible NVIDIA driver. Do not recreate an existing healthy venv.

```powershell
# Only if the official venv is absent on the new machine:
py -3.12 -m venv external\OmniVoice\.venv312
$backendPython = '.\external\OmniVoice\.venv312\Scripts\python.exe'
& $backendPython -m pip install torch==2.8.0+cu128 torchaudio==2.8.0+cu128 --index-url https://download.pytorch.org/whl/cu128
& $backendPython -m pip install -r requirements-backend.txt
& $backendPython -m pip check
& $backendPython scripts\audit_backend_runtime.py
```

Run each step only if the previous command succeeds. Dependency installation
needs package access; offline inference additionally requires model weights and
the audio tokenizer already present in local cache. These commands do not fetch
model weights. CUDA build 12.8 belongs to the PyTorch wheel contract; installing
or upgrading a standalone CUDA toolkit is not part of this checkpoint.

For an update, first audit and review the intended version diff. Preview with
`python -m pip install --dry-run -r requirements-backend.txt`, preserve the CUDA
constraints, then install only the reviewed change and rerun audit/tests.
Never use an unreviewed `pip install -U`. Direct dependency pins plus the local
upstream checkout are the contract; a fresh-machine/full transitive lock
reproduction has not been verified by CP0.3B-0.

## FFmpeg

Both `ffmpeg -version` and `ffprobe -version` must work from PowerShell and from
the Python process using PATH. Find them with `where.exe ffmpeg` and
`where.exe ffprobe`. The audited host resolves `C:\ffv2\bin` first; this is
evidence, not an application hard-coded path. Version: 2025-06-02 git-688f3944ce
full build. A second installation is also on PATH; command resolution order
matters. No FFmpeg bundling, PATH editing, or redistribution approval is implied.

## Tests

```powershell
. .\scripts\activate_backend.ps1
python -m pytest prototype/tests/test_omnivoice_provider.py prototype/tests/test_omnivoice_cloning.py prototype/tests/test_omnivoice_languages.py prototype/tests/test_long_text.py prototype/tests/test_long_text_manager.py prototype/tests/test_audio_boundary.py -v
python -m pytest prototype/tests tests -v
```

Checkpoint results: targeted 92 passed; broader 103 passed. A pydub `audioop`
deprecation warning is non-blocking on Python 3.12. These suites do not replace
live model quality verification. No new long-form or multilingual benchmark
is required for this environment-only checkpoint.

## FastAPI startup — CP0.3B-2

`backend.main:app` now includes health, system-status and provider-status routes.
CP0.3B-2 registers one lazy OmniVoice primary provider per app lifespan, without
loading its model at startup. It uses the same official interpreter. From the repository root:

```powershell
& .\scripts\run_backend.ps1
```

The run helper sets absolute repository/prototype import paths and starts the
server on loopback by default. It creates the provider object but does not load
AI models at startup.
The activation helper remains separate and starts no server. Exact Uvicorn
command, configuration, response contracts and tests: [backend README](../backend/README.md).
