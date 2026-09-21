# Clean Room Verification & Smoke Gate Script
param(
    [string]$CoreAppDir = "D:\Tool Dich Cho Khach\release\core-dist\Voca Basic Core",
    [string]$AiPackagesDir = "F:\Voca-AI-Packages",
    [string]$TestRoot = "F:\Voca-Clean-Release-Test"
)

$ErrorActionPreference = 'Stop'

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "      VOCA BASIC - CLEAN ROOM SMOKE VERIFICATION       " -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

# 1. Check prerequisites
if (-not (Test-Path -LiteralPath (Join-Path $CoreAppDir "Voca Basic.exe"))) {
    throw "Core App executable missing: $CoreAppDir\Voca Basic.exe"
}
if (-not (Test-Path -LiteralPath $AiPackagesDir)) {
    throw "AI Packages directory missing: $AiPackagesDir"
}

# 2. Setup Clean Room
Write-Host "`n[1/5] Setting up Clean Room environment at: $TestRoot" -ForegroundColor Yellow
if (Test-Path -LiteralPath $TestRoot) {
    Remove-Item -LiteralPath $TestRoot -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Force -Path $TestRoot | Out-Null

$cleanAppDir = Join-Path $TestRoot "Voca Basic Core"
Write-Host "  -> Copying Core App..."
Copy-Item -LiteralPath $CoreAppDir -Destination $cleanAppDir -Recurse -Force

# Setup sibling ai-packages
$cleanAiPackages = Join-Path $cleanAppDir "ai-packages"
New-Item -ItemType Directory -Force -Path $cleanAiPackages | Out-Null

Write-Host "`n[2/5] Deploying AI Packages into Clean Room (Extracting from .7z)..." -ForegroundColor Yellow
$sevenZip = "C:\Program Files\7-Zip\7z.exe"
foreach ($pkg in @("runtime-main", "runtime-chatterbox", "models")) {
    $archive = Join-Path $AiPackagesDir "$pkg.7z"
    $destPkg = Join-Path $cleanAiPackages $pkg
    if (Test-Path -LiteralPath $archive) {
        Write-Host "  -> Extracting $pkg.7z into $destPkg..." -ForegroundColor Cyan
        New-Item -ItemType Directory -Force -Path $destPkg | Out-Null
        & $sevenZip x $archive -o"$destPkg" -y | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to extract $archive with code $LASTEXITCODE"
        }
    } elseif (Test-Path -LiteralPath (Join-Path $AiPackagesDir $pkg)) {
        Write-Host "  -> Copying uncompressed $pkg..."
        Copy-Item -LiteralPath (Join-Path $AiPackagesDir $pkg) -Destination $destPkg -Recurse -Force
    } else {
        throw "Neither archive $pkg.7z nor folder found in $AiPackagesDir"
    }
}

# 3. Verify Files and Hashes
Write-Host "`n[3/5] Verifying Clean Room critical payloads..." -ForegroundColor Yellow
$cleanPython = Join-Path $cleanAiPackages "runtime-main\python.exe"
$cleanChatterbox = Join-Path $cleanAiPackages "runtime-chatterbox\python.exe"
$cleanHub = Join-Path $cleanAiPackages "models\huggingface\hub"

foreach ($p in @($cleanPython, $cleanChatterbox, $cleanHub)) {
    if (-not (Test-Path -LiteralPath $p)) {
        throw "Verification failed: missing clean payload: $p"
    }
    Write-Host "  [OK] Found: $p" -ForegroundColor Green
}

# 4. Smoke Test: Backend Process Startup & Health
Write-Host "`n[4/5] Running Smoke Test: Launching Backend in Clean Room..." -ForegroundColor Yellow
$cleanAppData = Join-Path $TestRoot "app-data"
New-Item -ItemType Directory -Force -Path $cleanAppData | Out-Null
$cleanAudio = Join-Path $cleanAppData "audio"
$cleanDb = Join-Path $cleanAppData "data\metadata.sqlite3"
$cleanToken = Join-Path $cleanAppData "runtime\session.token"

# Backend source is located in resources/backend (Core App) or runtime-main/app
$backendSource = Join-Path $cleanAppDir "resources\backend"
if (-not (Test-Path -LiteralPath $backendSource)) {
    $backendSource = Join-Path $cleanAiPackages "runtime-main\app"
}
if (-not (Test-Path -LiteralPath $backendSource)) {
    throw "Backend source directory not found in Clean Room!"
}

# The parent directory containing 'backend' folder
$backendRoot = if (Test-Path (Join-Path $backendSource "backend")) { $backendSource } else { Split-Path -Parent $backendSource }

$envVars = @{
    "LOCAL_AI_APP_DATA_DIR" = $cleanAppData
    "LOCAL_AI_DATA_ROOT" = $cleanAppData
    "LOCAL_AI_OUTPUT_DIR" = $cleanAudio
    "LOCAL_AI_DATABASE_PATH" = $cleanDb
    "LOCAL_AI_TOKEN_PATH" = $cleanToken
    "LOCAL_AI_REQUIRE_LOCAL_TOKEN" = "1"
    "LOCAL_AI_WARM_UP_ON_START" = "0"
    "LOCAL_AI_HOST" = "127.0.0.1"
    "LOCAL_AI_PORT" = "8000"
    "LOCAL_AI_CHATTERBOX_PYTHON" = $cleanChatterbox
    "HF_HOME" = (Join-Path $cleanAiPackages "models\huggingface")
    "HF_HUB_CACHE" = $cleanHub
    "HF_HUB_OFFLINE" = "1"
    "TRANSFORMERS_OFFLINE" = "1"
    "PYTHONPATH" = "$backendRoot;$backendSource"
}

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $cleanPython
$psi.Arguments = "-m backend.main"
$psi.WorkingDirectory = $backendRoot
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true

foreach ($k in $envVars.Keys) {
    $psi.EnvironmentVariables[$k] = $envVars[$k]
}

$backendProc = [System.Diagnostics.Process]::Start($psi)
Write-Host "  -> Backend process started (PID: $($backendProc.Id))"

$token = $null
$healthy = $false
$deadline = (Get-Date).AddSeconds(45)

try {
    Write-Host "  -> Waiting for /api/health..."
    while ((Get-Date) -lt $deadline) {
        if ($backendProc.HasExited) {
            $err = $backendProc.StandardError.ReadToEnd()
            throw "Backend exited prematurely with code $($backendProc.ExitCode). Error: $err"
        }

        if (-not $token) {
            try {
                $tokenResp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/auth/token" -Method Get -TimeoutSec 2 -ErrorAction Stop
                if ($tokenResp.token) {
                    $token = $tokenResp.token
                    Write-Host "  -> Session token acquired successfully." -ForegroundColor Green
                }
            } catch { }
        }

        if ($token) {
            try {
                $headers = @{ "X-Local-Token" = $token }
                $healthResp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -Method Get -Headers $headers -TimeoutSec 2 -ErrorAction Stop
                if ($healthResp.status -eq "ok") {
                    $healthy = $true
                    Write-Host "  -> Backend reached HEALTHY state! (Version: $($healthResp.version))" -ForegroundColor Green
                    break
                }
            } catch { }
        }
        Start-Sleep -Milliseconds 500
    }

    if (-not $healthy) {
        throw "Backend did not become healthy within 45 seconds."
    }

    # 5. Synthesis test
    Write-Host "`n[5/5] Testing Vietnamese TTS Synthesis via API..." -ForegroundColor Yellow
    $ttsPayload = @{
        text = "Xin chào, hệ thống Voca Basic đã kiểm tra hoàn tất."
        language = "vi"
        format = "wav"
        speed = 1.0
    } | ConvertTo-Json

    $headers = @{
        "X-Local-Token" = $token
        "Content-Type" = "application/json"
    }

    $ttsResp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/tts" -Method Post -Headers $headers -Body $ttsPayload -TimeoutSec 30
    Write-Host "  -> Synthesis Job submitted/completed: Job ID $($ttsResp.job_id), Status: $($ttsResp.status)" -ForegroundColor Green

    if ($ttsResp.status -eq "COMPLETED" -and $ttsResp.audio_url) {
        Write-Host "  -> Audio URL: $($ttsResp.audio_url)" -ForegroundColor Green
        # Verify file on disk
        $audioFiles = Get-ChildItem -LiteralPath $cleanAudio -Filter "*.wav"
        if ($audioFiles.Count -gt 0) {
            Write-Host "  -> Audio output verified on disk: $($audioFiles[0].FullName) ($($audioFiles[0].Length) bytes)" -ForegroundColor Green
        } else {
            throw "TTS reported COMPLETED but no WAV audio found in $cleanAudio"
        }
    } else {
        throw "TTS synthesis failed or returned non-completed status: $($ttsResp.status)"
    }

    Write-Host "`n=======================================================" -ForegroundColor Green
    Write-Host " CLEAN ROOM VERIFICATION PASSED 100%! READY TO SHIP!  " -ForegroundColor Green
    Write-Host "=======================================================" -ForegroundColor Green

} finally {
    if (-not $backendProc.HasExited) {
        Write-Host "`nTerminating clean room backend process..." -ForegroundColor Gray
        $backendProc.Kill()
        $backendProc.WaitForExit(5000)
    }
}
