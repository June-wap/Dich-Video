from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator
from backend.schemas.common import ErrorBody


class LongFormRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    text: StrictStr = Field(min_length=1, max_length=100000)
    language: StrictStr = "vi"
    profile_id: StrictStr
    speed: float = Field(default=1.0, strict=True)
    format: Literal["wav", "mp3"] = "wav"

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("INVALID_TEXT")
        return value

    @field_validator("speed")
    @classmethod
    def native_speed(cls, value):
        if value != 1.0:
            raise ValueError("INVALID_SPEED")
        return value


class LongFormStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    job_id: str
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
    progress_percent: float = 0
    audio_url: str | None = None
    error: ErrorBody | None = None
