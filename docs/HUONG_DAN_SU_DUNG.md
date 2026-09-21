# Hướng dẫn sử dụng Voca Basic

## 1. Tổng quan

Voca Basic là ứng dụng tạo giọng nói bằng AI chạy cục bộ. Giao diện khách hàng hiện có các mục:

- **Trang chủ**: điểm bắt đầu và liên kết nhanh.
- **Tạo giọng nói**: chuyển văn bản thành âm thanh.
- **Nhân bản giọng nói**: tạo hồ sơ giọng từ âm thanh tham chiếu.
- **Thư viện giọng nói**: xem, tìm kiếm, dùng thử và xóa hồ sơ giọng.
- **Lịch sử**: xem lại các tác vụ TTS và phát âm thanh đã hoàn thành.
- **Cài đặt**: lưu các tùy chọn ứng dụng.

Ứng dụng dùng backend cục bộ, token phiên cục bộ và dữ liệu lưu trên máy. Không cần đưa văn bản hoặc file tham chiếu lên dịch vụ web để thực hiện các luồng này.

## 2. Kích hoạt trước khi tạo nội dung

Nếu ứng dụng hiển thị trạng thái chưa kích hoạt, mở hộp thoại bản quyền, sao chép Machine ID và nhập khóa do đơn vị cấp phép cung cấp. Các nút tạo TTS, tạo hồ sơ giọng và thử giọng sẽ yêu cầu giấy phép hợp lệ.

## 3. Tạo giọng nói từ văn bản

1. Mở **Tạo giọng nói**.
2. Nhập hoặc dán nội dung vào vùng văn bản.
3. Chọn ngôn ngữ/giọng phù hợp trong các điều khiển hiển thị.
4. Điều chỉnh các tùy chọn được trang cung cấp, như tốc độ hoặc định dạng đầu ra, nếu cần.
5. Chọn **Tạo** để gửi tác vụ.
6. Chờ trạng thái hoàn thành, sau đó phát thử hoặc tải/lưu âm thanh theo nút trong giao diện.

Lần tạo đầu tiên sau khi mở ứng dụng có thể lâu hơn do mô hình đang được nạp. Không đóng ứng dụng trong khi tác vụ đang chạy. Nếu tác vụ lỗi, ghi lại mã lỗi hiển thị rồi kiểm tra phần xử lý sự cố.

## 4. Nhân bản giọng nói

### Chuẩn bị âm thanh tham chiếu

Chọn bản ghi có một người nói, lời nói rõ, ít tiếng ồn, không nhạc nền và không có nhiều người nói chồng lên nhau. File quá lớn hoặc định dạng/âm thanh không hợp lệ sẽ bị từ chối. Chỉ dùng giọng nói mà bạn có quyền sử dụng và đã nhận được sự đồng ý cần thiết.

### Tạo hồ sơ

1. Mở **Nhân bản giọng nói**.
2. Chọn file âm thanh tham chiếu.
3. Nhập tên dễ nhận biết cho hồ sơ.
4. Chọn ngôn ngữ phù hợp và nhập transcript tham chiếu nếu biểu mẫu yêu cầu hoặc có hỗ trợ.
5. Nhấn nút tạo hồ sơ/nhân bản.
6. Chờ thông báo hoàn thành; hồ sơ mới sẽ xuất hiện trong **Thư viện giọng nói**.

### Thử giọng nhân bản

Trong trang nhân bản hoặc từ luồng mà ứng dụng cung cấp, chọn hồ sơ vừa tạo, nhập một đoạn văn ngắn rồi dùng chức năng thử giọng. Đây là cách nên dùng để kiểm tra chất lượng trước khi tạo nội dung dài.

## 5. Quản lý thư viện giọng nói

Mở **Thư viện giọng nói** để:

- Tìm theo tên giọng hoặc provider.
- Xem chi tiết như tên, profile ID, trạng thái và thông tin file tham chiếu.
- Chọn **Dùng để thử giọng** để quay về luồng thử giọng.
- Xóa hồ sơ khi không còn dùng.

Xóa hồ sơ là thao tác không hoàn tác. Hệ thống có thể từ chối xóa hồ sơ đang được một tác vụ sử dụng; hãy chờ tác vụ kết thúc hoặc hủy tác vụ trước.

## 6. Xem lịch sử và nghe lại âm thanh

Mở **Lịch sử** để xem các tác vụ TTS đã lưu. Có thể:

- Làm mới danh sách.
- Tìm theo Job ID.
- Xem trạng thái `COMPLETED`, `RUNNING`, `FAILED` hoặc trạng thái khác được trả về.
- Chọn **Phát lại** với tác vụ đã hoàn thành có file âm thanh.

Lịch sử được lưu trong cơ sở dữ liệu cục bộ, nên vẫn còn sau khi đóng/mở ứng dụng. Nếu file âm thanh đã bị xóa khỏi thư mục dữ liệu, bản ghi lịch sử có thể còn nhưng không phát lại được.

## 7. Cài đặt và dữ liệu

Trong **Cài đặt**, thay đổi các lựa chọn mà giao diện cho phép và lưu lại. Cài đặt được lưu cục bộ trong SQLite, không cần chỉnh sửa trực tiếp tệp hệ thống.

Để sao lưu, mở menu **Dữ liệu** của ứng dụng và chọn **Sao lưu dữ liệu...**. Để xóa sạch dữ liệu cục bộ, dùng **Xóa toàn bộ dữ liệu cục bộ...**; thao tác này xóa audio, hồ sơ giọng, lịch sử, cài đặt và dữ liệu bản quyền đã lưu.

## 8. Khi có lỗi

1. Đọc thông báo và mã lỗi trên màn hình.
2. Nếu có thể, thử lại sau khi chờ vài phút để mô hình hoàn tất nạp.
3. Kiểm tra giấy phép còn hiệu lực khi lỗi xảy ra lúc tạo TTS hoặc nhân bản.
4. Đảm bảo máy có GPU NVIDIA/CUDA hoạt động và ba thư mục AI đã được cài đúng vị trí.
5. Nếu cần hỗ trợ, cung cấp ảnh chụp lỗi, thời điểm xảy ra, thao tác vừa thực hiện và thông tin phiên bản hiển thị ở thanh bên. Không gửi khóa bản quyền hoặc token phiên cho người không được ủy quyền.

## 9. Lưu ý sử dụng có trách nhiệm

- Chỉ sử dụng văn bản, giọng nói và hồ sơ giọng mà bạn có quyền sử dụng.
- Không dùng tính năng nhân bản để giả mạo, lừa đảo hoặc tạo nội dung gây nhầm lẫn về danh tính.
- Sao lưu dữ liệu trước khi xóa hồ sơ hoặc reset dữ liệu.
- Không tự thay đổi thư mục runtime/model trong khi ứng dụng đang chạy.
