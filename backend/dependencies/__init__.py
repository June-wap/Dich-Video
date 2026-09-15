from fastapi import Request
from backend.errors import ApplicationError, ErrorCode
from backend.services.system_service import SystemService
from backend.services.provider_service import ProviderService
from backend.services.tts_service import TTSService
from backend.services.voice_profile_service import VoiceProfileService


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

