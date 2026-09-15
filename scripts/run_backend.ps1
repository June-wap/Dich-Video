# Run from any working directory. No installs, model probes or frontend startup.
$backendRoot = Split-Path -Parent $PSScriptRoot
$backendPython = Join-Path $backendRoot 'external\OmniVoice\.venv312\Scripts\python.exe'
& $backendPython -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Official Python 3.12 unavailable; see docs/backend_runtime.md.' }
$env:PYTHONPATH = $backendRoot + [IO.Path]::PathSeparator + (Join-Path $backendRoot 'prototype')
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
& $backendPython -m backend.main
if ($LASTEXITCODE -ne 0) { throw 'Backend exited with an error. Review console diagnostics.' }
