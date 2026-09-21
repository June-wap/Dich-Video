"""General app settings (General/Audio/Performance/Storage/Advanced tabs).

Deliberately separate from backend/schemas/settings.py (Gemini BYOK translation
key), which has its own security handling (never echoes the secret back).
This payload has no secrets, so it is safe to read back in full on GET.

Stored as one JSON blob under settings key "app_settings" via the same
Repository key-value table TranslationService/TTSService already use - no
schema migration needed.

Every field's default here is what gets saved the FIRST time a customer opens
Settings and hits Save on anything. A customer who has never done that at all
(including a fresh install) gets the true legacy behavior instead, which is
not always the same as these defaults - see
AppSettingsService.resolve_retry_count()/resolve_num_steps()/
resolve_silence_trim() for exactly where and why that distinction matters
(short version: retry_count's real legacy value is 1, not 2; num_steps' real
legacy behavior is "let the provider pick 16 normal / 24 cloned", not a flat
16; silence_trim's real legacy value is False, not True). Everything else
(app_lang, app_theme, output_format, pause_policy_ms, device, quality_preset,
debug_logs) has no such gap - its schema default already equals its old
hardcoded behavior.

Fields intentionally NOT here:
- SQLite WAL toggle: removed from the UI entirely rather than persisted here,
  because backend/persistence.py enables WAL unconditionally
  (`PRAGMA journal_mode=WAL`) - a toggle for it can never have any effect,
  so keeping it would just move the "looks saved, does nothing" problem here.

`device` ("gpu"/"cpu") IS here, unlike an earlier version of this file assumed:
the former engine had a real (if unverified/unbenchmarked)
CPU code path gated behind its own allow_unverified_cpu flag - backend/config.py
and backend/services/provider_service.py were updated alongside this field to
honor it. Choosing "cpu" only takes effect on the *next* backend startup (the
provider is constructed once at lifespan startup, not hot-swappable mid-run) -
see AppSettingsService.resolve_effective_settings().
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # --- General ---
    app_lang: str = "vi"
    app_theme: str = "light"
    notify_completion: bool = True
    notify_errors: bool = True

    # --- Audio ---
    # "wav", "mp3", or "wav+mp3" - a DISPLAY/default-selection value only.
    # The real /api/tts request format is strictly "wav" or "mp3" (see
    # backend/schemas/tts.py's TTSData.format Literal and
    # tts_service.py's validate_request(), which rejects anything else with
    # INVALID_FORMAT) - there is no third "produce both, always" request
    # mode. The frontend (frontend/src/pages/TTSPage.tsx) maps "wav+mp3"
    # here to submitting "mp3" per job, which is the closest real backend
    # behavior: whenever a job's format is "mp3", TTSService keeps BOTH the
    # original .wav and the exported .mp3 on disk (see tts_service.py's
    # `outputs = [wav_path] + ([mp3_path] if fmt == "mp3" else [])`) - it
    # just serves the .mp3 as the primary played-back artifact. "wav" alone
    # never produces the extra .mp3 copy.
    output_format: str = "wav+mp3"
    pause_policy_ms: int = 400
    silence_trim: bool = True
    # None = use the backend's configured default (Settings.output_dir).
    output_dir: str | None = None

    # --- Performance ---
    # "cpu" is experimental and unverified for output quality/benchmarking
    # (the former provider reported cpu_verified=False even when
    # it runs) and is dramatically slower than CUDA. Requires a backend
    # restart to take effect - see this module's docstring.
    device: Literal["gpu", "cpu"] = "gpu"
    quality_preset: str = "balanced"
    retry_count: int = Field(default=2, ge=1, le=3)

    # --- Advanced ---
    num_steps: int = Field(default=16, ge=8, le=32)
    debug_logs: bool = False


class AppSettingsResponse(AppSettings):
    """AppSettings plus read-only, server-computed fields the UI displays but
    can never set directly (Storage tab). Real values, not the previous
    hardcoded placeholder strings.
    """
    model_config = ConfigDict(frozen=True)

    actual_db_path: str
    actual_output_dir: str
    # Real total size (bytes) of every file in actual_output_dir - this is
    # the customer's own generated audio, not a separate disposable cache, so
    # the UI shows it as disk usage rather than offering a blanket "clear"
    # (deleting these would silently break History/playback entries that
    # still reference them).
    output_dir_bytes: int
