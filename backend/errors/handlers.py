import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from backend.errors import ApplicationError, ErrorCode
from backend.schemas.common import ErrorBody, ErrorResponse

logger = logging.getLogger("backend.errors")
MESSAGES = {
    ErrorCode.PROFILE_IN_USE: "Hồ sơ giọng đọc đang được sử dụng.",
    ErrorCode.JOB_NOT_FOUND: "Không tìm thấy tác vụ.",
    ErrorCode.INTERNAL_ERROR: "Đã xảy ra lỗi trong quá trình xử lý.",
    ErrorCode.INVALID_REQUEST: "Yêu cầu không hợp lệ.",
    ErrorCode.SERVICE_UNAVAILABLE: "Dịch vụ hiện chưa sẵn sàng.",
    ErrorCode.NOT_FOUND: "Không tìm thấy tài nguyên.",
    ErrorCode.METHOD_NOT_ALLOWED: "Phương thức không được hỗ trợ.",
    ErrorCode.PROVIDER_NOT_FOUND: "Không tìm thấy bộ máy tạo giọng được chọn.",
    ErrorCode.PROVIDER_UNAVAILABLE: "Bộ máy tạo giọng hiện không khả dụng.",
    ErrorCode.PROVIDER_LOAD_FAILED: "Không thể nạp bộ máy tạo giọng. Vui lòng kiểm tra runtime và model.",
    ErrorCode.PROVIDER_NOT_READY: "Bộ máy tạo giọng chưa sẵn sàng.",
    ErrorCode.INVALID_TEXT: "Văn bản không hợp lệ.",
    ErrorCode.TEXT_TOO_LONG: "Văn bản vượt quá giới hạn của chế độ TTS ngắn.",
    ErrorCode.LANGUAGE_NOT_SUPPORTED: "Ngôn ngữ không được hỗ trợ.",
    ErrorCode.VOICE_NOT_FOUND: "Không tìm thấy giọng đọc được chọn.",
    ErrorCode.INVALID_SPEED: "Tốc độ đọc không hợp lệ. Vui lòng chọn trong khoảng 0.5 đến 2.0.",
    ErrorCode.INVALID_FORMAT: "Định dạng âm thanh không được hỗ trợ.",
    ErrorCode.GENERATION_FAILED: "Quá trình tạo giọng nói thất bại.",
    ErrorCode.AUDIO_EXPORT_FAILED: "Không thể xuất file âm thanh.",
    ErrorCode.ARTIFACT_NOT_FOUND: "Không tìm thấy file âm thanh.",
    ErrorCode.INVALID_REFERENCE_AUDIO: "Tệp âm thanh mẫu không hợp lệ.",
    ErrorCode.REFERENCE_AUDIO_TOO_LARGE: "Tệp âm thanh mẫu vượt quá dung lượng cho phép.",
    ErrorCode.INVALID_REFERENCE_TRANSCRIPT: "Văn bản phát âm mẫu không hợp lệ.",
    ErrorCode.VOICE_PROFILE_CREATION_FAILED: "Không thể tạo hồ sơ giọng đọc từ âm thanh mẫu.",
    ErrorCode.VOICE_PROFILE_NOT_FOUND: "Không tìm thấy hồ sơ giọng đọc.",
    ErrorCode.VOICE_PROFILE_NOT_READY: "Hồ sơ giọng đọc chưa sẵn sàng.",
    ErrorCode.CLONE_GENERATION_FAILED: "Quá trình tạo giọng nói nhân bản thất bại.",
    ErrorCode.IDEMPOTENCY_KEY_CONFLICT: "Khóa idempotency này đã được dùng với một yêu cầu khác.",
    ErrorCode.TRANSLATION_KEY_REQUIRED: "Cần cấu hình API key Gemini trong Cài đặt để tạo giọng nói cho ngôn ngữ khác tiếng Việt.",
    ErrorCode.TRANSLATION_FAILED: "Không thể dịch văn bản qua Gemini API. Kiểm tra API key, hạn mức sử dụng, hoặc kết nối mạng rồi thử lại.",
    ErrorCode.UNAUTHORIZED: "Không có quyền truy cập API cục bộ.",
    ErrorCode.LOCAL_GPU_UNAVAILABLE: "GPU NVIDIA cục bộ không khả dụng cho Chatterbox.",
    ErrorCode.GPU_RESOURCE_INSUFFICIENT: "GPU không đủ bộ nhớ để tạo giọng nói.",
    ErrorCode.VOICE_PROFILE_PROVIDER_MISMATCH: "Hồ sơ giọng đọc không tương thích với ngôn ngữ đầu ra đã chọn.",
    ErrorCode.LICENSE_REQUIRED: "Phần mềm chưa được kích hoạt bản quyền. Vui lòng nhập mã bản quyền để sử dụng.",
    ErrorCode.LICENSE_EXPIRED: "Bản quyền đã hết hạn sử dụng. Vui lòng liên hệ để gia hạn bản quyền.",
    ErrorCode.LICENSE_INVALID: "Mã bản quyền không hợp lệ hoặc không khớp với thiết bị này.",
    ErrorCode.LICENSE_CLOCK_TAMPERED: "Phát hiện thời gian hệ thống không chính xác. Vui lòng kiểm tra lại ngày giờ máy tính.",
    ErrorCode.LICENSE_BLOCKED: "Mã bản quyền này đã bị khóa do vi phạm chính sách sử dụng.",
    ErrorCode.DEVICE_LIMIT_REACHED: "Mã bản quyền đã đạt số lượng thiết bị tối đa cho phép. Vui lòng gỡ kích hoạt trên máy cũ.",
    ErrorCode.ACTIVATION_REVOKED: "Bản quyền trên thiết bị này đã bị thu hồi từ máy chủ.",
    ErrorCode.MACHINE_MISMATCH: "Mã bản quyền không khớp với thiết bị hiện tại.",
    ErrorCode.TOKEN_INVALID: "Token bản quyền không hợp lệ hoặc đã bị thay đổi.",
    ErrorCode.TOKEN_EXPIRED: "Token bản quyền đã hết hạn sử dụng.",
    ErrorCode.LEASE_EXPIRED: "Đã hết thời hạn sử dụng ngoại tuyến. Vui lòng kết nối Internet để đồng bộ bản quyền.",
}
STATUSES = {
    ErrorCode.PROFILE_IN_USE: 409, ErrorCode.JOB_NOT_FOUND: 404,
    ErrorCode.INTERNAL_ERROR: 500, ErrorCode.INVALID_REQUEST: 422,
    ErrorCode.SERVICE_UNAVAILABLE: 503, ErrorCode.NOT_FOUND: 404,
    ErrorCode.METHOD_NOT_ALLOWED: 405,
    ErrorCode.PROVIDER_NOT_FOUND: 404, ErrorCode.PROVIDER_UNAVAILABLE: 503,
    ErrorCode.PROVIDER_LOAD_FAILED: 503, ErrorCode.PROVIDER_NOT_READY: 503,
    ErrorCode.INVALID_TEXT: 422, ErrorCode.TEXT_TOO_LONG: 422,
    ErrorCode.LANGUAGE_NOT_SUPPORTED: 422, ErrorCode.VOICE_NOT_FOUND: 422,
    ErrorCode.INVALID_SPEED: 422, ErrorCode.INVALID_FORMAT: 422,
    ErrorCode.GENERATION_FAILED: 500, ErrorCode.AUDIO_EXPORT_FAILED: 500,
    ErrorCode.ARTIFACT_NOT_FOUND: 404,
    ErrorCode.INVALID_REFERENCE_AUDIO: 422, ErrorCode.REFERENCE_AUDIO_TOO_LARGE: 422,
    ErrorCode.INVALID_REFERENCE_TRANSCRIPT: 422,
    ErrorCode.VOICE_PROFILE_NOT_FOUND: 404, ErrorCode.VOICE_PROFILE_NOT_READY: 503,
    ErrorCode.VOICE_PROFILE_CREATION_FAILED: 500, ErrorCode.CLONE_GENERATION_FAILED: 500,
    ErrorCode.IDEMPOTENCY_KEY_CONFLICT: 409,
    ErrorCode.TRANSLATION_KEY_REQUIRED: 422, ErrorCode.TRANSLATION_FAILED: 502,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.LOCAL_GPU_UNAVAILABLE: 503, ErrorCode.GPU_RESOURCE_INSUFFICIENT: 503,
    ErrorCode.VOICE_PROFILE_PROVIDER_MISMATCH: 422,
    ErrorCode.LICENSE_REQUIRED: 403, ErrorCode.LICENSE_EXPIRED: 403,
    ErrorCode.LICENSE_INVALID: 403, ErrorCode.LICENSE_CLOCK_TAMPERED: 403,
    ErrorCode.LICENSE_BLOCKED: 403, ErrorCode.DEVICE_LIMIT_REACHED: 403,
    ErrorCode.ACTIVATION_REVOKED: 403, ErrorCode.MACHINE_MISMATCH: 403,
    ErrorCode.TOKEN_INVALID: 403, ErrorCode.TOKEN_EXPIRED: 403,
    ErrorCode.LEASE_EXPIRED: 403,
}


def error_response(code: ErrorCode, status_code: int | None = None) -> JSONResponse:
    payload = ErrorResponse(error=ErrorBody(code=code.value, message=MESSAGES[code]))
    return JSONResponse(payload.model_dump(), status_code=status_code or STATUSES[code])


async def unexpected_error(request: Request, exc: Exception):
    # Do not log request URL, query, headers or body. Server stack stays local.
    logger.error("request_failed code=INTERNAL_ERROR", exc_info=(type(exc), exc, exc.__traceback__))
    return error_response(ErrorCode.INTERNAL_ERROR)


def register_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error(request: Request, exc: ApplicationError):
        logger.warning("request_failed code=%s", exc.code.value)
        return error_response(exc.code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic errors can contain original input or custom exception text.
        logger.warning("request_failed code=INVALID_REQUEST")
        return error_response(ErrorCode.INVALID_REQUEST)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = {404: ErrorCode.NOT_FOUND, 405: ErrorCode.METHOD_NOT_ALLOWED,
                503: ErrorCode.SERVICE_UNAVAILABLE}.get(
                    exc.status_code, ErrorCode.INTERNAL_ERROR if exc.status_code >= 500 else ErrorCode.INVALID_REQUEST)
        logger.warning("request_failed status=%d code=%s", exc.status_code, code.value)
        response = error_response(code, exc.status_code)
        if exc.status_code == 405 and exc.headers and "Allow" in exc.headers:
            response.headers["Allow"] = exc.headers["Allow"]
        return response

    app.add_exception_handler(Exception, unexpected_error)
