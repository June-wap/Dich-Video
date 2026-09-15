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
    omnivoice_available: bool
    omnivoice_model_loaded: bool
    primary_provider: str
    provider_state: ProviderState
    audio: AudioContract = Field(default_factory=AudioContract)
    runtime_mode: Literal["local"] = "local"
