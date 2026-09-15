from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict


class ProviderState(str, Enum):
    NOT_LOADED = "NOT_LOADED"
    LOADING = "LOADING"
    READY = "READY"
    ERROR = "ERROR"
    UNLOADING = "UNLOADING"
    UNAVAILABLE = "UNAVAILABLE"


class VerifiedLanguage(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    display_name: str
    native_name: str
    status: Literal["VERIFIED"]
    verification_scope: str
    cloned_live_verified: bool
    production_ready: bool


class ProviderStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    available: bool
    state: ProviderState
    loaded: bool
    device: str
    languages: tuple[str, ...]
    language_metadata: tuple[VerifiedLanguage, ...]
    experimental_languages_enabled: bool
    production_ready: bool
    error_code: str | None = None


class ProvidersResponse(BaseModel):
    primary: str
    providers: list[ProviderStatus]
