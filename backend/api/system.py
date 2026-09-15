from typing import Annotated
from fastapi import APIRouter, Depends
from backend.dependencies import get_system_service
from backend.schemas.system import SystemStatus
from backend.services.system_service import SystemService

router = APIRouter()


@router.get("/system/status", response_model=SystemStatus, tags=["system"])
def system_status(service: Annotated[SystemService, Depends(get_system_service)]) -> SystemStatus:
    # Sync route runs probing in FastAPI's thread pool, not the event loop.
    return service.status()
