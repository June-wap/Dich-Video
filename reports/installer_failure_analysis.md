# Phân tích lỗi installer Voca Basic

**Ngày phân tích:** 18/09/2026  
**Trạng thái:** Installer hiện tại không được phép phát hành hoặc gửi khách hàng.

## 1. Triệu chứng

Sau khi chạy `Voca-Basic-Setup-1.0.0.exe` trên máy cài:

- Setup báo hoàn tất.
- Start Menu/Desktop có shortcut `Voca Basic`.
- Shortcut trỏ đến `C:\Program Files\Voca Basic\Voca Basic.exe`.
- Thư mục `C:\Program Files\Voca Basic\` chỉ có dữ liệu khoảng vài KB (shortcut/uninstaller), không có `Voca Basic.exe`.
- Khi Windows hoặc shortcut cố mở app, xuất hiện lỗi không tìm được `Voca Basic.exe`.

Đây không phải lỗi người dùng tìm sai vị trí cài đặt.

## 2. Bằng chứng kỹ thuật

### 2.1 File thực thi tồn tại ở bản build chưa đóng gói

Trong thư mục build, file sau tồn tại:

```text
release\dist\win-unpacked\Voca Basic.exe
```

Kích thước được kiểm tra: **210,848,768 bytes** (khoảng 201 MB).

Do đó Electron Builder đã tạo được executable trước khi tạo installer.

### 2.2 Setup chứa payload nội bộ

Khi liệt kê nội dung NSIS installer bằng 7-Zip, installer có payload:

```text
$PLUGINSDIR\app-64.7z
```

Payload này là archive mà NSIS phải giải nén vào thư mục cài đặt.

### 2.3 Payload bị hỏng

`app-64.7z` được tách ra từ Setup và kiểm tra bằng 7-Zip. Kết quả:

```text
Open ERROR: Cannot open the file as [7z] archive
Unexpected end of archive
```

Đây là bằng chứng quyết định: archive bị cắt dở hoặc chưa được ghi xong khi được nhúng vào file Setup.

## 3. Nguyên nhân gốc

Quá trình đóng gói đã chạy chồng/chưa hoàn tất trong khi archive lớn `app-64.7z` đang được nén. NSIS sau đó đã tạo `Setup.exe` với một bản archive chưa toàn vẹn.

Vì file NSIS vẫn đủ cấu trúc để chạy, nó vẫn có thể tạo thư mục cài đặt, shortcut và uninstaller. Tuy nhiên, khi đến bước giải nén ứng dụng, archive hỏng khiến `Voca Basic.exe`, runtime Python, FFmpeg và model không được cài đặt.

Lỗi không có bằng chứng cho thấy do Windows Defender, antivirus, hoặc thao tác của khách hàng.

## 4. Yếu tố làm chẩn đoán ban đầu khó hơn

- Bản installer đầu tiên có lỗi shortcut trỏ đến profile build nội bộ `CodexSandboxOffline`.
- Bản installer sau đã sửa đích shortcut sang `C:\Program Files\Voca Basic`, nhưng payload bên trong lại hỏng.
- Cả hai lần cùng dùng tên `Voca-Basic-Setup-1.0.0.exe`, dễ gây nhầm lẫn giữa bản cũ và bản mới khi sao chép sang máy khác.
- Installer và executable chưa được ký số; đây có thể gây cảnh báo SmartScreen, nhưng không phải nguyên nhân đã được chứng minh cho việc payload archive bị hỏng.

## 5. Tác động

- Installer hiện tại **không thể cài ứng dụng hoàn chỉnh**.
- Không được gửi cho khách hàng hoặc dùng làm bản phát hành.
- Shortcut được tạo ra nhưng không có file đích để khởi chạy.

## 6. Hướng khắc phục bắt buộc

1. Xóa toàn bộ output installer/build lỗi trong `release\dist` sau khi bảo đảm không còn tiến trình `electron-builder`, `7za` hoặc `makensis` đang chạy.
2. Chạy đúng **một** tiến trình đóng gói; không khởi chạy build thứ hai khi build trước chưa kết thúc.
3. Chờ Electron Builder kết thúc với mã trả về thành công trước khi dùng artifact.
4. Kiểm tra bắt buộc trước phát hành:
   - `Voca-Basic-Setup-<version>.exe` tồn tại.
   - Tách `app-64.7z` từ installer và chạy kiểm tra toàn vẹn bằng 7-Zip; không được có `Unexpected end of archive`.
   - Xác minh archive chứa `Voca Basic.exe`.
   - Cài thử trên môi trường sạch hoặc thư mục thử nghiệm, sau đó xác minh `C:\Program Files\Voca Basic\Voca Basic.exe` tồn tại và chạy được.
5. Tăng version/tên artifact cho mỗi bản phát hành, ví dụ `Voca-Basic-Setup-1.0.1.exe`, để tránh gửi nhầm installer cũ.
6. Sau khi chức năng đúng, ký số installer và executable trước khi phân phối rộng rãi.

## 7. Tiêu chí chấp nhận bản sửa

Bản Setup mới chỉ được coi là hợp lệ khi thỏa tất cả điều kiện sau:

- Archive nội bộ vượt qua kiểm tra 7-Zip.
- Cài xong có `Voca Basic.exe` trong thư mục cài.
- Shortcut Start Menu và Desktop mở đúng ứng dụng.
- Ứng dụng khởi động được, backend local đạt trạng thái healthy.
- Bản cài đã được xác minh bằng SHA-256 và có version artifact riêng.

## 8. Kết luận

Lỗi hiện tại là **installer chứa payload ứng dụng bị hỏng**. Cách xử lý đúng không phải tìm lại file `.exe` trên máy khách, mà là tạo lại installer trong một pipeline tuần tự, sau đó kiểm tra toàn vẹn archive và cài thử trước khi gửi đi.
