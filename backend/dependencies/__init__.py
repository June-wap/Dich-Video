from fastapi import Request
from backend.errors import ApplicationError, ErrorCode
from backend.services.system_service import SystemService
from backend.services.provider_service import ProviderService
from backend.services.tts_service import TTSService
from backend.services.voice_profile_service import VoiceProfileService
from backend.services.translation_service import TranslationService
from backend.services.app_settings_service import AppSettingsService


def get_provider_service(request: Request) -> ProviderService:
    service = getattr(request.app.state, "provider_service", None)
    if service is None:
        raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)
    return service


def get_system_service(request: Request) -> SystemService:
    service = getattr(request.app.state, "system_service", None)
    if service is None:
        raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)
    return service


def get_tts_service(request: Request) -> TTSService:
    service = getattr(request.app.state, "tts_service", None)
    if service is None:
        raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)
    return service


def get_voice_profile_service(request: Request) -> VoiceProfileService:
    service = getattr(request.app.state, "voice_profile_service", None)
    if service is None:
        raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)
    return service


def get_translation_service(request: Request) -> TranslationService:
    service = getattr(request.app.state, "translation_service", None)
    if service is None:
        raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)
    return service


def get_app_settings_service(request: Request) -> AppSettingsService:
    service = getattr(request.app.state, "app_settings_service", None)
    if service is None:
        raise ApplicationError(ErrorCode.SERVICE_UNAVAILABLE)
    return service

