from typing import Annotated
from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_tts_service, require_valid_license
from backend.schemas.tts import TTSRequest, TTSResponse
from backend.services.tts_service import TTSService

router = APIRouter()


@router.post("/tts", response_model=TTSResponse, tags=["tts"], dependencies=[Depends(require_valid_license)])
async def synthesize_tts(
    request: TTSRequest,
    service: Annotated[TTSService, Depends(get_tts_service)],
) -> TTSResponse:
    return await run_in_threadpool(service.synthesize, request)

