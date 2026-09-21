# Hướng Dẫn Cài Đặt và Sử Dụng Bộ Quản Trị Bản Quyền (Voca Basic Keygen)

Công cụ này dành riêng cho **Người Bán (Admin)** để tạo, cấp phát, gia hạn, khóa và quản lý License Keys trực tiếp trên **Firebase Cloud Firestore** (project `vocaltts`).

---

## 1. Chuẩn bị quyền kết nối (Service Account) — Chỉ cần làm 1 lần

1. Truy cập vào Firebase Console: **https://console.firebase.google.com**
2. Chọn project **`vocaltts`**
3. Bấm vào biểu tượng **Bánh răng (Project Settings)** ở góc trên bên trái -> chọn **Project settings**
4. Chuyển sang tab **Service accounts**
5. Bấm nút **"Generate new private key"** (Tạo khóa riêng mới) -> chọn **Generate key**
6. Một file `.json` sẽ được tải về máy tính của bạn
7. Đổi tên file vừa tải về thành:
   ```text
   serviceAccountKey.json
   ```
8. Di chuyển file `serviceAccountKey.json` này vào thư mục:
   ```text
   D:\Tool Dich Cho Khach\server_keygen\
   ```

> [!WARNING]
> **TUYỆT ĐỐI KHÔNG** chia sẻ file `serviceAccountKey.json` cho khách hàng hoặc đưa lên các kho lưu trữ công khai (Git). File này chứa quyền quản trị tối cao cơ sở dữ liệu của bạn!

---

## 2. Cách sử dụng

### Cách 1: Dùng Menu giao diện dòng lệnh tiếng Việt (Dễ nhất)
Nhấp đúp chuột vào file:
👉 **`Quan-Ly-Ban-Quyen.bat`** (hoặc file `Tao-Key-Firebase-Cloud.bat` ở thư mục gốc)

Menu tương tác sẽ xuất hiện:
```text
======================================================
     VOCA BASIC - QUAN LY BAN QUYEN FIREBASE CLOUD
======================================================
 [1] Tao License Key moi (Lifetime / Theo ngay)
 [2] Xem danh sach tat ca License tren Cloud
 [3] Xem chi tiet 1 License (thiet bi dang dung)
 [4] Khoa License (Block / Thu hoi)
 [5] Mo khoa License (Unblock)
 [6] Gia han License (Cong them so ngay)
 [7] Reset thiet bi (Cho phep khach doi sang may khac)
 [0] Thoat
======================================================
```
- Khi tạo xong, Key sẽ được tự động copy vào bộ nhớ tạm (Clipboard), bạn chỉ cần ấn `Ctrl + V` là gửi được cho khách!

---

### Cách 2: Dùng câu lệnh CLI (Dành cho kỹ thuật viên)

```bash
cd server_keygen

# 1. Tạo 1 key Vĩnh viễn (Lifetime):
python keygen.py generate --plan lifetime --customer "Nguyen Van A"

# 2. Tạo 1 key 30 ngày (Monthly):
python keygen.py generate --plan time_limited --days 30 --customer "Tran Van B"

# 3. Tạo 5 key dùng thử 7 ngày hàng loạt:
python keygen.py generate --plan time_limited --days 7 --count 5 --note "Batch trial thang 9"

# 4. Xem danh sách tất cả các key trên Firestore:
python keygen.py list

# 5. Xem chi tiết thông tin và thiết bị đang kích hoạt của 1 key:
python keygen.py info --key VB-XXXX-XXXX-XXXX-XXXX-XXXX

# 6. Khóa key khi phát hiện gian lận hoặc chargeback:
python keygen.py block --key VB-XXXX-XXXX-XXXX-XXXX-XXXX --reason "Gian lan"

# 7. Mở khóa lại key:
python keygen.py unblock --key VB-XXXX-XXXX-XXXX-XXXX-XXXX

# 8. Gia hạn thêm 30 ngày:
python keygen.py extend --key VB-XXXX-XXXX-XXXX-XXXX-XXXX --days 30

# 9. Reset thiết bị (gỡ máy cũ để khách kích hoạt trên máy mới):
python keygen.py reset-device --key VB-XXXX-XXXX-XXXX-XXXX-XXXX
```

---

## 3. Cấu trúc dữ liệu lưu trên Firestore

- Collection: **`licenses`**
- Document ID: **`SHA-256(normalized_key)`** (Bảo mật: không lộ key thật nếu vô tình nhìn thấy database)
- Thuộc tính document:
  - `status`: `"active"` | `"blocked"` | `"expired"`
  - `plan`: `"lifetime"` | `"time_limited"`
  - `maxDevices`: Số lượng máy tối đa được kích hoạt (mặc định 1)
  - `activationCount`: Số máy hiện tại đang kích hoạt
  - `customerId`: Tên hoặc ghi chú khách hàng
  - `createdAt`: Thời gian tạo
  - `expiresAt`: Ngày hết hạn (hoặc `null` nếu là Lifetime)
