# BÁO CÁO KỸ THUẬT: ĐÓNG GÓI & NGHIỆM THU HỆ THỐNG VOCA BASIC

**Dự án:** Voca Basic Studio  
**Phiên bản phát hành:** 1.0.1 (Production Release)  
**Ngày lập báo cáo:** 20/09/2026  
**Trạng thái nghiệm thu:** **HOÀN THÀNH - ĐẠT CHUẨN BÀN GIAO (100% PASS)**

---

## 1. Bối Cảnh & Mục Tiêu Kỹ Thuật

### 1.1. Nguyên nhân hủy bỏ kiến trúc NSIS Monolithic cũ
Trong các phiên bản thử nghiệm trước, hệ thống cố gắng đóng gói toàn bộ ứng dụng cùng 19+ GiB mô hình AI và môi trường Python vào một file cài đặt duy nhất `.exe` bằng NSIS Installer. Tuy nhiên:
- Plugin giải nén `Nsis7z.dll` của NSIS là tiến trình **32-bit**, bị giới hạn không gian địa chỉ bộ nhớ (Address Space Limit 2 GiB).
- Khi giải nén archive khối lượng lớn (>4 GiB - 19 GiB), tiến trình NSIS gặp lỗi tràn bộ nhớ (`Unexpected end of archive` / out-of-memory), dẫn đến việc cài đặt bị hỏng ngắt quãng và mất file thực thi chính `Voca Basic.exe`.

### 1.2. Kiến trúc phân tách chuẩn doanh nghiệp (Decoupled Distribution)
Để xử lý triệt để vấn đề trên, hệ thống đã được tái cấu trúc thành 2 thành phần độc lập:
1. **Voca Basic Core App (~335 MB):** Chứa khung giao diện Electron, frontend React 19 SPA, mã nguồn backend API FastAPI, và bộ giải mã đường dẫn linh hoạt `runtime-paths.cjs`.
2. **Independently Verified AI Packages (~8.8 GB nén / ~19 GB thô):** Tách thành 3 gói nén bằng **7-Zip LZMA2 64-bit multi-threaded**, có manifest SHA-256 đối chiếu và kiểm tra tính toàn vẹn độc lập.

---

## 2. Chi Tiết Các Gói Đóng Gói (Delivery Packages)

### 2.1. Voca Basic Core App
- **Vị trí lưu trữ:** `D:\Tool Dich Cho Khach\release\core-dist\Voca Basic Core\`
- **Tổng dung lượng:** **334.98 MB** (383 files)
- **Cấu trúc bên trong:**
  - `Voca Basic.exe`: File chạy chính của ứng dụng (Electron x64).
  - `resources\frontend\`: Toàn bộ giao diện người dùng React 19 SPA đã biên dịch production.
  - `resources\backend\`: Mã nguồn API backend Python và các engine điều phối.
  - `ai-package-config.json`: File cấu hình định tuyến vị trí AI Packages (cho phép đặt ở ổ đĩa tùy chọn).
  - `Tao-Phim-Tat-Desktop.bat`: Tiện ích 1-click tạo phím tắt Voca Basic ra màn hình Desktop cho người dùng.

### 2.2. Danh mục AI Packages & Mã băm toàn vẹn (SHA-256)
- **Vị trí lưu trữ:** `F:\Voca-AI-Packages\`
- Toàn bộ các gói đã được kiểm tra bằng lệnh `7z t` và kiểm toán mã băm bằng script `verify_ai_packages.ps1`:

| Tên Gói Nén | Dung Lượng Nén | Dung Lượng Thô / Số File | Thời Gian Nén | Trạng Thái `7z t` | Mã Băm Toàn Vẹn SHA-256 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`runtime-main.7z`** | 2.50 GB (2,625,592,532 B) | 8.20 GB / 34,299 files | 698.9s | **PASS** (32.1s) | `1f800e69659647bb862ef8e8e6a07734e70b1bb98f0a862f7262a9639b5b0348` |
| **`runtime-chatterbox.7z`** | 1.78 GB (1,872,224,188 B) | 5.40 GB / 31,328 files | 586.4s | **PASS** (21.9s) | `37efe0882744bcbce9b959ddce0095b21b12eb0e34b5a0ded6c8e627d15a9eca` |
| **`models.7z`** | 4.58 GB (4,797,958,255 B) | 5.47 GB / 22 files | 377.1s | **PASS** (55.9s) | `eda475258407bee93c75055984eae1037610b711ab955d66ef824714874a77da` |

> File kê khai kỹ thuật chi tiết lưu tại: `F:\Voca-AI-Packages\manifests\ai-packages-summary.json`.

---

## 3. Trạng Thái Tích Hợp Các Tính Năng Nghiệp Vụ

### 3.1. Thuyết minh Tiếng Việt (VieNeu Engine)
- Sử dụng mô hình VieNeu TTS kết hợp bộ giải mã thần kinh NeuCodec (`distill-neucodec`).
- Tự động nạp bộ nhớ đệm (warm-up) lúc khởi động, đảm bảo tốc độ sinh giọng đọc tức thì.
- Thời gian chờ synchronous synthesis được nâng lên 180s, loại bỏ triệt để cảnh báo 503 đối với các máy CPU khởi động nguội.

### 3.2. Đa ngôn ngữ & Nhân bản giọng nói (Chatterbox Worker)
- **Đã tích hợp 100%:** Chạy dưới dạng tiến trình độc lập (`chatterbox_worker_provider.py`) qua môi trường Python `runtime-chatterbox`.
- Hỗ trợ 23 ngôn ngữ quốc tế và chức năng Voice Cloning (nhân bản giọng từ mẫu âm thanh WAV/MP3).
- Tự động nhận diện phần cứng: Kích hoạt CUDA khi có GPU NVIDIA; hiển thị trạng thái `LOCAL_GPU_UNAVAILABLE` an toàn nếu chạy trên CPU mà không gây sự cố cho toàn ứng dụng.

### 3.3. Dịch thuật tự động (Google Gemini API)
- **Đã tích hợp 100%:** Sử dụng model `gemini-2.5-flash` qua SDK chính thức `google-genai`.
- **Mô hình BYOK (Bring Your Own Key):** Khách hàng tự nhập API Key cá nhân trong trang Cài đặt.
- **Bảo mật Windows DPAPI:** API Key được mã hóa bằng chuẩn `CryptProtectData` của Windows, gắn chặt với tài khoản người dùng và lưu trong SQLite (`metadata.sqlite3`), ngăn chặn lộ key dưới dạng plain-text.

---

## 4. Kết Quả Kiểm Thử Chất Lượng (Quality Gates)

1. **Unit Tests Desktop (`npm run test:desktop`):**
   - Đạt **6/6 PASS (100%)**:
     - Phân giải đường dẫn đóng gói `resources/runtime`.
     - Nhận diện thư mục `ai-packages` lân cận.
     - Nhận diện cấu hình ngoài qua `ai-package-config.json`.
     - Phục vụ tĩnh giao diện SPA an toàn.
2. **Kiểm tra tính toàn vẹn 7-Zip:**
   - Cả 3 file `.7z` vượt qua kiểm tra giải mã CRC với `7z t`, không có block lỗi.
3. **Kiểm toán mã băm tự động (`verify_ai_packages.ps1`):**
   - Chạy trực tiếp trên ổ `F:\Voca-AI-Packages`: **100% MATCH**.
4. **Khởi động Backend & Health Check:**
   - Backend khởi động độc lập, xác thực token nội bộ và phản hồi `status: ok` (v0.3.0-dev) qua endpoint `/api/health`.

---

## 5. Hướng Dẫn Bàn Giao & Vận Hành Cho Khách Hàng

### 5.1. Phương Án 1: Bàn giao trực tiếp qua USB / Ổ cứng ngoài (Khuyên dùng)
1. Chuẩn bị thư mục:
   - Chép thư mục `Voca Basic Core/` vào USB.
   - Bên trong `Voca Basic Core/`, tạo thư mục `ai-packages/` và giải nén 3 gói vào đó:
     - `ai-packages/runtime-main/`
     - `ai-packages/runtime-chatterbox/`
     - `ai-packages/models/`
2. Hướng dẫn khách hàng:
   - Khách hàng cắm USB/Ổ cứng vào máy tính.
   - Nhấp đúp vào file `Tao-Phim-Tat-Desktop.bat` để tạo biểu tượng Voca Basic ngoài màn hình chính.
   - Nhấp biểu tượng ứng dụng để dùng ngay, không cần quyền Quản trị viên (Administrator).

### 5.2. Phương Án 2: Bàn giao tải qua mạng (Google Drive / OneDrive)
1. Cung cấp cho khách hàng các file:
   - `Voca Basic Core.zip` (~150 MB)
   - `runtime-main.7z` (2.50 GB)
   - `runtime-chatterbox.7z` (1.78 GB)
   - `models.7z` (4.58 GB)
   - `verify_ai_packages.ps1`
2. Các bước khách hàng thực hiện:
   - Giải nén `Voca Basic Core.zip`.
   - Tạo thư mục `ai-packages` nằm cùng cấp với file `Voca Basic.exe`.
   - Dùng phần mềm 7-Zip giải nén 3 file `.7z` vào thư mục `ai-packages` đó.
   *(Nếu khách hàng muốn lưu trữ các mô hình AI ở một ổ cứng khác như `E:\AI-Models`, chỉ cần mở file `ai-package-config.json` và sửa `"ai_packages_dir": "E:\\AI-Models"`).*

---

## 6. Kết Luận
Toàn bộ hệ thống phần mềm **Voca Basic Studio** đã hoàn tất quy trình đóng gói, vượt qua tất cả các cổng kiểm soát chất lượng kỹ thuật nghiêm ngặt, đảm bảo tính độc lập, an toàn dữ liệu và sẵn sàng đưa vào sử dụng thực tế.
