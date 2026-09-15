# Báo cáo phân tích dự án "Tool Dich Cho Khach"

**Ngày phân tích:** 15/09/2026
**Phạm vi:** Toàn bộ thư mục dự án tại `D:\Tool Dich Cho Khach` (backend FastAPI, frontend React, prototype nghiên cứu, tài liệu, báo cáo checkpoint, quy tắc dự án)

---

## 1. Tổng quan dự án

Đây là một ứng dụng desktop thương mại (theo `Rule/RULES.txt`) làm **Text-to-Speech (TTS) chạy local/offline**, hỗ trợ nhân bản giọng nói (voice cloning), dùng model **OmniVoice** chạy trên GPU NVIDIA (CUDA). Dự án gồm 3 phần chính:

- **`backend/`**: API FastAPI, kiến trúc lớp rõ ràng (api / services / schemas / errors / dependencies), lưu trạng thái bằng SQLite.
- **`frontend/`**: Giao diện React + TypeScript + Vite, đầy đủ các trang (TTS, Long-form, Voice Cloning, Voices, Projects, History, Settings, Diagnostics).
- **`prototype/` + `external/OmniVoice/`**: Lớp lõi xử lý audio, engine TTS nghiên cứu ban đầu, mã nguồn thư viện OmniVoice được vendor vào (có `.git` riêng của thư viện đó).
- **`Rule/`, `reports/`, `docs/`**: Quy trình phát triển kiểu checkpoint (ChatGPT làm kiến trúc sư/reviewer, Codex/AI Agent làm người triển khai), rất nhiều báo cáo bằng chứng (evidence-based) cho từng checkpoint.

Quá trình phát triển được tổ chức cực kỳ bài bản: mỗi checkpoint đều phải đọc rule, ghi log, chạy test, viết báo cáo PASS/PASS_WITH_LIMITATIONS/BLOCKED/FAILED, không được tự nhận đạt nếu chưa có bằng chứng — đây là điểm hiếm gặp ở các dự án cỡ này.

---

## 2. Điểm cộng

**Kiến trúc backend sạch và chuyên nghiệp.** Phân lớp rõ ràng theo api/services/schemas/errors/dependencies, dùng dependency injection chuẩn của FastAPI, `lifespan` quản lý vòng đời provider (load/unload model) một cách tường minh thay vì singleton toàn cục.

**Xử lý lỗi tập trung, nhất quán và thân thiện người dùng.** Toàn bộ lỗi được ánh xạ qua `ErrorCode` + thông báo tiếng Việt rõ ràng cho người dùng cuối, không rò rỉ traceback, đường dẫn file, hay chi tiết nội bộ ra response — kể cả với lỗi validate của Pydantic.

**Tư duy bảo mật khá tốt cho một sản phẩm local-first:** giới hạn CORS chỉ cho origin loopback, validate Host header, chống path traversal khi trả file audio (`is_relative_to`), validate UUID nghiêm ngặt cho `profile_id`/`artifact_id`, giới hạn dung lượng file upload (15MB) và thời lượng audio mẫu (3–60s), kiểm tra checksum SHA-256 cho file tham chiếu giọng nói trước khi dùng lại.

**Kiểm soát đồng thời (concurrency) cẩn thận.** Dùng `Condition` để quản lý trạng thái load/unload provider tránh race condition, `RLock` để serialize suy luận GPU, cơ chế "reservation" cho voice profile để đảm bảo một profile không bị xoá khi đang có long-form job dùng nó.

**Lưu trữ bền vững có thiết kế tốt.** SQLite với migration theo version, WAL mode, ràng buộc khóa ngoại/unique, tự động đánh dấu job dở dang là `FAILED` (`INTERRUPTED`) khi backend khởi động lại — tránh trạng thái "job chạy mãi không xong" sau restart.

**Test coverage backend khá đầy đủ:** 7 file test tương ứng từng service (tts, long-form, persistence, provider, voice-profile, voices API...), có cả "provider fakes" để test logic nghiệp vụ mà không cần GPU thật. Theo báo cáo checkpoint, bộ test đang ở mức 145–242 test pass tuỳ phạm vi.

**Quy trình điều tra lỗi rất khoa học.** Báo cáo `cp03b5_1_content_fidelity_investigation.md` là một ví dụ hiếm gặp về điều tra lỗi chuyên nghiệp: cô lập từng tầng pipeline (chuẩn hóa văn bản → chia chunk → audio thô từ model → xử lý DSP trim/fade → ghép nối) để xác định chính xác "First Failing Stage" bằng số liệu đo được (sample-accounting, RMS, peak amplitude), thay vì đoán mò. Từ đó đưa ra khuyến nghị cấu hình tối ưu (1 câu/chunk, num_step=24) dựa trên ma trận thử nghiệm đối chứng 7 biến thể.

**Rà soát license mô hình/dữ liệu nghiêm túc trước khi thương mại hoá** (`docs/model_license_matrix.md`) — việc rất nhiều dự án AI bỏ qua. Đã phát hiện và loại một số model (XTTS-v2, Piper Hindi/Japanese do dataset CC-BY-NC-SA) khỏi danh mục sản xuất vì lý do license, tránh rủi ro pháp lý khi bán ra thị trường.

---

## 3. Điểm trừ và rủi ro lớn

**Không có kiểm soát phiên bản (Git) cho mã nguồn chính của dự án.** Thư mục gốc không có `.git` (chỉ `external/OmniVoice` — thư viện vendor — có `.git` riêng của nó). Toàn bộ backend, frontend, prototype, hàng chục báo cáo checkpoint đều không được version control. Đây là rủi ro nghiêm trọng: không thể rollback khi có lỗi, không có lịch sử thay đổi thực sự (dù báo cáo checkpoint có mục "Git Diff Summary" nhưng không tồn tại git để tra), không thể code review qua diff, và toàn bộ công sức có thể mất nếu ổ đĩa hỏng hoặc thao tác nhầm.

**Frontend hoàn toàn tách rời khỏi backend — chưa phải sản phẩm hoạt động thật.** Tất cả service ở frontend (`voiceService.ts`, `projectService.ts`, `historyService.ts`) chỉ trả về dữ liệu mẫu cứng (`MOCK_VOICES`, `MOCK_PROJECTS`, `MOCK_HISTORY`) qua `Promise.resolve()`. Trang `TTSPage.tsx` mô phỏng quá trình tạo giọng nói bằng `setInterval` tăng dần progress giả, **không hề gọi API thật** tới backend FastAPI đang chạy ở `127.0.0.1:8000`. Nói cách khác, giao diện đẹp và đầy đủ nhưng chưa kết nối với phần lõi đã được xây khá kỹ ở backend.

**Khoảng cách lớn giữa kỳ vọng UI và khả năng thực tế của backend.** Frontend cho chọn 9 ngôn ngữ và tốc độ đọc 0.5x–2.0x, nhưng backend hiện tại: (a) chỉ tiếng Việt được `VERIFIED` cho production, 8 ngôn ngữ còn lại `NOT_VERIFIED` hoàn toàn; (b) tham số `speed` bị khoá cứng — code validate yêu cầu `float(speed) != 1.0` mới **raise lỗi**, nghĩa là **chỉ speed = 1.0 mới được chấp nhận**, dù schema API và UI đều cho phép chọn giá trị khác. Đây gần như là một "tính năng chết" (dead feature) nếu không được dọn dẹp hoặc ghi chú rõ.

**Yêu cầu cứng GPU NVIDIA CUDA, không có phương án CPU.** `backend/config.py` chủ động raise `ValueError` nếu `omnivoice_device` không đúng định dạng `cuda:N`. Với một sản phẩm định vị bán cho khách hàng đại trà ("Tool Dich Cho Khach"), việc bắt buộc phải có GPU rời NVIDIA sẽ loại bỏ phần lớn máy tính phổ thông (laptop văn phòng, máy Mac, máy chỉ có GPU tích hợp) khỏi tệp khách hàng tiềm năng.

**Chưa có con đường license hợp lệ cho phần lớn phạm vi V1 đã cam kết.** `Rule/RULES.txt` yêu cầu V1 hỗ trợ đầy đủ 9 ngôn ngữ (VI/EN/ZH/JA/ES/PT/IT/FR/HI), nhưng `docs/model_license_matrix.md` cho thấy phần lớn model ứng viên đang ở trạng thái `PENDING` hoặc bị `REJECTED` (XTTS-v2 vì CPML non-commercial, Piper Hindi/Japanese vì dataset CC-BY-NC-SA, espeak-ng data cần thay thế vì GPL). Tức là về mặt pháp lý, sản phẩm chưa có nền tảng an toàn để thương mại hoá đúng như phạm vi đã đề ra.

**Chất lượng giọng đọc long-form còn vấn đề nghiêm trọng, đã tự phát hiện nhưng đánh đổi bằng hiệu năng.** Nhóm tự phát hiện model OmniVoice bị nuốt từ/nuốt câu, phát âm sai thanh điệu, méo tiếng khi chunk văn bản dài ~140–150 ký tự trở lên. Hướng khắc phục (chia 1 câu/chunk, tăng `num_step` từ 16 lên 24) giải quyết được lỗi nội dung nhưng làm **RTF (real-time factor) tăng từ ~13x lên ~35x** — nghĩa là để tạo ra 1 phút audio có thể mất tới ~35 phút xử lý GPU. Với một tool được kỳ vọng dùng cho audiobook/nội dung dài, đây là vấn đề hiệu năng đáng lo ngại chưa có lời giải triệt để.

**Kiến trúc single-process, một khoá suy luận dùng chung cho tất cả.** TTS ngắn, voice cloning và long-form job đều tranh chấp cùng một `inference_lock`. Một long-form job (có thể chạy hàng chục phút tới hàng giờ) sẽ khiến toàn bộ chức năng TTS ngắn/test giọng khác của "khách hàng" bị treo chờ trong lúc đó — model xử lý tuần tự tuyệt đối, không có bất kỳ mức độ song song nào.

**Chưa hỗ trợ resume/khôi phục job.** Dù đã có SQLite lưu trạng thái chunk chi tiết, khi backend restart giữa chừng một long-form job đang chạy, job đó bị đánh dấu `FAILED` vĩnh viễn thay vì được resume từ chunk đã hoàn thành — bản thân báo cáo checkpoint cũng liệt kê đây là hạn chế đã biết, chưa triển khai.

**Tài liệu không được đồng bộ qua các checkpoint.** `backend/README.md` mở đầu bằng câu "No TTS endpoint, inference, profile upload, database or job queue is implemented", nhưng phần cuối cùng tài liệu lại mô tả các API đó đã tồn tại (CP0.3B-5). Tài liệu kiểu "chắp vá qua từng checkpoint" như vậy dễ gây hiểu lầm nghiêm trọng cho người đọc mới hoặc thành viên tham gia sau.

**Danh sách giọng đọc trên UI là dữ liệu tưởng tượng.** Các voice như "Hoài My", "BTV Thời Sự 19h", "Jenny Studio"... hiển thị trên frontend không có ánh xạ thật nào tới backend — backend hiện chỉ có `omnivoice_auto` (voice mặc định) và các profile do người dùng tự tạo qua clone. Nếu ra mắt với đúng giao diện hiện tại, khách hàng sẽ thấy danh sách giọng "có sẵn" nhưng không tồn tại thực.

---

## 4. Bug tiềm ẩn / rủi ro kỹ thuật cụ thể

1. **Tham số `speed` gần như vô dụng nhưng vẫn phơi ra API/schema** (`backend/services/tts_service.py`, `voice_profile_service.py`): validate bắt buộc `float(speed) == 1.0`, mọi giá trị khác đều bị từ chối với lỗi `INVALID_SPEED`. Nếu một client (kể cả frontend tương lai khi được nối dây) gửi `speed=1.25` như UI hiện đang cho phép chọn, request sẽ luôn thất bại.

2. **Ghi DB phụ trong hàm "validate".** `TTSService.validate_request()` gọi `self._db.put('voices', ...)` cho từng voice mỗi lần validate một request TTS ngắn — tác dụng phụ (side-effect) ghi SQLite bị lồng vào một hàm tưởng chừng chỉ đọc/kiểm tra, gây ghi đè không cần thiết vào DB trên mỗi request và trộn lẫn trách nhiệm (validation vs. persistence), dễ gây khó hiểu/khó bảo trì và giảm hiệu năng khi tải cao.

3. **Hằng số audio (24000 Hz, mono) lặp lại rải rác ở nhiều nơi** (`tts_service.py`, `voice_profile_service.py`, `long_form_service.py`) thay vì định nghĩa tập trung một chỗ. Nếu sau này cần đổi sample rate, rất dễ sót một nơi khiến audio bị coi là "invalid" một cách âm thầm.

4. **Nghẽn tài nguyên (resource starvation) do khoá suy luận toàn cục dùng chung** giữa TTS ngắn, clone và long-form — không có ưu tiên, không có time-slicing, không có giới hạn hàng đợi (theo `docs/long_form_api.md`: "no eviction/queue quota"). Về lâu dài có thể dẫn tới tình huống một job dài "khoá chết" trải nghiệm người dùng khác.

5. **Đồng bộ Unicode giữa văn bản gốc và các chunk trong long-form** (`long_form_service._run`): logic ánh xạ vị trí ký tự dựa trên loại bỏ khoảng trắng (`i for i, char in enumerate(request.text) if not char.isspace()`) khá tinh vi; với các chuỗi Unicode tiếng Việt có dấu tổ hợp (combining marks) hoặc văn bản hỗn hợp ngôn ngữ, đây là điểm code phức tạp, khó kiểm chứng đầy đủ chỉ qua test hiện có, và là nơi dễ phát sinh lỗi khó tái hiện khi có input lạ.

6. **Không có xác thực (authentication) ở bất kỳ API nào** — hiện được ghi nhận là chủ đích ("as explicitly requested") vì đây là app desktop chạy loopback. Tuy nhiên nếu sản phẩm sau này mở rộng ra dạng server dùng chung hoặc LAN, đây là lỗ hổng bảo mật cần giải quyết trước, không phải "thêm sau".

7. **`get_audio` (route phát file audio) phụ thuộc vào `get_tts_service`** dù phục vụ audio cho cả TTS ngắn, clone và long-form. Việc gắn logic phục vụ file dùng chung vào một service riêng lẻ tạo sự phụ thuộc chéo không cần thiết giữa các service vốn được thiết kế tách biệt.

8. **Thư mục dự án lẫn rất nhiều file nhị phân nặng** (model `.onnx` ~63MB/model, hàng trăm file `.wav/.mp3` test/output, `__pycache__`, `node_modules`) ngay trong cây thư mục làm việc — không có Git nên `.gitignore` hiện chỉ có tác dụng lý thuyết, không giúp ích khi copy/backup/chia sẻ thư mục.

---

## 5. Đánh giá theo hạng mục

| Hạng mục | Đánh giá | Ghi chú |
|---|---|---|
| Chất lượng kỹ thuật backend | Tốt | Kiến trúc sạch, bảo mật cơ bản ổn, concurrency cẩn thận |
| Test & quy trình QA | Tốt | Test coverage khá, quy trình checkpoint kỷ luật, điều tra lỗi khoa học |
| Frontend | Trung bình | UI đầy đủ, chuyên nghiệp về mặt hình thức, nhưng 100% mock, chưa nối API |
| Mức độ hoàn thiện sản phẩm (so với scope V1) | Yếu | Mới 1/9 ngôn ngữ hoạt động thật; frontend chưa tích hợp; chưa có gói desktop app |
| Tính khả thi thương mại (license, phần cứng) | Yếu | Yêu cầu GPU CUDA bắt buộc; phần lớn license ngôn ngữ khác VI còn PENDING/REJECTED |
| Quản lý mã nguồn / hạ tầng dự án | Yếu | Không có Git; nhiều file nặng lẫn trong thư mục làm việc |
| Hiệu năng (long-form chất lượng cao) | Yếu | RTF ~35x sau khi sửa lỗi nuốt từ — rất chậm so với thời gian thực |

---

## 6. Điểm tổng thể: **6/10**

Đây là một dự án có **nền tảng kỹ thuật và quy trình phát triển thuộc loại tốt hơn mặt bằng chung** — đặc biệt ở phần backend (kiến trúc, bảo mật, xử lý đồng thời, test) và ở kỷ luật quy trình (checkpoint có bằng chứng, điều tra lỗi bằng số liệu, rà soát license chủ động). Nếu chỉ chấm phần backend đơn lẻ, con số hợp lý sẽ ở mức 8/10.

Tuy nhiên khi nhìn dự án như **một sản phẩm tổng thể chuẩn bị đưa cho khách hàng** — đúng như tên gọi và mục tiêu trong `Rule/RULES.txt` — có ba khoảng trống đủ lớn để kéo điểm tổng xuống mức trung bình khá:

1. Frontend và backend chưa hề được nối với nhau (sản phẩm chưa "chạy được" từ góc nhìn người dùng cuối).
2. Phạm vi cam kết (9 ngôn ngữ) mới hoàn thành xác thực 1/9, và phần lớn còn lại vướng license thương mại chưa có lối ra rõ ràng.
3. Thiếu Git/kiểm soát phiên bản là một lỗ hổng quản lý dự án cơ bản, rủi ro cho toàn bộ công sức đã bỏ ra.

**Khuyến nghị ưu tiên tiếp theo:** (1) khởi tạo Git ngay lập tức và commit trạng thái hiện tại; (2) nối frontend với backend thật cho luồng TTS tiếng Việt (vốn đã chạy được) trước khi mở rộng thêm tính năng; (3) quyết định rõ ràng hướng đi license cho 8 ngôn ngữ còn lại (tìm model thay thế được cấp phép thương mại, hoặc thu hẹp scope V1 chỉ còn tiếng Việt + tiếng Anh); (4) đánh giá lại yêu cầu bắt buộc GPU CUDA nếu muốn tiếp cận khách hàng phổ thông.
