"""Translation (Gemini BYOK) settings payloads.

Deliberately separate from backend/schemas/system.py: this is user-owned,
mutable configuration (an API key the customer supplies and can change or
clear), not read-only hardware/runtime status.
"""
from pydantic import BaseModel, ConfigDict


class TranslationSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None/empty clears the stored key (equivalent to DELETE).
    gemini_api_key: str | None = None


class TranslationSettingsStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    configured: bool
    # Never echoes the key back in full - only enough to let the user confirm
    # "yes, that's the key I saved" without re-displaying the secret.
    key_preview: str | None = None
