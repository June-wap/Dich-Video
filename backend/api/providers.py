from typing import Annotated
from fastapi import APIRouter, Depends
from backend.dependencies import get_provider_service
from backend.schemas.providers import ProvidersResponse
from backend.services.provider_service import ProviderService

router = APIRouter()


@router.get("/providers/status", response_model=ProvidersResponse, tags=["providers"])
def provider_status(service: Annotated[ProviderService, Depends(get_provider_service)]) -> ProvidersResponse:
    return service.status()
