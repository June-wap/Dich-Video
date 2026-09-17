# Run from any working directory. No installs, model probes or frontend startup.
$backendRoot = Split-Path -Parent $PSScriptRoot
$backendPython = Join-Path $backendRoot 'external\OmniVoice\.venv312\Scripts\python.exe'
& $backendPython -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Official Python 3.12 unavailable; see docs/backend_runtime.md.' }
$env:PYTHONPATH = $backendRoot + [IO.Path]::PathSeparator + (Join-Path $backendRoot 'prototype')
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
# Security P0 (checklist-bao-mat-truoc-dong-goi-17-09.md item 1): this is the
# ONLY place that turns on the local API auth token for a real run - backend
# tests deliberately default this off (see Settings.require_local_token's
# docstring in backend/config.py) so this script is what makes every actual
# launch of the product require it. The token itself is generated fresh at
# each startup (backend/main.py's lifespan) - never set it to a fixed value
# here.
$env:LOCAL_AI_REQUIRE_LOCAL_TOKEN = '1'
# UX: without this, the primary provider (and Piper, for its 6 languages)
# only loads its model on the first real TTS request after this process
# starts - a customer who opens the app and immediately clicks "Tạo giọng
# nói" would eat that load time as part of their first job. This starts
# loading in a background thread right away instead (see
# Settings.warm_up_on_start's docstring in backend/config.py) - off by
# default for tests, on for every real run via this script.
$env:LOCAL_AI_WARM_UP_ON_START = '1'

# "1 tiến trình, 1 cổng" (mục tiêu đóng gói 17/09): backend tự phục vụ luôn
# bản build frontend (frontend/dist) thay vì bắt chạy `npm run dev` ở một
# cổng riêng - xem Settings.serve_frontend trong backend/config.py. Build tự
# động CHỈ khi frontend/dist còn thiếu (lần chạy đầu tiên trên máy này); nếu
# đã có sẵn thì bỏ qua để khởi động nhanh - sau khi sửa code frontend, tự
# `npm run build` lại (trong thư mục frontend) hoặc xoá frontend/dist để
# script build lại từ đầu.
$frontendDir = Join-Path $backendRoot 'frontend'
$frontendIndexHtml = Join-Path $frontendDir 'dist\index.html'
if (-not (Test-Path $frontendIndexHtml)) {
    Write-Host 'frontend/dist chưa có - đang build frontend lần đầu (npm run build)...'
    Push-Location $frontendDir
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'npm run build thất bại - xem log ở trên rồi thử lại.' }
    } finally {
        Pop-Location
    }
}
$env:LOCAL_AI_SERVE_FRONTEND = '1'

# Mở trình duyệt tới đúng origin backend đang phục vụ (127.0.0.1, khớp
# DEFAULT_API_BASE_URL trong frontend/src/services/httpClient.ts - "localhost"
# và "127.0.0.1" là hai origin KHÁC NHAU với trình duyệt). Chạy nền, trễ vài
# giây vì không có cách chờ tín hiệu "Uvicorn đã sẵn sàng" ở đây - nếu trang
# báo lỗi không kết nối được, tải lại (F5) sau vài giây là được.
Start-Job -ScriptBlock { Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000/' } | Out-Null

& $backendPython -m backend.main
if ($LASTEXITCODE -ne 0) { throw 'Backend exited with an error. Review console diagnostics.' }
