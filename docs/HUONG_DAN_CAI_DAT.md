# Hướng dẫn cài đặt Voca Basic

## 1. Thành phần bộ phát hành

Voca Basic là ứng dụng Windows chạy cục bộ. Bộ phát hành gồm phần **Core** và ba gói AI độc lập:

- Thư mục `Voca Basic Core` chứa `Voca Basic.exe` và tệp `ai-package-config.json`.
- `runtime-main.7z` chứa Python/runtime chính.
- `runtime-chatterbox.7z` chứa Python/runtime dành riêng cho Chatterbox Voice Cloning.
- `models.7z` chứa mô hình và bộ nhớ đệm Hugging Face.

Ba gói AI phải được giải nén cùng thành một thư mục `ai-packages` nằm cạnh `Voca Basic.exe`. Không đổi tên các thư mục `runtime-main`, `runtime-chatterbox` hoặc `models` sau khi giải nén.

## 2. Yêu cầu máy

- Windows 10 hoặc Windows 11 64-bit.
- Ổ đĩa có đủ dung lượng cho Core, ba gói AI sau giải nén và dữ liệu âm thanh sinh ra.
- GPU NVIDIA và CUDA tương thích là yêu cầu vận hành của cấu hình AI hiện tại. Ứng dụng không tự chuyển sang chế độ CPU khi GPU/CUDA không sẵn sàng.
- Khuyến nghị dùng ổ đĩa cục bộ có quyền ghi cho thư mục cài đặt và `%LOCALAPPDATA%`.

Không cần cài Python, Node.js, CUDA Toolkit hoặc trình duyệt riêng để sử dụng bản đã đóng gói. Không xóa driver NVIDIA đang hoạt động trên máy.

## 3. Cài đặt Core và gói AI

1. Giải nén Core vào một thư mục cố định, ví dụ `C:\Voca Basic\Voca Basic Core`.
2. Trong chính thư mục có `Voca Basic.exe`, tạo thư mục `ai-packages`.
3. Giải nén từng gói để nhận đúng cây thư mục sau:

```text
Voca Basic Core\
├─ Voca Basic.exe
├─ ai-package-config.json
├─ ai-packages\
│  ├─ runtime-main\
│  │  └─ python.exe
│  ├─ runtime-chatterbox\
│  │  └─ python.exe
│  └─ models\
│     └─ huggingface\
│        └─ hub\
└─ resources\
```

4. Không đặt các gói AI lồng thêm một cấp thư mục, ví dụ tránh `ai-packages\runtime-main.7z\runtime-main`.
5. Nếu Core có `Tao-Phim-Tat-Desktop.bat`, có thể chạy tệp này để tạo lối tắt Desktop. Đây là bước tùy chọn.
6. Khởi động bằng `Voca Basic.exe`.

Mặc định `ai-package-config.json` dùng đường dẫn tương đối `./ai-packages`. Nếu cần đặt gói AI ở vị trí khác, chỉ thay giá trị `ai_packages_dir` trong tệp cấu hình bằng đường dẫn tuyệt đối của thư mục chứa ba thư mục con ở trên. Không trỏ đến các tệp `.7z` chưa giải nén.

## 4. Lần khởi động đầu tiên

Khi mở ứng dụng, Electron khởi chạy backend cục bộ ở `127.0.0.1:8000`; giao diện hoạt động cục bộ ở `127.0.0.1:5173` khi cần máy chủ tĩnh. Backend chỉ lắng nghe loopback, không công khai dịch vụ ra mạng LAN/Internet.

Lúc khởi động, ứng dụng kiểm tra runtime chính, runtime Chatterbox và kho mô hình. Runtime Chatterbox được truyền riêng cho backend; vì vậy cả `runtime-main\python.exe` và `runtime-chatterbox\python.exe` đều phải tồn tại.

Mô hình có thể được nạp nền ở lần mở đầu tiên. Chờ giao diện xuất hiện hoàn toàn trước khi gửi yêu cầu tạo âm thanh đầu tiên.

## 5. Kích hoạt bản quyền

Các thao tác tạo TTS, tạo hồ sơ giọng và thử giọng nhân bản yêu cầu giấy phép hợp lệ.

1. Mở Voca Basic và mở hộp thoại bản quyền từ chỉ báo trạng thái trong giao diện.
2. Sao chép **Machine ID** hiển thị trên máy.
3. Gửi Machine ID cho đơn vị cấp phép để nhận khóa bản quyền.
4. Dán khóa vào ô kích hoạt và xác nhận.

Khóa được kiểm tra cục bộ bằng chữ ký Ed25519 và gắn với Machine ID. Khi đổi máy hoặc cần thu hồi, dùng chức năng hủy kích hoạt nếu được cung cấp, sau đó liên hệ đơn vị cấp phép.

## 6. Dữ liệu người dùng, sao lưu và gỡ cài đặt

Dữ liệu thay đổi được lưu ngoài thư mục cài đặt, mặc định tại:

```text
%LOCALAPPDATA%\Voca Basic\
├─ audio\                 # âm thanh đã tạo
├─ data\metadata.sqlite3  # hồ sơ, tác vụ và cài đặt
├─ voice-profiles\        # âm thanh tham chiếu của hồ sơ giọng
├─ runtime\session.token  # token phiên cục bộ
└─ temp\                  # dữ liệu tạm
```

Trong menu **Dữ liệu**, chọn **Sao lưu dữ liệu...** để chép toàn bộ dữ liệu này sang thư mục khác. Chỉ chọn **Xóa toàn bộ dữ liệu cục bộ...** khi muốn xóa âm thanh, hồ sơ giọng, lịch sử, cài đặt và bản quyền đã lưu; thao tác này không hoàn tác được. Việc xóa Core không tự xóa dữ liệu `%LOCALAPPDATA%\Voca Basic`.

## 7. Khắc phục sự cố cài đặt

| Triệu chứng | Kiểm tra và cách xử lý |
| --- | --- |
| Báo thiếu `runtime-main/python.exe` | Kiểm tra `ai-packages\runtime-main\python.exe`; giải nén lại `runtime-main.7z` đúng cấp thư mục. |
| Báo thiếu `runtime-chatterbox/python.exe` hoặc Chatterbox runtime unavailable | Kiểm tra `ai-packages\runtime-chatterbox\python.exe`; giải nén lại `runtime-chatterbox.7z`, không dùng runtime Python khác thay thế. |
| Báo thiếu model store/hub | Kiểm tra `ai-packages\models\huggingface\hub`; giải nén lại `models.7z`. |
| Ứng dụng không khởi động hoặc AI không sẵn sàng | Kiểm tra driver NVIDIA, trạng thái CUDA/GPU, dung lượng ổ đĩa và vị trí của ba thư mục AI. Cấu hình hiện tại không có CPU fallback. |
| Không kích hoạt được | Kiểm tra Machine ID/khóa được dán đầy đủ; liên hệ đơn vị cấp phép nếu khóa sai máy hoặc đã hết hạn. |
| Muốn chuyển sang máy khác | Sao lưu dữ liệu trước, cài Core và ba gói AI trên máy mới, sau đó kích hoạt theo Machine ID của máy mới. |

## 8. Ghi chú cho người vận hành kỹ thuật

Không sao chép hoặc thay thế riêng lẻ file từ runtime bằng môi trường phát triển. Không chạy ứng dụng từ junction/symlink trỏ đến thư mục staging. Khi nâng cấp Core, giữ nguyên thư mục `ai-packages` nếu ba gói AI không thay đổi; thay Core cùng cấp với thư mục đó và kiểm tra lại `ai-package-config.json`.
