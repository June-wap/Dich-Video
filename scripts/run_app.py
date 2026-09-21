"""Cửa sổ desktop THẬT cho Tool Dich Cho Khach (17/09) - bọc backend FastAPI
bằng pywebview thay vì mở tab trình duyệt (scripts/run_backend.ps1's cách cũ,
"1 tiến trình, 1 cổng" - xem Settings.serve_frontend trong backend/config.py).
Trên Windows, pywebview tự dùng WebView2 (engine Chromium có sẵn từ
Windows 10/11 hiện đại - cùng engine Edge) nếu đã cài thêm gói `pythonnet` -
xem ghi chú trong requirements-backend.txt. Không có `pythonnet`/WebView2
Runtime, pywebview rơi về renderer MSHTML cũ (IE) - sẽ không hiển thị đúng
giao diện React hiện đại. scripts/run_backend.ps1 tự kiểm tra `import webview`
trước khi gọi file này - chưa cài thì tự rơi về mở tab trình duyệt như cũ,
không bắt buộc phải có pywebview mới chạy được sản phẩm.

KHÔNG tự chạy file này riêng lẻ - nó không tự set PYTHONPATH hay các biến
môi trường LOCAL_AI_REQUIRE_LOCAL_TOKEN/LOCAL_AI_WARM_UP_ON_START/
LOCAL_AI_SERVE_FRONTEND mà scripts/run_backend.ps1 đã set trước khi gọi tới
đây - tự chạy riêng sẽ ra một backend không có token/warm-up/serve_frontend
bật (giống một lần chạy test), không phải cấu hình cho một lần chạy thật.

Lỗi thực tế đã gặp (17/09) - xem _kill_lingering_webview_processes():
`msedgewebview2.exe` (engine của pywebview trên Windows) sinh ra nhiều tiến
trình con (renderer/GPU/network service, giống Chrome) và KHÔNG phải lúc
nào cũng tự tắt hết ngay khi cửa sổ đóng - chúng có thể còn giữ khoá các
file trong `frontend/dist/assets` một lúc sau, khiến `npm run build` lần kế
tiếp báo lỗi EPERM cho tới khi bị tắt thủ công qua Task Manager. Đã thêm
bước dọn dẹp chủ động ngay dưới đây để không phải làm tay việc đó mỗi lần.
"""
import logging
import os
import threading
import time

import psutil
import uvicorn

from backend.main import app

logger = logging.getLogger("backend.lifecycle")


def _run_server(server: uvicorn.Server) -> None:
    server.run()


def _kill_lingering_webview_processes(parent_pid: int, *, timeout: float = 3.0) -> None:
    """Sau khi webview.start() trả về (cửa sổ đã đóng), chờ tối đa `timeout`
    giây cho các tiến trình con `msedgewebview2.exe` của CHÍNH tiến trình
    Python này tự thoát - nếu vẫn còn sống sau đó, ép tắt (`kill()`, không
    phải chỉ đóng cửa sổ hiển thị). Chỉ duyệt theo cây tiến trình con của
    `parent_pid` (tiến trình Python đang chạy file này) nên không đụng tới
    msedgewebview2.exe của bất kỳ app nào khác đang chạy trên máy (kể cả
    Edge thật của người dùng)."""
    try:
        parent = psutil.Process(parent_pid)
    except psutil.NoSuchProcess:
        return

    def _webview_children() -> list[psutil.Process]:
        try:
            return [
                p for p in parent.children(recursive=True)
                if p.is_running() and p.name().lower() == "msedgewebview2.exe"
            ]
        except psutil.NoSuchProcess:
            return []

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _webview_children():
            return
        time.sleep(0.2)

    survivors = _webview_children()
    if not survivors:
        return
    logger.info("killing_lingering_webview2_processes count=%d", len(survivors))
    for proc in survivors:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def main() -> None:
    import webview  # import trễ - xem docstring, tránh crash sớm nếu thiếu

    settings = app.state.settings
    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(config)

    # uvicorn.Server.run() tự tạo event loop asyncio RIÊNG của nó
    # (asyncio.run bên trong) - chạy an toàn trong 1 thread nền, không đụng
    # tới main thread mà pywebview cần giữ cho vòng lặp GUI của nó.
    server_thread = threading.Thread(target=_run_server, args=(server,), daemon=True)
    server_thread.start()

    window = webview.create_window(
        settings.app_name,
        f"http://{settings.host}:{settings.port}/",
        width=1280,
        height=820,
        min_size=(960, 600),
    )

    def _on_closed() -> None:
        # server.should_exit=True là cách chính thức của uvicorn để tự thoát
        # sạch vòng lặp serve() từ một thread khác - kích hoạt luôn lifespan
        # shutdown thật của backend/main.py (xoá token file, đóng service...),
        # không phải kill process thô bạo.
        logger.info("app_window_closed - đang tắt backend...")
        server.should_exit = True

    window.events.closed += _on_closed

    # webview.start() chặn (block) main thread cho tới khi cửa sổ đóng - đây
    # chính là vòng lặp chính của "app", tương đương uvicorn.run() chặn ở
    # cách chạy cũ (python -m backend.main).
    webview.start()

    # Cửa sổ đã đóng - dọn nốt các tiến trình con msedgewebview2.exe còn sót
    # lại TRƯỚC KHI coi app đã tắt xong, để lần build frontend kế tiếp không
    # còn bị khoá file (xem docstring đầu file + hàm ở trên).
    _kill_lingering_webview_processes(os.getpid())

    server_thread.join(timeout=5)


if __name__ == "__main__":
    main()
