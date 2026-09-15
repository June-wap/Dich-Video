"""ASGI factory: one primary provider per app lifespan; model loading stays lazy."""
from contextlib import asynccontextmanager
import logging
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

from backend.api.router import router
from backend.config import Settings
from backend.errors import ErrorCode
from backend.errors.handlers import error_response, register_handlers, unexpected_error
from backend.logging_config import configure_logging
from backend.services.system_service import SystemService
from backend.services.provider_service import ProviderService, create_provider_service
from backend.services.tts_service import TTSService
from backend.services.voice_profile_service import VoiceProfileService
from backend.services.long_form_service import LongFormTTSService

logger = logging.getLogger("backend.lifecycle")


def create_app(settings: Settings | None = None,
               service_factory: Callable[[ProviderService], SystemService] = SystemService,
               provider_service_factory: Callable[[Settings], ProviderService] = create_provider_service,
               tts_service_factory: Callable[[Settings, ProviderService], TTSService] = TTSService,
               voice_profile_service_factory: Callable[[Settings, ProviderService], VoiceProfileService] = VoiceProfileService) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging(settings.log_level)
        providers = provider_service_factory(settings)
        application.state.provider_service = providers
        application.state.system_service = None
        application.state.tts_service = None
        application.state.voice_profile_service = None
        application.state.long_form_service = None
        try:
            application.state.system_service = service_factory(providers)
            application.state.tts_service = tts_service_factory(settings, providers)
            application.state.voice_profile_service = voice_profile_service_factory(settings, providers)
            application.state.long_form_service = LongFormTTSService(
                settings, providers, application.state.voice_profile_service)
            logger.info("backend_start version=%s", settings.app_version)
            yield
        finally:
            if application.state.long_form_service is not None:
                await run_in_threadpool(application.state.long_form_service.close)
                application.state.long_form_service = None
            try:
                if application.state.system_service is not None:
                    application.state.system_service.close()
            finally:
                await run_in_threadpool(providers.shutdown)
                application.state.system_service = None
                application.state.provider_service = None
                application.state.tts_service = None
                application.state.voice_profile_service = None
                logger.info("backend_stop")

    application = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    application.state.settings = settings
    register_handlers(application)

    @application.middleware("http")
    async def request_boundary(request: Request, call_next):
        if request.url.hostname not in settings.allowed_hosts:
            logger.warning("request_rejected code=INVALID_REQUEST reason=host")
            return error_response(ErrorCode.INVALID_REQUEST, 400)
        try:
            return await call_next(request)
        except Exception as exc:
            # Normalize inside CORS so unexpected-error responses also carry
            # CORS headers for allowed clients. The global handler is a fallback.
            return await unexpected_error(request, exc)

    application.add_middleware(
        CORSMiddleware, allow_origins=list(settings.cors_origins),
        allow_credentials=False, allow_methods=["GET", "POST", "DELETE"], allow_headers=["Content-Type"],
    )
    application.include_router(router, prefix=settings.api_prefix)
    return application


app = create_app()


def run() -> None:
    import uvicorn
    settings = app.state.settings
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower(),
                access_log=False)


if __name__ == "__main__":
    run()
