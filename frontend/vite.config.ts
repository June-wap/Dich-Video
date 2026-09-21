import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
  build: {
    // 17/09 - EPERM khi build lại: mặc định Vite tự xoá sạch `dist/` trước
    // khi build (`emptyOutDir: true`), kể cả những file KHÔNG đổi. Trên
    // Windows, nếu cửa sổ app (scripts/run_app.py, pywebview/WebView2) vừa
    // đóng, các tiến trình con msedgewebview2.exe có thể còn giữ khoá đúng
    // các file .js/.css cũ trong `dist\assets` một lúc (xem
    // scripts/run_app.py's _kill_lingering_webview_processes - đã thêm dọn
    // dẹp chủ động, nhưng không phải lúc nào cũng kịp/đủ) -> lệnh xoá đó báo
    // lỗi EPERM và cả build thất bại, dù không file nào thực sự cần bị xoá.
    //
    // Tắt tự xoá: Vite chỉ ghi các file MỚI (tên file assets có mã hash nội
    // dung riêng mỗi build, vd `index-ab12cd.js`) mà không đụng tới file cũ
    // đang bị khoá -> build không còn phụ thuộc vào việc dọn tiến trình có
    // kịp hay không. Đánh đổi: `dist/` sẽ tích luỹ dần các file assets cũ
    // của những lần build trước (không được tự xoá nữa) - vô hại cho app này
    // (dung lượng nhỏ), dọn tay bằng cách xoá cả thư mục `dist` khi cần
    // (đóng app trước khi xoá để không bị khoá file lúc xoá).
    emptyOutDir: false,
  },
})
