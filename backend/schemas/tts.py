from typing import Any, Literal
from pydantic import BaseModel, ConfigDict

from backend.schemas.common import ErrorBody


class TTSRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Any = None
    language: Any = None
    voice_id: Any = "omnivoice_auto"
    speed: Any = 1.0
    format: Any = "wav"
    # Optional client-supplied idempotency token. When set, resubmitting the
    # same key returns the existing job instead of creating a duplicate one.
    idempotency_key: Any = None


class TTSData(BaseModel):
    model_config = ConfigDict(frozen=True)

    generation_id: str
    status: Literal["completed"] = "completed"
    provider: str
    language: str
    voice_id: str
    duration_seconds: float
    sample_rate: int
    channels: int
    format: Literal["wav", "mp3"]
    audio_url: str


class TTSResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Literal[True] = True
    data: TTSData


class TTSStatus(BaseModel):
    """Minimal job-status payload for the async short-TTS job API.

    Mirrors LongFormStatus's exposure philosophy: no source text, filesystem
    paths, or provider/model internals. Only job_id, status, and a safe
    audio_url/error once terminal.
    """
    model_config = ConfigDict(frozen=True)

    job_id: str
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"]
    audio_url: str | None = None
    error: ErrorBody | None = None
