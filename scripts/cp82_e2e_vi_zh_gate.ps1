$ErrorActionPreference = 'Stop'

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mainPython = Join-Path $root '.runtime\cp82\runtime-main\python.exe'
$workerPython = Join-Path $root '.runtime\cp82\runtime-chatterbox\python.exe'
$backendRoot = Join-Path $root '.runtime\cp82\runtime-main\app'
$gates = Join-Path $root '.runtime\cp82\gates'
$stdout = Join-Path $gates 'vi-zh-e2e-backend.stdout.log'
$stderr = Join-Path $gates 'vi-zh-e2e-backend.stderr.log'
$reportPath = Join-Path $gates 'vi-zh-e2e-report.json'
$e2eWav = Join-Path $gates 'vi-zh-e2e.wav'
$port = 8017

New-Item -ItemType Directory -Force -Path $gates | Out-Null
Remove-Item -LiteralPath $stdout,$stderr,$reportPath,$e2eWav -Force -ErrorAction SilentlyContinue
$env:HF_HOME = Join-Path $root '.runtime\cp81b\models\huggingface'
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME 'hub'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
Remove-Item Env:HF_TOKEN -ErrorAction SilentlyContinue
$env:LOCAL_AI_CHATTERBOX_PYTHON = $workerPython
$env:LOCAL_AI_APP_DATA_DIR = Join-Path $env:LOCALAPPDATA 'Voca Basic'
$env:LOCAL_AI_PORT = "$port"
$env:LOCAL_AI_REQUIRE_LOCAL_TOKEN = '1'
$env:LOCAL_AI_WARM_UP_ON_START = '0'
$env:LOCAL_AI_SERVE_FRONTEND = '0'

$report = [ordered]@{
    parent_executable = $mainPython
    worker_executable = $workerPython
    backend_origin = $backendRoot
    network_used = $false
    hf_token_used = $false
    user_hf_cache_used = $false
    translation_status = 'NOT_RUN'
    source_language = 'vi'
    target_language = 'zh'
    routed_provider = $null
    tts_status = 'NOT_RUN'
    wav_valid = $false
}
$process = $null
try {
    $process = Start-Process -FilePath $mainPython -ArgumentList @('-E', '-s', '-m', 'backend.main') -WorkingDirectory $backendRoot -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    $report.backend_pid = $process.Id
    $base = "http://127.0.0.1:$port"
    $token = $null
    for ($i = 0; $i -lt 90; $i++) {
        try {
            $token = (Invoke-RestMethod -Uri "$base/api/auth/token" -TimeoutSec 2).token
            if ($token) { break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $token) { throw 'PORTABLE_BACKEND_START_OR_AUTH_FAILED' }
    $headers = @{ 'X-Local-Token' = $token }
    $body = @{ text = 'Xin chào, đây là kiểm tra dịch tiếng Trung ngoại tuyến.'; source_language = 'vi'; language = 'zh'; voice_id = 'chatterbox_default'; speed = 1.0; format = 'wav' } | ConvertTo-Json -Compress
    # This is the explicit real Gemini E2E request requested for Task 4B.
    $response = Invoke-RestMethod -Method Post -Uri "$base/api/tts" -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 600
    $report.network_used = $true
    $report.translation_status = 'PASS'
    $report.routed_provider = $response.data.provider
    $report.tts_status = if ($response.ok) { 'PASS' } else { 'FAIL' }
    $report.api_response = $response
    $audio = Invoke-WebRequest -Uri "$base$($response.data.audio_url)" -Headers $headers -OutFile $e2eWav -TimeoutSec 30
    if (Test-Path -LiteralPath $e2eWav) {
        $report.wav_size = (Get-Item -LiteralPath $e2eWav).Length
        $report.wav_valid = $report.wav_size -gt 44
    }
} catch {
    $report.error = $_.Exception.Message
    $report.tts_status = 'FAIL'
} finally {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
        $process.WaitForExit(15000) | Out-Null
    }
    $report.backend_exit_code = if ($process -and $process.HasExited) { $process.ExitCode } else { $null }
    $report.stdout = if (Test-Path -LiteralPath $stdout) { Get-Content -LiteralPath $stdout -Raw } else { '' }
    $report.stderr = if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Raw } else { '' }
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding utf8
    $report | ConvertTo-Json -Depth 8
}
if ($report.tts_status -ne 'PASS' -or -not $report.wav_valid) { exit 1 }
