from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from backend.schemas.providers import ProviderState


class AudioContract(BaseModel):
    model_config = ConfigDict(frozen=True)
    sample_rate: Literal[24000] = 24000
    channels: Literal[1] = 1


class SystemStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: Literal["ready", "degraded"]
    python_version: str
    torch_version: str | None
    cuda_available: bool
    gpu_name: str | None
    primary_provider: str | None
    provider_state: ProviderState | None
    audio: AudioContract = Field(default_factory=AudioContract)
    runtime_mode: Literal["local"] = "local"


class SystemLogsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    # Real, in-memory-only backend log lines (see backend/logging_config.py's
    # ring buffer) - oldest first, capped at MAX_LOG_LINES. Never written to
    # or read from disk; empty on a backend that just started with nothing
    # logged yet.
    logs: list[str]
