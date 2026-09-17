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

    # resolve_audio_path() looks up the directory this specific job actually
    # wrote to (which may differ from today's default if Settings > Audio's
    # Output Directory changed since), falling back to the current default
    # directory - see TTSService.resolve_audio_path(). artifact_id is already
    # constrained by SAFE_ARTIFACT_RE to a bare "<uuid>.<ext>" with no path
    # separators, so joining it onto either directory can never escape it.
    target_file = service.resolve_audio_path(artifact_id).resolve()

    if not target_file.is_file():
        raise ApplicationError(ErrorCode.ARTIFACT_NOT_FOUND)

    media_type = "audio/wav" if artifact_id.endswith(".wav") else "audio/mpeg"
    return FileResponse(
        path=target_file,
        media_type=media_type,
        filename=artifact_id,
    )
