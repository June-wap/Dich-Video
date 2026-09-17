"""Translation (Gemini BYOK) settings endpoints. See
backend/services/translation_service.py for the BYOK rationale.

PUT is deliberately not used: backend/main.py's CORS middleware only allows
GET/POST/DELETE, and this router stays within that rather than widening CORS
for one endpoint.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.dependencies import get_translation_service
from backend.schemas.settings import TranslationSettingsRequest, TranslationSettingsStatus
from backend.services.translation_service import TranslationService

router = APIRouter(prefix="/settings/translation", tags=["settings"])


def _status(service: TranslationService) -> TranslationSettingsStatus:
    key = service.get_api_key()
    return TranslationSettingsStatus(
        configured=bool(key),
        key_preview=service.key_preview(key) if key else None,
    )


@router.get("", response_model=TranslationSettingsStatus)
def get_translation_settings(
    service: Annotated[TranslationService, Depends(get_translation_service)],
) -> TranslationSettingsStatus:
    return _status(service)


@router.post("", response_model=TranslationSettingsStatus)
def set_translation_settings(
    request: TranslationSettingsRequest,
    service: Annotated[TranslationService, Depends(get_translation_service)],
) -> TranslationSettingsStatus:
    service.set_api_key(request.gemini_api_key)
    return _status(service)


@router.delete("", response_model=TranslationSettingsStatus)
def clear_translation_settings(
    service: Annotated[TranslationService, Depends(get_translation_service)],
) -> TranslationSettingsStatus:
    service.set_api_key(None)
    return _status(service)
