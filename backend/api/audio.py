import re
from typing import Annotated
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from backend.dependencies import get_tts_service
from backend.errors import ApplicationError, ErrorCode
from backend.services.tts_service import TTSService

router = APIRouter()
SAFE_ARTIFACT_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(wav|mp3)$")


@router.get("/audio/{artifact_id}", tags=["audio"])
async def get_audio(
    artifact_id: str,
    service: Annotated[TTSService, Depends(get_tts_service)],
) -> FileResponse:
    if not SAFE_ARTIFACT_RE.fullmatch(artifact_id):
        raise ApplicationError(ErrorCode.ARTIFACT_NOT_FOUND)

    base_dir = service.output_dir.resolve()
    target_file = (base_dir / artifact_id).resolve()

    try:
        if not target_file.is_relative_to(base_dir):
            raise ApplicationError(ErrorCode.ARTIFACT_NOT_FOUND)
    except (ValueError, AttributeError):
        raise ApplicationError(ErrorCode.ARTIFACT_NOT_FOUND)

    if not target_file.is_file():
        raise ApplicationError(ErrorCode.ARTIFACT_NOT_FOUND)

    media_type = "audio/wav" if artifact_id.endswith(".wav") else "audio/mpeg"
    return FileResponse(
        path=target_file,
        media_type=media_type,
        filename=artifact_id,
    )
