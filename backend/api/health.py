from fastapi import APIRouter, Request
from backend.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
def health(request: Request) -> HealthResponse:
    return HealthResponse(version=request.app.state.settings.app_version)
