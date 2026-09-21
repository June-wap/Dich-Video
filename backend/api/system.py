from typing import Annotated
from fastapi import APIRouter, Depends
from backend.dependencies import get_system_service, get_capability_service
from backend.logging_config import get_recent_logs
from backend.schemas.system import SystemLogsResponse, SystemStatus
from backend.services.system_service import SystemService
from backend.services.capability_service import HardwareCapabilityService

router = APIRouter()


@router.get("/system/status", response_model=SystemStatus, tags=["system"])
def system_status(service: Annotated[SystemService, Depends(get_system_service)]) -> SystemStatus:
    # Sync route runs probing in FastAPI's thread pool, not the event loop.
    return service.status()


@router.get("/system/capabilities", tags=["system"])
def system_capabilities(service: Annotated[HardwareCapabilityService, Depends(get_capability_service)]) -> dict:
    return service.response()


@router.get("/system/logs", response_model=SystemLogsResponse, tags=["system"])
def system_logs() -> SystemLogsResponse:
    # No service dependency needed - the ring buffer lives on the "backend"
    # logger itself (see backend/logging_config.py), independent of any
    # per-request service. Diagnostics > Open Logs (Task 12) uses this
    # instead of a hardcoded sample transcript.
    return SystemLogsResponse(logs=get_recent_logs())
