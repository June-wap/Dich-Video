from typing import Any, Literal
from pydantic import BaseModel, ConfigDict


class ReferenceAudioInfo(BaseModel):
    model_config = ConfigDict(frozen=True)

    duration_seconds: float
    sample_rate: int
    channels: int


class VoiceProfileData(BaseModel):
    model_config = ConfigDict(frozen=True)

    profile_id: str
    name: str
    provider: str
    status: Literal["ready"] = "ready"
    reference: ReferenceAudioInfo | None = None


class VoiceProfileResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Literal[True] = True
    data: VoiceProfileData


class VoiceProfileListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Literal[True] = True
    data: list[VoiceProfileData]


class CloneTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Any = None
    language: Any = "vi"
    speed: Any = 1.0
    format: Any = "wav"


class CloneTTSData(BaseModel):
    model_config = ConfigDict(frozen=True)

    generation_id: str
    profile_id: str
    status: Literal["completed"] = "completed"
    provider: str
    language: str
    duration_seconds: float
    sample_rate: int
    channels: int
    format: Literal["wav", "mp3"]
    audio_url: str


class CloneTTSResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Literal[True] = True
    data: CloneTTSData
