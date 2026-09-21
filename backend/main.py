"""ASGI factory: one primary provider per app lifespan; model loading stays lazy
by default (on-demand, first request pays load time) unless
Settings.warm_up_on_start opts into a background eager-load at startup - see
that field's docstring in backend/config.py. Settings.serve_frontend
additionally opts into serving a built frontend/dist alongside the API from
this same process/port - see that field's docstring too."""
from contextlib import asynccontextmanager
import hmac
import logging
import os
from pathlib import Path
import secrets
import threading
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from backend.api.router import router
from backend.config import Settings
from backend.errors import ErrorCode
from backend.errors.handlers import error_response, register_handlers, unexpected_error
from backend.logging_config import configure_logging
from backend.services.system_service import SystemService
from backend.services.capability_service import HardwareCapabilityService
from backend.services.provider_service import ProviderService, create_provider_service
from backend.services.tts_service import TTSService
from backend.services.voice_profile_service import VoiceProfileService
from backend.services.translation_service import TranslationService
from backend.services.app_settings_service import AppSettingsService
from backend.services.license_service import LicenseService

logger = logging.getLogger("backend.lifecycle")

# Security P1 (checklist-bao-mat-truoc-dong-goi-17-09.md muc 7): reject an
# oversized request BEFORE Starlette/FastAPI ever parses its body (multipart
# or otherwise) - api/voices.py's create_profile previously called
# `await file.read()` unconditionally and only checked
# VoiceProfileService.MAX_REFERENCE_SIZE (15 MiB) afterwards inside
# create_profile(), so an arbitrarily large upload was fully read into memory
# before that check ever ran. This ceiling is generous above the one
# multipart endpoint's own 15 MiB limit (spare room for multipart boundary/
# form-field overhead); every other endpoint only ever sends small JSON, so
# this never affects them.
MAX_REQUEST_BODY_BYTES = 20 * 1024 * 1024


def _write_token_file(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    try:
        # Best-effort only: os.chmod's owner-only bits are a real ACL on
        # Linux/macOS but Windows has no POSIX permission model - chmod there
        # only toggles the read-only attribute, not a per-user ACL. A real
        # Windows ACL restricting this file to the current user needs
        # pywin32 (win32security) - not attempted here; see
        # checklist-bao-mat-truoc-dong-goi-17-09.md item 1 for the residual
        # gap this leaves on Windows specifically.
        os.chmod(path, 0o600)
    except OSError:
        pass


def _remove_token_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def create_app(settings: Settings | None = None,
               service_factory: Callable[[ProviderService], SystemService] = SystemService,
               provider_service_factory: Callable[[Settings], ProviderService] = create_provider_service,
               translation_service_factory: Callable[[Settings], TranslationService] = TranslationService,
               app_settings_service_factory: Callable[[Settings], AppSettingsService] = AppSettingsService,
               voice_profile_service_factory: Callable[[Settings, ProviderService], VoiceProfileService] = VoiceProfileService,
               tts_service_factory: Callable[..., TTSService] = TTSService) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging(settings.log_level)
        application.state.provider_service = None
        application.state.system_service = None
        application.state.capability_service = None
        application.state.tts_service = None
        application.state.voice_profile_service = None
        application.state.long_form_service = None
        application.state.translation_service = None
        application.state.app_settings_service = None
        application.state.license_service = None
        application.state.local_token = None
        try:
            if settings.require_local_token:
                # Security P0: a fresh random token each process start
                # (never persisted/reused across restarts) that every other
                # API request must present - see backend/api/auth.py (the
                # one bootstrap exception) and this module's
                # request_boundary middleware below. Off by default
                # (Settings.require_local_token) so the existing test suite
                # is unaffected; scripts/run_backend.ps1 is what turns this
                # on for every real run.
                application.state.local_token = secrets.token_urlsafe(32)
                _write_token_file(settings.token_path, application.state.local_token)
            # Constructed first, ahead of the provider: AppSettingsService's
            # __init__ also re-applies any persisted Advanced > Debug Logging
            # level (see AppSettingsService._apply_log_level) as early in
            # startup as possible, and its resolve_effective_settings() below
            # decides which device (CUDA vs the experimental CPU path) the
            # provider gets constructed with - a customer's Settings >
            # Performance > Device choice, applied once here at startup
            # rather than hot-swapped into an already-running provider.
            application.state.app_settings_service = app_settings_service_factory(settings)
            effective_settings = application.state.app_settings_service.resolve_effective_settings(settings)
            application.state.license_service = LicenseService(effective_settings, application.state.app_settings_service._db)
            application.state.capability_service = HardwareCapabilityService(effective_settings)
            if provider_service_factory is create_provider_service:
                providers = provider_service_factory(
                    effective_settings, application.state.capability_service)
            else:
                # Test/custom factories historically accept only Settings.
                providers = provider_service_factory(effective_settings)
            application.state.provider_service = providers
            if settings.warm_up_on_start:
                # UX: without this, a customer's first "Tạo giọng nói" click
                # after opening the app eats the primary provider's real
                # model-load time as part of that job. Kick off one daemon
                # thread per currently-available provider that just calls
                # ensure_loaded() - never awaited, never blocks Uvicorn from
                # accepting connections or this lifespan from continuing.
                # ProviderService.ensure_loaded()'s own Condition/BUSY state
                # machine already makes this safe to race against a real
                # request that also calls it concurrently (the request simply
                # waits for the same in-flight load instead of starting a
                # second one). A failed warm-up (e.g. CUDA unavailable) is
                # only logged - see _warm_up_provider - the first real
                # request still goes through today's on-demand path.
                def _warm_up_provider(provider_id: str) -> None:
                    try:
                        logger.info("provider_warm_up_start provider=%s", provider_id)
                        providers.ensure_loaded(provider_id)
                        logger.info("provider_warm_up_done provider=%s", provider_id)
                    except Exception:
                        logger.exception("provider_warm_up_failed provider=%s", provider_id)

                for entry in providers.status().providers:
                    if entry.available:
                        threading.Thread(
                            target=_warm_up_provider, args=(entry.id,),
                            daemon=True, name=f"provider-warm-up-{entry.id}",
                        ).start()
            application.state.system_service = service_factory(providers)
            # No model/network work at construction time - just opens the
            # same local SQLite settings store TTSService already uses.
            application.state.translation_service = translation_service_factory(settings)
            # Constructed before TTSService specifically so a Short TTS job's
            # voice_id can also name a cloned voice profile (see
            # TTSService.validate_request()/_run()) - it has no dependency on
            # TTSService itself, so this reordering is safe.
            application.state.voice_profile_service = voice_profile_service_factory(settings, providers)
            application.state.tts_service = tts_service_factory(
                settings, providers, application.state.translation_service,
                application.state.voice_profile_service, application.state.app_settings_service)
            logger.info("backend_start version=%s", settings.app_version)
            yield
        finally:
            if application.state.tts_service is not None:
                await run_in_threadpool(application.state.tts_service.close)
            try:
                if application.state.system_service is not None:
                    application.state.system_service.close()
                if application.state.capability_service is not None:
                    application.state.capability_service.close()
            finally:
                # application.state.provider_service (not the local `providers`
                # variable) is used here because construction can now fail
                # before `providers` is ever assigned (app_settings_service_factory
                # or resolve_effective_settings raising, e.g. an invalid
                # persisted device value) - this stays safe either way.
                if application.state.provider_service is not None:
                    await run_in_threadpool(application.state.provider_service.shutdown)
                if application.state.local_token is not None:
                    _remove_token_file(settings.token_path)
                    application.state.local_token = None
                application.state.system_service = None
                application.state.capability_service = None
                application.state.provider_service = None
                application.state.tts_service = None
                application.state.voice_profile_service = None
                application.state.translation_service = None
                application.state.app_settings_service = None
                application.state.license_service = None
                logger.info("backend_stop")

    application = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    application.state.settings = settings
    register_handlers(application)

    # The one path request_boundary below exempts from needing the token
    # already - see backend/api/auth.py's own docstring for why this specific
    # exemption is still safe (Origin-gated, not "public").
    auth_token_path = f"{settings.api_prefix}/auth/token"

    @application.middleware("http")
    async def request_boundary(request: Request, call_next):
        if request.url.hostname not in settings.allowed_hosts:
            logger.warning("request_rejected code=INVALID_REQUEST reason=host")
            return error_response(ErrorCode.INVALID_REQUEST, 400)
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = None
            if declared_size is not None and declared_size > MAX_REQUEST_BODY_BYTES:
                logger.warning(
                    "request_rejected code=REFERENCE_AUDIO_TOO_LARGE reason=content_length size=%d",
                    declared_size,
                )
                return error_response(ErrorCode.REFERENCE_AUDIO_TOO_LARGE, 413)
        if (settings.require_local_token
                and request.url.path.startswith(settings.api_prefix)
                and request.url.path != auth_token_path):
            # Security P0 (checklist-bao-mat-truoc-dong-goi-17-09.md item 1):
            # every other API request must present the token this process
            # generated at startup. Read from the header first
            # (frontend/src/services/httpClient.ts's apiFetch) and fall back
            # to a `?token=` query param for the two request kinds that
            # cannot set a custom header at all - <audio src>/<a download>
            # against GET /api/audio/{id} (see resolveBackendUrl there).
            # Scoped to api_prefix specifically so the frontend static files
            # served below (Settings.serve_frontend) never need it - the
            # page itself has to load BEFORE it can fetch a token at all.
            supplied = request.headers.get("x-local-token") or request.query_params.get("token")
            expected = application.state.local_token
            if not expected or not supplied or not hmac.compare_digest(supplied, expected):
                logger.warning("request_rejected code=UNAUTHORIZED reason=local_token")
                return error_response(ErrorCode.UNAUTHORIZED, 401)
        try:
            return await call_next(request)
        except Exception as exc:
            # Normalize inside CORS so unexpected-error responses also carry
            # CORS headers for allowed clients. The global handler is a fallback.
            return await unexpected_error(request, exc)

    application.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins),
        allow_credentials=False, allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Local-Token"],
    )
    application.include_router(router, prefix=settings.api_prefix)

    if settings.serve_frontend:
        # "1 tiến trình, 1 cổng" (mục tiêu đóng gói 17/09): thay vì chạy
        # `npm run dev` ở một cổng riêng, phục vụ luôn bản build frontend
        # (frontend/dist, `npm run build`) từ chính backend - xem
        # Settings.serve_frontend's docstring in backend/config.py và
        # scripts/run_backend.ps1 (nơi duy nhất bật cờ này cho một lần chạy
        # thật). Route này được include_in_schema=False và luôn đăng ký SAU
        # include_router ở trên, nên mọi request /api/* vẫn khớp router đó
        # trước - route bắt-tất-cả này chỉ nhận những gì còn lại.
        dist_dir = settings.frontend_dist_dir.resolve()
        if dist_dir.is_dir():
            @application.get("/{full_path:path}", include_in_schema=False)
            async def serve_frontend(full_path: str) -> FileResponse:
                # Chặn path traversal (vd. "../../secrets") - chỉ phục vụ
                # file thật sự nằm trong dist_dir; mọi thứ khác (kể cả một
                # route phía client như "/history" mà React Router xử lý ở
                # trình duyệt, hoặc một request traversal) rơi về
                # index.html - đây chính là SPA fallback.
                candidate = (dist_dir / full_path).resolve() if full_path else dist_dir
                if candidate.is_file() and candidate.is_relative_to(dist_dir):
                    return FileResponse(candidate)
                return FileResponse(dist_dir / "index.html")
        else:
            logger.warning(
                "frontend_dist_missing path=%s - phục vụ frontend đã tắt cho lần chạy này, "
                "chạy `npm run build` trong thư mục frontend rồi khởi động lại.",
                dist_dir,
            )

    return application


app = create_app()


def run() -> None:
    import uvicorn
    settings = app.state.settings
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower(),
                access_log=False)


if __name__ == "__main__":
    run()
