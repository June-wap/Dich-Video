"""Async short-TTS job API: create, fetch by id, and list persisted history.

Mirrors the long-form job API's exposure/status conventions (direct typed
JSON, no ok/data envelope). The legacy synchronous `POST /api/tts` endpoint
(backend/api/tts.py) is unchanged and still returns a completed TTSResponse;
this router is an additive sibling under /tts/jobs.
"""
from typing import Annotated

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_tts_service
from backend.schemas.tts import TTSRequest, TTSStatus
from backend.services.tts_service import TTSService

router = APIRouter(prefix="/tts/jobs", tags=["tts"])


@router.post("", response_model=TTSStatus, status_code=202, response_model_exclude_none=True)
async def create_job(
    request: TTSRequest,
    service: Annotated[TTSService, Depends(get_tts_service)],
) -> TTSStatus:
    return await run_in_threadpool(service.submit, request)


@router.get("", response_model=list[TTSStatus], response_model_exclude_none=True)
async def list_jobs(
    service: Annotated[TTSService, Depends(get_tts_service)],
) -> list[TTSStatus]:
    return await run_in_threadpool(service.history)


@router.get("/{job_id}", response_model=TTSStatus, response_model_exclude_none=True)
async def get_job(
    job_id: str,
    service: Annotated[TTSService, Depends(get_tts_service)],
) -> TTSStatus:
    return await run_in_threadpool(service.status, job_id)
