"""General app settings endpoints (General/Audio/Performance/Storage/Advanced
tabs). See backend/services/app_settings_service.py.

PUT is deliberately not used here either, matching backend/api/settings.py's
reasoning: backend/main.py's CORS middleware only allows GET/POST/DELETE.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.dependencies import get_app_settings_service
from backend.schemas.app_settings import AppSettings, AppSettingsResponse
from backend.services.app_settings_service import AppSettingsService

router = APIRouter(prefix="/settings/app", tags=["settings"])


@router.get("", response_model=AppSettingsResponse)
def get_app_settings(
    service: Annotated[AppSettingsService, Depends(get_app_settings_service)],
) -> AppSettingsResponse:
    return service.get()


@router.post("", response_model=AppSettingsResponse)
def save_app_settings(
    request: AppSettings,
    service: Annotated[AppSettingsService, Depends(get_app_settings_service)],
) -> AppSettingsResponse:
    return service.save(request)
