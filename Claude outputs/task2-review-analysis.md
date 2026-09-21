# Task 2 — Review Package (TTS Job + History)

Status: **implementation EXECUTED, NOT verified** (pytest chưa chạy được — xem Blocker). Không tiến sang Task 3. Đính kèm: `task2-review-files.zip` (8 file gốc, nguyên trạng, không diff — vì thư mục làm việc không phải git repo nên không tạo được unified diff sạch).

## 1. Hai điểm được yêu cầu review kỹ

### 1a. `self._db.recover()` gọi trong `TTSService.__init__` — có race/ownership issue không?

**File:** `backend/services/tts_service.py` dòng 75; đối chiếu `backend/services/long_form_service.py` dòng 70; `backend/persistence.py` dòng 244-264.

Sự thật về code hiện tại:

- `TTSService` và `LongFormTTSService` mỗi service tự tạo `Repository` riêng (`self._db = Repository(settings)`), nhưng cả hai trỏ vào **cùng một file SQLite** (`settings.database_path`).
- Cả hai constructor đều gọi `self._db.recover()` — không có filter theo `kind`, câu lệnh là `WHERE status IN ('QUEUED','RUNNING')` trên toàn bộ bảng `tts_jobs`. Nghĩa là recover() vốn đã là **global**, không phải per-kind.
- Thứ tự khởi tạo trong `main.py` lifespan là tuần tự, cùng một thread (`system_service → tts_service → voice_profile_service → long_form_service`), không có gì chạy song song ở bước này.
- `Repository.recover()` mở transaction bằng `BEGIN IMMEDIATE` (khóa ghi ngay lập tức) và `connect()` có `busy_timeout=5000`. Nếu giả định thứ tự tuần tự sai (ví dụ sau này refactor sang khởi tạo song song), hai lệnh `BEGIN IMMEDIATE` từ hai connection khác nhau vẫn được SQLite tuần tự hóa an toàn (connection thứ hai chờ đến khi connection thứ nhất commit, sau đó `SELECT ... WHERE status IN (...)` không còn dòng nào để sửa).

**Kết luận:** Đây **không phải bug chức năng** ở kiến trúc hiện tại (single-process, khởi tạo tuần tự, SQLite serialize qua `BEGIN IMMEDIATE`). Gọi `recover()` hai lần là **idempotent theo hàng** (row-level), lần gọi thứ hai chỉ là no-op.

Tuy nhiên đây đúng là một **code smell về ownership** đáng để sửa trước khi thêm service thứ ba:

- `recover()` là một thao tác global (ảnh hưởng mọi `kind`) nhưng lại được gọi từ *hai constructor độc lập*, mỗi bên chỉ biết một phần bức tranh. Tính đúng đắn phụ thuộc vào một giả định ngầm (thứ tự khởi tạo tuần tự + khóa SQLite) chứ không phải một ranh giới rõ ràng trong code.
- Nếu sau này có service thứ ba (hoặc một trong hai constructor được gọi từ nơi khác, ví dụ trong test hoặc một tool CLI) mà quên/gọi thiếu, hành vi vẫn "tình cờ đúng" chứ không được đảm bảo bởi thiết kế.

**Đề xuất (chưa áp dụng, chờ quyết định):** chuyển `recover()` ra khỏi cả hai constructor, gọi **một lần duy nhất** ở `main.py` lifespan, trước khi bất kỳ service nào được tạo — service không còn tự gọi `recover()` nữa. Rủi ro: các unit test hiện dựng `TTSService(settings, provider)` / `LongFormTTSService(...)` trực tiếp (không qua `create_app`) — ví dụ `test_interrupted_job_marked_failed_on_restart_not_resumed` trong `test_tts_jobs.py` — đang trông cậy vào việc constructor tự phục hồi. Refactor này cần sửa các fixture đó (gọi `Repository(settings).recover()` tường minh trước khi dựng service trong test) — phạm vi rộng hơn một chỗ, nên xin ý kiến trước khi làm, không tự ý sửa.

### 1b. Idempotency scan theo `execution_snapshot` — collision semantics khi cùng key khác payload

**File:** `backend/persistence.py` dòng 275-296 (`find_job_by_idempotency_key`); `backend/services/tts_service.py` dòng 168-171 (`submit()`).

Đã xác nhận đây là **bug thật, chưa có test bao phủ**:

```python
if idempotency_key is not None:
    existing_id = self._db.find_job_by_idempotency_key(JOB_KIND, idempotency_key)
    if existing_id is not None:
        return self._get(existing_id).snapshot
```

`find_job_by_idempotency_key` chỉ so khớp trên `idempotency_key`, **không so payload**. Kịch bản lỗi cụ thể:

1. Client gửi `POST /api/tts/jobs` với `idempotency_key="abc"`, `text="Xin chào"` → tạo job A.
2. Client gửi lại `idempotency_key="abc"` nhưng `text="Tạm biệt"` (payload khác — do bug client, copy-paste nhầm key, hoặc client cố tình) → service **âm thầm trả về snapshot của job A** (nội dung "Xin chào"), không tạo job mới, không báo lỗi.

Đây là vi phạm ngữ nghĩa idempotency-key chuẩn (kiểu Stripe): cùng key + cùng payload → trả kết quả cũ (đúng, đây mới là "retry an toàn"); cùng key + payload khác → phải là lỗi xác định (409 conflict), không được trả nhầm kết quả của request khác.

Kiểm tra bộ test hiện có (`test_tts_jobs.py`): có `test_idempotency_retry_same_key_returns_same_job` (cùng key, cùng payload) và `test_idempotency_different_keys_create_different_jobs` (khác key). **Không có test nào cho "cùng key, khác payload"** — đúng như nghi ngờ, đây là lỗ hổng trong bộ test bắt buộc ban đầu, cần bổ sung.

**Đề xuất fix (chưa áp dụng, chờ quyết định):**

1. Khi lưu `execution_snapshot`, thêm một fingerprint của payload (hash các field ảnh hưởng kết quả: `text, language, voice_id, speed, format` — loại trừ chính `idempotency_key`), ví dụ `hashlib.sha256(json.dumps({...}, sort_keys=True)).hexdigest()`.
2. `find_job_by_idempotency_key` trả về `(job_id, payload_fingerprint)` thay vì chỉ `job_id`.
3. Trong `submit()`: nếu key trùng và fingerprint trùng → trả job cũ (như hiện tại). Nếu key trùng nhưng fingerprint khác → raise lỗi mới, ví dụ `ErrorCode.IDEMPOTENCY_KEY_CONFLICT` (cần thêm vào `backend/errors/__init__.py` + `MESSAGES`/`STATUSES` trong `backend/errors/handlers.py`, gợi ý HTTP 409 — đã có tiền lệ `PROFILE_IN_USE` dùng 409).
4. Test bắt buộc bổ sung: `test_idempotency_same_key_different_payload_is_rejected` (hoặc tên tương đương) assert 409 + không tạo job mới + job cũ không bị sửa.

Không có thay đổi schema DB cần thiết (fingerprint nằm trong `execution_snapshot` JSON, giống `idempotency_key` hiện tại) — giữ nguyên rủi ro thấp so với baseline migration test của Task 1.

## 2. Danh sách file thay đổi (đúng như đã báo cáo, xác nhận lại từ code thực tế)

| File | Loại | Vị trí chính |
|---|---|---|
| `backend/schemas/tts.py` | Modified | `TTSRequest.idempotency_key` (dòng 17), `TTSStatus` (dòng 42-55) |
| `backend/services/tts_service.py` | Rewritten | Toàn bộ — job/queue/worker, `submit/status/history/_run/synthesize` |
| `backend/persistence.py` | Modified | `find_job_by_idempotency_key` (dòng 275-296) — không đổi schema |
| `backend/api/tts_jobs.py` | New | Router `/tts/jobs` — POST/GET list/GET by id |
| `backend/api/router.py` | Modified | Đăng ký `tts_jobs_router` (dòng 6, 17) |
| `backend/main.py` | Modified | `close()` cho `tts_service` khi shutdown (dòng 52-53) |
| `backend/tests/test_backend.py` | Modified | Cập nhật tập route trong `test_openapi_only_checkpoint_routes` (dòng 225-226) |
| `backend/tests/test_tts_jobs.py` | New | 16 test |

## 3. API contract (xác nhận từ `tts_jobs.py`)

- `POST /api/tts/jobs` → `202`, body `TTSStatus` (`response_model_exclude_none=True`)
- `GET /api/tts/jobs/{job_id}` → `200 TTSStatus` hoặc `404 JOB_NOT_FOUND`
- `GET /api/tts/jobs` → `200 list[TTSStatus]`
- `GET /api/audio/{artifact_id}` — không đổi
- `POST /api/tts` — không đổi, vẫn đồng bộ, vẫn `200`/error tương ứng (implement lại bằng `submit()` + poll nội bộ, hành vi quan sát được từ bên ngoài giữ nguyên)

## 4. Blocker (không đổi so với báo cáo trước)

- `device_bash` trên máy Windows của user vẫn lỗi do bug Windows update (8/9) không mount được Plan9 drive share.
- Cloud sandbox không có network access tới pypi.org / files.pythonhosted.org (egress gateway trả 403 `host_not_allowed`).
- → **Chưa chạy được pytest ở đâu cả.** Không có con số pass/fail thực tế nào được báo cáo — đúng yêu cầu "không báo PASS nếu chưa có output test thực tế".

## 5. Bước tiếp theo đề xuất

Chờ bạn + ChatGPT review xong hai điểm trên (và bất kỳ điểm nào khác phát hiện thêm từ file đính kèm). Nếu quyết định:

- **1a** (recover ownership): chấp nhận as-is (an toàn theo phân tích trên, chỉ là code smell) hoặc yêu cầu refactor tập trung — cho biết hướng nào để triển khai.
- **1b** (idempotency collision): gần như chắc chắn nên fix trước khi chạy test, vì đây là gap thật trong yêu cầu "idempotency tối thiểu" — đề nghị xác nhận để mình áp dụng fix ở trên + thêm test tương ứng.

Sau khi thống nhất, mình sẽ áp dụng fix (nếu có), rồi chạy `backend/tests` trên máy Windows của bạn (một khi `device_bash` hoạt động lại) hoặc chờ bạn chạy và gửi output thực tế.
