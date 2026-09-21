# Run from any working directory. No installs, model probes or frontend startup.
$backendRoot = Split-Path -Parent $PSScriptRoot
$backendPython = (Get-Command python -ErrorAction Stop).Source
& $backendPython -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Official Python 3.12 unavailable; see docs/backend_runtime.md.' }
$env:PYTHONPATH = $backendRoot
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
# UX: without this, the primary provider only loads its model on the first
# real TTS request after this process
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

# "Cửa sổ app thật" (17/09, scripts/run_app.py): nếu đã cài `pywebview`
# (thấy trong requirements-backend.txt, tuỳ chọn - không bắt buộc), mở MỘT
# cửa sổ desktop riêng (không phải tab trình duyệt, không thanh địa chỉ)
# thay vì mở trình duyệt mặc định. Kiểm tra bằng một tiến trình python RIÊNG
# chạy `import webview` trước - rẻ, không đụng gì tới CUDA/torch - để quyết
# định dùng cách nào; chưa cài thì tự rơi về mở tab trình duyệt như cũ,
# không báo lỗi, không bắt buộc phải cài pywebview mới chạy được sản phẩm.
& $backendPython -c 'import webview' 2>$null
$hasWebview = ($LASTEXITCODE -eq 0)

if ($hasWebview) {
    Write-Host 'Đã có pywebview - mở cửa sổ app thật (không phải tab trình duyệt)...'
    & $backendPython (Join-Path $backendRoot 'scripts\run_app.py')
    if ($LASTEXITCODE -ne 0) { throw 'App exited with an error. Review console diagnostics.' }
} else {
    Write-Host 'Chưa cài pywebview - mở bằng tab trình duyệt như trước (pip install pywebview pythonnet vào .venv312 nếu muốn cửa sổ app thật, xem requirements-backend.txt).'
    # Mở trình duyệt tới đúng origin backend đang phục vụ (127.0.0.1, khớp
    # DEFAULT_API_BASE_URL trong frontend/src/services/httpClient.ts -
    # "localhost" và "127.0.0.1" là hai origin KHÁC NHAU với trình duyệt).
    # Chạy nền, trễ vài giây vì không có cách chờ tín hiệu "Uvicorn đã sẵn
    # sàng" ở đây - nếu trang báo lỗi không kết nối được, tải lại (F5) sau
    # vài giây là được.
    Start-Job -ScriptBlock { Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000/' } | Out-Null

    & $backendPython -m backend.main
    if ($LASTEXITCODE -ne 0) { throw 'Backend exited with an error. Review console diagnostics.' }
}
