# Local AI Voice — Function Test Prototype

Prototype được sửa tiếp trên mã và model hiện có. Không tải lại model CP0, không dùng API trả phí. Giao diện chỉ nghe tại `127.0.0.1:7860`.

## Runtime chính thức từ CP0.3B-0

Backend và test suite cần môi trường Python được cấu hình riêng.
(Python 3.12.10). Hướng dẫn cài đặt/audit: [Backend runtime](../docs/backend_runtime.md).
Các môi trường `.cp0` chỉ còn là môi trường nghiên cứu lịch sử.

```powershell
cd "D:\Tool Dich Cho Khach"
. .\scripts\activate_backend.ps1
python scripts\audit_backend_runtime.py
```

`app.py` bên dưới là entrypoint prototype cũ, vẫn đăng ký Sherpa/Japanese/VieNeu.
CP0.3B-0 không tích hợp công cụ TTS này vào entrypoint và không xác minh live inference
của các engine cũ trong runtime chính thức. Mô tả tính năng bên dưới là của prototype
cũ; không phải bằng chứng backend FastAPI đã có.

## Cài môi trường mới (chỉ khi cần)

Không cần tạo/cài lại môi trường trên máy đã audit. Dùng quy trình trong
[backend_runtime.md](../docs/backend_runtime.md) khi chuẩn bị máy mới.
`prototype/requirements.txt` là snapshot legacy; file dependency chính thức là
`requirements-backend.txt` ở thư mục gốc.

Cần FFmpeg trên PATH cho MP3. Thiếu FFmpeg: giữ WAV và báo MP3 FAIL, không chạy lại TTS. Cài dependency/model là bước chuẩn bị riêng cần internet; ứng dụng đặt HF_HUB_OFFLINE=1 và TRANSFORMERS_OFFLINE=1, không tự tải model khi tạo âm thanh.

## Vị trí model

- `.cp0/models/piper/<model>/<model>.onnx` và `<model>.onnx.json`: 9 model hiện có.
- `.cp0/models/sherpa/vits-piper-vi_VN-vais1000-medium/espeak-ng-data/`: từ điển Sherpa.
- `prototype/models/<model>/`: bản ONNX thêm metadata Sherpa, tạo từ model gốc ở lần dùng đầu. Không thay model gốc.
- VieNeu: cache Hugging Face hiện có `%USERPROFILE%/.cache/huggingface/hub/models--pnnbao-ump--VieNeu-TTS-v3-Turbo/`; các artifact phụ thuộc theo cấu hình VieNeu cũng cần có sẵn. Cache thiếu sẽ báo lỗi offline. Danh sách version trong báo cáo.

## Sử dụng

- TTS: chọn ngôn ngữ, giọng, nhập văn bản rồi Generate. Tốc độ áp dụng cho Sherpa/Japanese; VieNeu preset dùng tốc độ tự nhiên.
- Conversation: sửa JSON, mỗi dòng gồm `speaker`, `language`, `voice`, `text`, `pause_ms` (0–10000). Mặc định giọng nữ `vieneu:Trúc Ly`, nam `vieneu:Minh Đức`. Một dòng lỗi sẽ không xuất bản ghép thiếu dòng.
- Voice Cloning: WAV/MP3 mà bạn có quyền sử dụng, tên giọng và văn bản tiếng Việt. VieNeu v3 Turbo không yêu cầu transcript. Adapter giữ conditioning riêng, không ép provider thường phải hỗ trợ cloning.
- Diagnostics: xem phần cứng/model/runtime và chạy mỗi giọng đã đăng ký. PASS nghĩa là sinh được audio; không đồng nghĩa phát âm đạt chất lượng.

## Kiểm thử

```powershell
. .\scripts\activate_backend.ps1
python -m pytest prototype/tests tests -v
```

Bài acceptance chạy inference với socket bị chặn, ghi kết quả tại `reports/prototype_results.json`. Mẫu cloning 5/10/30 giây được cắt/lặp từ audio tổng hợp CP0 có sẵn: chỉ kiểm tra đường xử lý và thời lượng, không chứng minh độ giống giọng người. Chấm phát âm/tự nhiên/giống giọng/ổn định bằng tai vẫn cần người nghe.

## Cây file

```text
prototype/
  app.py
  core/{tts_manager,audio_utils,hardware,text_utils}.py
  providers/{base,sherpa_piper,ort_japanese,voice_clone}.py
  models/       # adapted ONNX cache
  outputs/      # WAV/MP3
  temp/         # synthetic references
  logs/prototype.log
  tests/{test_regressions,run_acceptance}.py
  requirements.txt
  README.md
reports/
  prototype_test_report.md
  prototype_results.json
  prototype_acceptance_console.log
  prototype_unit_tests.log
```

Đây là prototype chức năng. Không có installer, activation, cloud inference hay kiến trúc production. Ghi chú license/CP0 cũ được giữ nguyên trong `docs/` và `reports/`.
