from fastapi import APIRouter
from backend.api.health import router as health_router
from backend.api.system import router as system_router
from backend.api.providers import router as provider_router
from backend.api.tts import router as tts_router
from backend.api.audio import router as audio_router
from backend.api.voices import router as voices_router
from backend.api.long_form import router as long_form_router
from backend.schemas.common import ErrorResponse

router = APIRouter(responses={code: {"model": ErrorResponse} for code in (400, 404, 405, 422, 500, 503)})
router.include_router(health_router)
router.include_router(system_router)
router.include_router(provider_router)
router.include_router(tts_router)
router.include_router(audio_router)
router.include_router(voices_router)
router.include_router(long_form_router)
