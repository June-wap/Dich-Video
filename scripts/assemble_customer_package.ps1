# scripts/assemble_customer_package.ps1
# Authoritative Assembly and Verification Script for Voca Basic 1.0.1 Customer Package
param(
    [string]$CandidateCoreDir = "",
    [string]$CustomerDistDir = "release\Voca-Basic-1.0.1-Customer"
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$customerRoot = Join-Path $root $CustomerDistDir
$vocaBasicDir = Join-Path $customerRoot "Voca Basic"
$aiPackagesDir = Join-Path $customerRoot "AI-Packages"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "     VOCA BASIC 1.0.1 - ASSEMBLE CUSTOMER PACKAGE                " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Resolve Candidate Core App Directory
if (-not $CandidateCoreDir) {
    # Find latest candidate in release\core-dist\
    $candidates = Get-ChildItem -Path (Join-Path $root 'release\core-dist') -Directory | Where-Object { $_.Name -like "Voca Basic Core*" } | Sort-Object LastWriteTime -Descending
    if (-not $candidates) {
        throw "No Core App candidates found in release\core-dist\. Run scripts/build_core_app.ps1 first."
    }
    $CandidateCoreDir = $candidates[0].FullName
}
Write-Host "Selected Candidate Core: $CandidateCoreDir" -ForegroundColor Green

if (-not (Test-Path -LiteralPath (Join-Path $CandidateCoreDir "Voca Basic.exe"))) {
    throw "Invalid candidate core directory (missing Voca Basic.exe): $CandidateCoreDir"
}

# 2. Ensure Staged Tools
$ffmpegSource = Join-Path $root 'release\bin\ffmpeg.exe'
if (-not (Test-Path -LiteralPath $ffmpegSource)) {
    throw "Missing release\bin\ffmpeg.exe"
}
$sevenZipExe = Join-Path $root 'release\tools\7zip\7z.exe'
$sevenZipDll = Join-Path $root 'release\tools\7zip\7z.dll'
if (-not (Test-Path -LiteralPath $sevenZipExe) -or -not (Test-Path -LiteralPath $sevenZipDll)) {
    throw "Missing 7-Zip binaries in release\tools\7zip"
}

# 3. Prepare Customer Directory Structure
New-Item -ItemType Directory -Force -Path $vocaBasicDir | Out-Null
New-Item -ItemType Directory -Force -Path $aiPackagesDir | Out-Null

# 4. Sync Candidate Core into Voca Basic
Write-Host "`n=== Syncing Core App to Customer Package ===" -ForegroundColor Cyan
Copy-Item -Path "$CandidateCoreDir\*" -Destination $vocaBasicDir -Recurse -Force

# Ensure FFmpeg is present in resources\bin
$targetFfmpeg = Join-Path $vocaBasicDir 'resources\bin\ffmpeg.exe'
if (-not (Test-Path -LiteralPath $targetFfmpeg)) {
    New-Item -ItemType Directory -Force -Path (Join-Path $vocaBasicDir 'resources\bin') | Out-Null
    Copy-Item -LiteralPath $ffmpegSource -Destination $targetFfmpeg -Force
}
Write-Host "  -> Bundled FFmpeg verified: $targetFfmpeg ($((Get-Item $targetFfmpeg).Length) bytes)" -ForegroundColor Green

# Ensure 7-Zip 26.03 tools (7z.exe + 7z.dll) are present, removing stale 7za
Copy-Item -LiteralPath $sevenZipExe -Destination (Join-Path $vocaBasicDir '7z.exe') -Force
Copy-Item -LiteralPath $sevenZipDll -Destination (Join-Path $vocaBasicDir '7z.dll') -Force
if (Test-Path -LiteralPath (Join-Path $vocaBasicDir '7za.exe')) {
    Remove-Item -LiteralPath (Join-Path $vocaBasicDir '7za.exe') -Force
}
Write-Host "  -> 7-Zip 26.03 tools verified: 7z.exe + 7z.dll" -ForegroundColor Green

# 5. Verify AI Packages in AI-Packages\
Write-Host "`n=== Verifying Immutable AI Packages ===" -ForegroundColor Cyan
$expectedAiPackages = @{
    "runtime-main.7z"        = "74649f101b87644ea6be0a15686ab783ffeb7911f4c602c0662660f5e685e5e4"
    "runtime-chatterbox.7z"  = "37efe0882744bcbce9b959ddce0095b21b12eb0e34b5a0ded6c8e627d15a9eca"
    "models.7z"              = "eda475258407bee93c75055984eae1037610b711ab955d66ef824714874a77da"
}

foreach ($pkg in $expectedAiPackages.Keys) {
    $pkgPath = Join-Path $aiPackagesDir $pkg
    if (-not (Test-Path -LiteralPath $pkgPath)) {
        # Check fallback in release-candidates\final-ai-packages\
        $fallback = Join-Path $root "release-candidates\final-ai-packages\$pkg"
        if (Test-Path -LiteralPath $fallback) {
            Write-Host "  -> Copying $pkg from final-ai-packages..."
            Copy-Item -LiteralPath $fallback -Destination $pkgPath -Force
        } else {
            throw "Missing required AI package archive: $pkgPath"
        }
    }
    $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $pkgPath).Hash.ToLowerInvariant()
    $expectedHash = $expectedAiPackages[$pkg]
    if ($actualHash -ne $expectedHash) {
        throw "Hash mismatch for $pkg! Expected $expectedHash, got $actualHash"
    }
    Write-Host "  [OK] $pkg verified: $actualHash" -ForegroundColor Green
}

# 6. Write Updated Customer Batch Files
Write-Host "`n=== Writing Customer Installation & Verification Batch Files ===" -ForegroundColor Cyan

function Write-CustomerBatFile([string]$path, [string]$content) {
    $crlfContent = $content.Replace("`r`n", "`n").Replace("`n", "`r`n")
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($path, $crlfContent, $enc)
}

function Write-CustomerTextFile([string]$path, [string]$content) {
    $crlfContent = $content.Replace("`r`n", "`n").Replace("`n", "`r`n")
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($path, $crlfContent, $enc)
}

$caiDatBat = @'
@echo off
chcp 65001 >nul
setlocal

title Voca Basic - Cài đặt AI Packages

echo ============================================================
echo         VOCA BASIC 1.0.1 - CAI DAT AI PACKAGES
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "APP_DIR=%SCRIPT_DIR%"
set "SEVENZIP=%SCRIPT_DIR%7z.exe"
set "AI_SRC_DIR=%SCRIPT_DIR%..\AI-Packages"
set "TARGET_DIR=%SCRIPT_DIR%ai-packages"

:: 1. Kiem tra cong cu giai nen 7z.exe
if not exist "%SEVENZIP%" (
    echo [LOI] Khong tim thay cong cu giai nen: "%SEVENZIP%"
    echo Vui long dam bao file 7z.exe va 7z.dll nam trong thu muc Voca Basic.
    goto :error_exit
)

:: 2. Kiem tra su ton tai cua thu muc AI-Packages
if not exist "%AI_SRC_DIR%" (
    echo [LOI] Khong tim thay thu muc: "%AI_SRC_DIR%"
    echo Vui long dam bao thu muc AI-Packages nam cung cap voi thu muc Voca Basic.
    goto :error_exit
)

set "FILE_MAIN=%AI_SRC_DIR%\runtime-main.7z"
set "FILE_CB=%AI_SRC_DIR%\runtime-chatterbox.7z"
set "FILE_MODELS=%AI_SRC_DIR%\models.7z"

if not exist "%FILE_MAIN%" (
    echo [LOI] Khong tim thay file: runtime-main.7z
    echo Duong dan tim kiem: "%FILE_MAIN%"
    goto :error_exit
)
if not exist "%FILE_CB%" (
    echo [LOI] Khong tim thay file: runtime-chatterbox.7z
    echo Duong dan tim kiem: "%FILE_CB%"
    goto :error_exit
)
if not exist "%FILE_MODELS%" (
    echo [LOI] Khong tim thay file: models.7z
    echo Duong dan tim kiem: "%FILE_MODELS%"
    goto :error_exit
)

echo [OK] Da tim thay day du 3 goi AI Packages.
echo.

:: 3. Kiem tra dung luong o dia trong (can toi thieu 20 GB)
echo [KIEM TRA] Kiem tra dung luong o dia trong...
powershell -NoProfile -Command "$d = [System.IO.DriveInfo]::new('%~d0'); $gb = [math]::Round($d.AvailableFreeSpace / 1GB, 2); Write-Host \"  Dung luong trong tren o %~d0: $gb GB\"; if ($d.AvailableFreeSpace -lt 21474836480) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [LOI] Dung luong o dia khong du de giai nen!
    echo   Yeu cau toi thieu: 20 GB trong tren o %~d0
    goto :error_exit
)
echo [OK] Dung luong o dia hop le: du tu 20 GB tro len.
echo.

:: 4. Kiem tra tinh toan ven SHA256 truoc khi giai nen
echo [KIEM TRA] Kiem tra ma hash SHA256 cac goi AI...
echo (Qua trinh nay co the mat 1-2 phut de dam bao file khong bi loi download)

echo   Dang kiem tra runtime-main.7z...
powershell -NoProfile -Command "if ((Get-FileHash -Algorithm SHA256 '%FILE_MAIN%').Hash -ne '74649F101B87644EA6BE0A15686AB783FFEB7911F4C602C0662660F5E685E5E4') { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [LOI] runtime-main.7z bi loi hoac khong dung phien ban!
    goto :error_exit
)
echo   [OK] runtime-main.7z hop le.

echo   Dang kiem tra runtime-chatterbox.7z...
powershell -NoProfile -Command "if ((Get-FileHash -Algorithm SHA256 '%FILE_CB%').Hash -ne '37EFE0882744BCBCE9B959DDCE0095B21B12EB0E34B5A0DED6C8E627D15A9ECA') { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [LOI] runtime-chatterbox.7z bi loi hoac khong dung phien ban!
    goto :error_exit
)
echo   [OK] runtime-chatterbox.7z hop le.

echo   Dang kiem tra models.7z...
powershell -NoProfile -Command "if ((Get-FileHash -Algorithm SHA256 '%FILE_MODELS%').Hash -ne 'EDA475258407BEE93C75055984EAE1037610B711AB955D66EF824714874A77DA') { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [LOI] models.7z bi loi hoac khong dung phien ban!
    goto :error_exit
)
echo   [OK] models.7z hop le.
echo.

:: 5. Tien hanh giai nen vao ai-packages
echo ============================================================
echo   BAT DAU GIAI NEN AI PACKAGES
echo ============================================================
echo Thoi gian giai nen uoc tinh 3-7 phut tuy toc do o dia.
echo.

if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"

if exist "%TARGET_DIR%\runtime-main\python.exe" goto :skip_main
echo [1/3] Dang giai nen runtime-main...
"%SEVENZIP%" x -y -aoa -bso0 -bsp1 "%FILE_MAIN%" -o"%TARGET_DIR%\runtime-main"
if not exist "%TARGET_DIR%\runtime-main\python.exe" (
    echo [LOI] Giai nen runtime-main.7z that bai!
    goto :error_exit
)
echo [OK] runtime-main da giai nen xong.
:skip_main
if exist "%TARGET_DIR%\runtime-main\python.exe" echo [OK] runtime-main san sang.
echo.

if exist "%TARGET_DIR%\runtime-chatterbox\python.exe" goto :skip_cb
echo [2/3] Dang giai nen runtime-chatterbox...
"%SEVENZIP%" x -y -aoa -bso0 -bsp1 "%FILE_CB%" -o"%TARGET_DIR%\runtime-chatterbox"
if not exist "%TARGET_DIR%\runtime-chatterbox\python.exe" (
    echo [LOI] Giai nen runtime-chatterbox.7z that bai!
    goto :error_exit
)
echo [OK] runtime-chatterbox da giai nen xong.
:skip_cb
if exist "%TARGET_DIR%\runtime-chatterbox\python.exe" echo [OK] runtime-chatterbox san sang.
echo.

if exist "%TARGET_DIR%\models\huggingface\hub" goto :skip_models
echo [3/3] Dang giai nen models...
"%SEVENZIP%" x -y -aoa -bso0 -bsp1 "%FILE_MODELS%" -o"%TARGET_DIR%\models"
if not exist "%TARGET_DIR%\models\huggingface\hub" (
    echo [LOI] Giai nen models.7z that bai!
    goto :error_exit
)
echo [OK] models da giai nen xong.
:skip_models
if exist "%TARGET_DIR%\models\huggingface\hub" echo [OK] models san sang.
echo.

:: 6. Tao file cau hinh ai-package-config.json
echo {"ai_packages_dir": "./ai-packages"} > "%APP_DIR%ai-package-config.json"

:: 7. Kiem tra toan ven sau giai nen
echo [KIEM TRA] Kiem tra cau truc thu muc sau giai nen...
if not exist "%TARGET_DIR%\runtime-main\python.exe" (
    echo [LOI] Khong tim thay: %TARGET_DIR%\runtime-main\python.exe
    goto :error_exit
)
if not exist "%TARGET_DIR%\runtime-chatterbox\python.exe" (
    echo [LOI] Khong tim thay: %TARGET_DIR%\runtime-chatterbox\python.exe
    goto :error_exit
)
if not exist "%TARGET_DIR%\models\huggingface\hub" (
    echo [LOI] Khong tim thay: %TARGET_DIR%\models\huggingface\hub
    goto :error_exit
)

:: 8. Kiem tra Reparse Points (Junctions / Symlinks)
echo [KIEM TRA] Kiem tra tinh an toan (khong su dung symlink/junction)...
powershell -NoProfile -Command "$rp = Get-ChildItem -Path '%TARGET_DIR%' -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }; if ($rp) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo [LOI] Phat hien reparse point / symlink khong an toan trong ai-packages!
    goto :error_exit
)
echo [OK] Xac nhan 100%% file doc lap (Zero Reparse Points).
echo.

echo ============================================================
echo   CAI DAT AI PACKAGES: THANH CONG
echo ============================================================
echo   Tat ca thanh phan AI da duoc giai nen va xac thuc day du.
echo   He thong san sang hoat dong.
echo.
echo   Buoc tiep theo:
echo   - Chay file "Voca Basic.exe" de bat dau su dung.
echo ============================================================
echo.
pause
exit /b 0

:error_exit
echo.
echo ============================================================
echo   CAI DAT THAT BAI!
echo   Vui long kiem tra lai cac buoc tren hoac xem file HUONG-DAN.txt
echo ============================================================
echo.
pause
exit /b 1
'@
Write-CustomerBatFile (Join-Path $vocaBasicDir 'Cai-Dat-AI-Packages.bat') $caiDatBat

$kiemTraBat = @'
@echo off
chcp 65001 >nul
setlocal

title Voca Basic - Kiểm Tra Cài Đặt

echo ============================================================
echo         VOCA BASIC 1.0.1 - KIEM TRA CAI DAT
echo ============================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "APP_EXE=%SCRIPT_DIR%Voca Basic.exe"
set "RESOURCES_DIR=%SCRIPT_DIR%resources"
set "TARGET_DIR=%SCRIPT_DIR%ai-packages"

set "ERRORS=0"

echo [1] Kiem tra Core App...
if exist "%APP_EXE%" (
    echo   [OK] Voca Basic.exe
) else (
    echo   [LOI] Khong tim thay Voca Basic.exe
    set "ERRORS=1"
)

if exist "%SCRIPT_DIR%7z.exe" (
    echo   [OK] 7z.exe
) else (
    echo   [LOI] Khong tim thay 7z.exe
    set "ERRORS=1"
)

if exist "%SCRIPT_DIR%7z.dll" (
    echo   [OK] 7z.dll
) else (
    echo   [LOI] Khong tim thay 7z.dll
    set "ERRORS=1"
)

if exist "%RESOURCES_DIR%\bin\ffmpeg.exe" (
    echo   [OK] resources\bin\ffmpeg.exe
) else (
    echo   [LOI] Khong tim thay resources\bin\ffmpeg.exe
    set "ERRORS=1"
)

if exist "%RESOURCES_DIR%\backend" (
    echo   [OK] resources\backend
) else (
    echo   [LOI] Khong tim thay resources\backend
    set "ERRORS=1"
)

if exist "%RESOURCES_DIR%\frontend\index.html" (
    echo   [OK] resources\frontend
) else (
    echo   [LOI] Khong tim thay resources\frontend
    set "ERRORS=1"
)

echo.
echo [2] Kiem tra AI Packages...
if exist "%TARGET_DIR%\runtime-main\python.exe" (
    echo   [OK] ai-packages\runtime-main\python.exe
) else (
    echo   [LOI] Khong tim thay ai-packages\runtime-main\python.exe
    set "ERRORS=1"
)

if exist "%TARGET_DIR%\runtime-chatterbox\python.exe" (
    echo   [OK] ai-packages\runtime-chatterbox\python.exe
) else (
    echo   [LOI] Khong tim thay ai-packages\runtime-chatterbox\python.exe
    set "ERRORS=1"
)

if exist "%TARGET_DIR%\models\huggingface\hub" (
    echo   [OK] ai-packages\models\huggingface\hub
) else (
    echo   [LOI] Khong tim thay ai-packages\models\huggingface\hub
    set "ERRORS=1"
)

echo.
echo [3] Kiem tra Symlink / Reparse Points...
powershell -NoProfile -Command "$rp = Get-ChildItem -Path '%TARGET_DIR%' -Recurse -Force -ErrorAction SilentlyContinue | Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }; if ($rp) { exit 1 } else { exit 0 }"
if errorlevel 1 (
    echo   [LOI] Phat hien reparse point trong thu muc!
    set "ERRORS=1"
) else (
    echo   [OK] Xac nhan 100%% file doc lap, khong co symlink hoac junction.
)

echo.
echo ============================================================
if "%ERRORS%"=="0" (
    echo   TRANG THAI: SAN SANG SU DUNG
    echo   He thong da duoc cai dat day du va chinh xac.
    echo   Ban co the khoi chay Voca Basic.exe.
) else (
    echo   TRANG THAI: CHUA HOAN THIEN - Phat hien loi.
    echo   Vui long chay file Cai-Dat-AI-Packages.bat de cai dat lai.
)
echo ============================================================
echo.
pause
if "%ERRORS%"=="0" (exit /b 0) else (exit /b 1)
'@
Write-CustomerBatFile (Join-Path $vocaBasicDir 'Kiem-Tra-Cai-Dat.bat') $kiemTraBat

# 7. Update HUONG-DAN.txt
$huongDan = @'
================================================================================
                    HƯỚNG DẪN CÀI ĐẶT & SỬ DỤNG VOCA BASIC 1.0.1
================================================================================

1. YÊU CẦU HỆ THỐNG & NGUYÊN TẮC HOẠT ĐỘNG
--------------------------------------------------------------------------------
- Hệ điều hành: Windows 10 hoặc Windows 11 (64-bit).
- Dung lượng ổ đĩa trống: Tối thiểu 20 GB khả dụng trên ổ đĩa cài đặt.
- Phân bổ xử lý giọng đọc AI (Offline 100% trên máy):
  + Tiếng Việt (giọng đọc VieNeu): Chạy cục bộ trực tiếp trên CPU.
  + Các ngôn ngữ quốc tế hỗ trợ khác: Sử dụng bộ máy Chatterbox Multilingual V3.
  + Yêu cầu phần cứng Chatterbox: Bắt buộc trang bị card đồ họa rời NVIDIA hỗ trợ
    CUDA (khuyến nghị VRAM >= 4GB).
  + Lưu ý quan trọng: Chatterbox KHÔNG hỗ trợ chạy trên CPU và hệ thống KHÔNG tự
    động fallback âm thầm sang engine khác. Nếu máy không có NVIDIA CUDA, các tác
    vụ tạo giọng ngoại ngữ sẽ báo lỗi phần cứng để người dùng nhận biết rõ ràng.
- Kết nối Internet: Cần thiết khi sử dụng tính năng Dịch thuật Gemini BYOK.
  (Các mô hình TTS đọc văn bản chạy 100% OFFLINE trên máy).

2. CẤU TRÚC GÓI SẢN PHẨM
--------------------------------------------------------------------------------
Thư mục bàn giao gồm có:
  ├── Voca Basic/
  │   ├── Voca Basic.exe            (Phần mềm chính)
  │   ├── 7z.exe + 7z.dll          (Công cụ giải nén tự động đi kèm)
  │   ├── Cai-Dat-AI-Packages.bat   (Script tự động giải nén & cấu hình AI)
  │   ├── Kiem-Tra-Cai-Dat.bat      (Script kiểm tra trạng thái cài đặt)
  │   ├── Reset-Data-Ban-Trang.bat  (Script khôi phục dữ liệu trắng an toàn)
  │   ├── Tao-Phim-Tat-Desktop.bat  (Script tạo phím tắt màn hình chính)
  │   ├── HUONG-DAN.txt             (Tài liệu hướng dẫn này)
  │   └── resources/
  │       ├── bin/ffmpeg.exe        (Công cụ xử lý và xuất âm thanh MP3 tích hợp)
  │       ├── backend/              (Mã nguồn backend)
  │       └── frontend/             (Giao diện người dùng)
  ├── AI-Packages/
  │   ├── runtime-main.7z           (Gói môi trường Python & VieNeu TTS)
  │   ├── runtime-chatterbox.7z     (Gói PyTorch CUDA 12.4 & Chatterbox TTS)
  │   └── models.7z                 (Gói trọng số AI Models)
  └── SHA256SUMS.txt                (Bảng mã băm kiểm tra tính toàn vẹn)

3. CÁC BƯỚC CÀI ĐẶT
--------------------------------------------------------------------------------
Bước 1: Đặt thư mục "Voca-Basic-1.0.1-Customer" vào bất kỳ ổ đĩa nào có đủ >= 20GB trống.
        (Ví dụ: C:\, D:\, E:\, F:\... Không đặt trong thư mục có dấu tiếng Việt
        hoặc ký tự đặc biệt lạ).

Bước 2: Mở thư mục "Voca Basic", nhấp đúp chạy file:
        --> Cai-Dat-AI-Packages.bat

        * Script sẽ tự động:
          - Kiểm tra dung lượng ổ đĩa.
          - Kiểm tra mã SHA256 của các file nén trong AI-Packages.
          - Giải nén chính xác vào thư mục "ai-packages".
          - Kiểm tra xác nhận toàn bộ các thành phần AI đã sẵn sàng.
        * Quá trình giải nén thường mất từ 3 đến 7 phút.
        * Khi màn hình hiện thông báo: "CAI DAT AI PACKAGES: THANH CONG" là hoàn tất.

Bước 3: (Tùy chọn) Chạy file "Kiem-Tra-Cai-Dat.bat" để kiểm tra nhanh tình trạng cài đặt.

Bước 4: Nhấp đúp vào "Voca Basic.exe" để mở và sử dụng phần mềm.

4. CẤU HÌNH DỊCH THUẬT (GEMINI API KEY - BYOK)
--------------------------------------------------------------------------------
- Voca Basic sử dụng mô hình Google Gemini (phiên bản gemini-3.6-flash) chính hãng.
- Để sử dụng tính năng dịch thuật:
  1. Mở phần mềm Voca Basic.
  2. Vào phần Cài đặt (Settings) trên giao diện.
  3. Nhập mã Gemini API Key của bạn (lấy miễn phí tại https://aistudio.google.com).
  4. Nhấn Lưu (Save).
  5. Phần mềm sẽ tự động kết nối và dịch thuật văn bản chính xác, bảo mật.

5. XỬ LÝ SỰ CỐ THƯỜNG GẶP (TROUBLESHOOTING)
--------------------------------------------------------------------------------
- Lỗi "Không đủ dung lượng ổ đĩa":
  -> Đảm bảo ổ đĩa chứa thư mục còn trống tối thiểu 20 GB trước khi chạy cài đặt.
- Lỗi "Không tìm thấy file nén":
  -> Đảm bảo thư mục "AI-Packages" và "Voca Basic" nằm cạnh nhau như cấu trúc ban đầu.
- Lỗi phần mềm diệt virus chặn:
  -> Thêm thư mục "Voca Basic" vào danh sách ngoại lệ (Exclusion) của Windows Defender
     hoặc phần mềm diệt virus của bạn.
- Đóng ứng dụng:
  -> Chỉ cần đóng cửa sổ Voca Basic, phần mềm sẽ tự động tắt toàn bộ tiến trình
     chạy ngầm một cách an toàn và giải phóng tài nguyên máy.

================================================================================
                          VOCA BASIC - PHIÊN BẢN 1.0.1
================================================================================
'@
Write-CustomerTextFile (Join-Path $vocaBasicDir 'HUONG-DAN.txt') $huongDan
Write-CustomerTextFile (Join-Path $customerRoot 'HUONG-DAN.txt') $huongDan

# 8. Compute Authoritative SHA256SUMS.txt
Write-Host "`n=== Generating Authoritative SHA256SUMS.txt ===" -ForegroundColor Cyan
$checksumFiles = @(
    "Voca Basic\Voca Basic.exe",
    "Voca Basic\7z.exe",
    "Voca Basic\7z.dll",
    "Voca Basic\resources\bin\ffmpeg.exe",
    "Voca Basic\Cai-Dat-AI-Packages.bat",
    "Voca Basic\Kiem-Tra-Cai-Dat.bat",
    "Voca Basic\Reset-Data-Ban-Trang.bat",
    "Voca Basic\Tao-Phim-Tat-Desktop.bat",
    "Voca Basic\HUONG-DAN.txt",
    "AI-Packages\runtime-main.7z",
    "AI-Packages\runtime-chatterbox.7z",
    "AI-Packages\models.7z"
)

$shaLines = @(
    "# VOCA BASIC 1.0.1 - SHA256 CHECKSUMS & SIZES",
    "# Generated from final Customer Release Package",
    "# Format: SHA256  FileSize(Bytes)  RelativePath",
    "#=============================================================================="
)

foreach ($rel in $checksumFiles) {
    $full = Join-Path $customerRoot $rel
    if (-not (Test-Path -LiteralPath $full)) {
        throw "Missing required checksum target file: $full"
    }
    $item = Get-Item -LiteralPath $full
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $full).Hash.ToLowerInvariant()
    $relForward = $rel -replace '\\', '/'
    $line = "$hash  $($item.Length)  $relForward"
    $shaLines += $line
    Write-Host "  $line"
}

$shaPath = Join-Path $customerRoot "SHA256SUMS.txt"
Set-Content -LiteralPath $shaPath -Value $shaLines -Encoding utf8
Write-Host "Authoritative checksums written to: $shaPath" -ForegroundColor Green

Write-Host "`n=== Customer Package Assembly COMPLETE ===" -ForegroundColor Green
