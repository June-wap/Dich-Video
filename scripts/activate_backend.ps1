# Dot-source from PowerShell: . .\scripts\activate_backend.ps1
# Activates the sole official backend runtime; never starts a server.
$backendRoot = Split-Path -Parent $PSScriptRoot
$backendVenv = Join-Path $backendRoot 'external\OmniVoice\.venv312'
$backendPython = Join-Path $backendVenv 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $backendPython -PathType Leaf)) {
    throw 'Official backend interpreter missing. See docs/backend_runtime.md.'
}
& $backendPython -c 'import sys; print(sys.executable); print(sys.version); sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)'
if ($LASTEXITCODE -ne 0) {
    throw 'Official Python 3.12 could not run. Check base-interpreter access before repairing the venv.'
}
. (Join-Path $backendVenv 'Scripts\Activate.ps1')
# Do not inherit another environment through PYTHONPATH.
$env:PYTHONPATH = Join-Path $backendRoot 'prototype'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
& $backendPython -c 'import torch; print("Torch:", torch.__version__); print("CUDA:", torch.cuda.is_available()); print("GPU:", torch.cuda.get_device_name(0) if torch.cuda.is_available() else "N/A"); sys_ok = torch.__version__ == "2.8.0+cu128" and torch.cuda.is_available(); raise SystemExit(0 if sys_ok else 1)'
if ($LASTEXITCODE -ne 0) {
    throw 'CUDA baseline check failed. Do not reinstall Torch blindly; run the runtime audit.'
}
