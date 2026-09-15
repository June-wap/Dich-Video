from typing import Any, Literal
from pydantic import BaseModel, ConfigDict


class TTSRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Any = None
    language: Any = None
    voice_id: Any = "omnivoice_auto"
    speed: Any = 1.0
    format: Any = "wav"


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
