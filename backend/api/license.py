from typing import Annotated
from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from backend.dependencies import get_license_service
from backend.schemas.license import (
    ActivateLicenseRequest,
    ActivateLicenseResponse,
    LicenseStatusResponse,
)
from backend.services.license_service import LicenseService

router = APIRouter(prefix="/license", tags=["license"])


@router.get("/status", response_model=LicenseStatusResponse)
async def get_license_status(
    service: Annotated[LicenseService, Depends(get_license_service)],
) -> LicenseStatusResponse:
    """Returns current hardware Machine ID and license activation status."""
    return await run_in_threadpool(service.get_status)


@router.post("/activate", response_model=ActivateLicenseResponse)
async def activate_license(
    request: ActivateLicenseRequest,
    service: Annotated[LicenseService, Depends(get_license_service)],
) -> ActivateLicenseResponse:
    """Activates software with an Ed25519-signed license key."""
    status = await run_in_threadpool(service.activate, request.license_key)
    return ActivateLicenseResponse(ok=status.is_active, status=status)


@router.post("/deactivate", response_model=LicenseStatusResponse)
async def deactivate_license(
    service: Annotated[LicenseService, Depends(get_license_service)],
) -> LicenseStatusResponse:
    """Removes existing license key from device."""
    await run_in_threadpool(service.deactivate)
    return await run_in_threadpool(service.get_status)


@router.post("/refresh", response_model=LicenseStatusResponse)
async def refresh_license(
    service: Annotated[LicenseService, Depends(get_license_service)],
) -> LicenseStatusResponse:
    """Synchronizes license token with Cloud server."""
    return await run_in_threadpool(service.refresh_license)

