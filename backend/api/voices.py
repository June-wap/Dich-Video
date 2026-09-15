from typing import Annotated
from fastapi import APIRouter, Depends, File, Form, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_voice_profile_service
from backend.schemas.voices import (
    CloneTestRequest,
    CloneTTSResponse,
    VoiceProfileListResponse,
    VoiceProfileResponse,
)
from backend.services.voice_profile_service import VoiceProfileService

router = APIRouter(prefix="/voices", tags=["voices"])


@router.post("/profiles", response_model=VoiceProfileResponse)
async def create_profile(
    service: Annotated[VoiceProfileService, Depends(get_voice_profile_service)],
    file: Annotated[UploadFile | None, File()] = None,
    reference_transcript: Annotated[str | None, Form()] = None,
    name: Annotated[str | None, Form()] = None,
) -> VoiceProfileResponse:
    from backend.errors import ApplicationError, ErrorCode
    if file is None:
        raise ApplicationError(ErrorCode.INVALID_REFERENCE_AUDIO)
    audio_bytes = await file.read()
    filename = file.filename or "audio.wav"
    return await run_in_threadpool(
        service.create_profile,
        audio_bytes=audio_bytes,
        filename=filename,
        transcript=reference_transcript,
        name=name,
    )


@router.get("/profiles", response_model=VoiceProfileListResponse)
async def list_profiles(
    service: Annotated[VoiceProfileService, Depends(get_voice_profile_service)],
) -> VoiceProfileListResponse:
    return await run_in_threadpool(service.list_profiles)


@router.get("/profiles/{profile_id}", response_model=VoiceProfileResponse)
async def get_profile(
    profile_id: str,
    service: Annotated[VoiceProfileService, Depends(get_voice_profile_service)],
) -> VoiceProfileResponse:
    return await run_in_threadpool(service.get_profile, profile_id)


@router.delete("/profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    service: Annotated[VoiceProfileService, Depends(get_voice_profile_service)],
) -> dict:
    await run_in_threadpool(service.delete_profile, profile_id)
    return {"ok": True, "data": {"profile_id": profile_id, "deleted": True}}


@router.post("/profiles/{profile_id}/test", response_model=CloneTTSResponse)
async def synthesize_clone_test(
    profile_id: str,
    request: CloneTestRequest,
    service: Annotated[VoiceProfileService, Depends(get_voice_profile_service)],
) -> CloneTTSResponse:
    return await run_in_threadpool(service.synthesize_clone, profile_id, request)
