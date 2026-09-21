"""Persistence for the General/Audio/Performance/Storage/Advanced settings
tabs. See backend/schemas/app_settings.py for exactly what is (and isn't)
covered here, and why.
"""
from __future__ import annotations

import logging
from pathlib import Path

from backend.config import Settings
from backend.logging_config import configure_logging
from backend.persistence import Repository
from backend.schemas.app_settings import AppSettings, AppSettingsResponse

logger = logging.getLogger("backend.app_settings")

SETTINGS_KEY = "app_settings"

# debug_logs=True maps to DEBUG; False restores the level the process was
# actually started with (settings.log_level), not a hardcoded "INFO" - so a
# customer running with LOCAL_AI_LOG_LEVEL=warning who toggles debug on and
# back off ends up exactly where they started.
_DEBUG_LEVEL = "DEBUG"


class AppSettingsService:
    def __init__(self, settings: Settings):
        self._settings = settings
        # Same SQLite file/table TranslationService and TTSService already
        # use for the "settings" key-value table - no new storage mechanism.
        self._db = Repository(settings)
        # Apply any previously-saved debug_logs preference immediately on
        # startup, so a restart doesn't silently drop back to the configured
        # default while the UI still shows the toggle on.
        self._apply_log_level(self.resolve_debug_logs())

    def get(self) -> AppSettingsResponse:
        stored = self._db.get_setting(SETTINGS_KEY, default={}) or {}
        # Ignore unknown/stale keys (e.g. from a field removed in a later
        # version) instead of failing - an old settings blob should never
        # hard-crash a newer client.
        known_fields = AppSettings.model_fields
        filtered = {key: value for key, value in stored.items() if key in known_fields}
        try:
            base = AppSettings(**filtered)
        except Exception:
            logger.warning("app_settings_corrupt_falling_back_to_defaults")
            base = AppSettings()
        output_dir = Path(base.output_dir) if base.output_dir else Path(self._settings.output_dir)
        return AppSettingsResponse(
            **base.model_dump(),
            actual_db_path=str(self._db.path),
            actual_output_dir=str(output_dir),
            output_dir_bytes=self._compute_dir_bytes(output_dir),
        )

    def save(self, payload: AppSettings) -> AppSettingsResponse:
        self._db.put("settings", SETTINGS_KEY, payload.model_dump())
        self._apply_log_level(payload.debug_logs)
        logger.info("app_settings_updated")
        return self.get()

    @staticmethod
    def _compute_dir_bytes(directory: Path) -> int:
        """Real total size of every file under `directory`. Missing directory
        (e.g. nothing has been synthesized yet on a fresh install) is 0 bytes,
        not an error - this is a display value, not a precondition check.
        """
        if not directory.exists():
            return 0
        total = 0
        try:
            for path in directory.rglob("*"):
                if path.is_file():
                    try:
                        total += path.stat().st_size
                    except OSError:
                        continue
        except OSError:
            logger.warning("app_settings_output_dir_scan_failed")
        return total

    def _apply_log_level(self, debug_logs: bool) -> None:
        configure_logging(_DEBUG_LEVEL if debug_logs else self._settings.log_level)

    def resolve_debug_logs(self) -> bool:
        stored = self._db.get_setting(SETTINGS_KEY, default={}) or {}
        value = stored.get("debug_logs")
        return bool(value) if isinstance(value, bool) else False

    def resolve_output_dir(self) -> Path:
        """Used by TTSService to pick the audio output directory per request
        instead of only ever reading the frozen startup config. Returns a
        pathlib.Path - the configured default if the customer never set one.
        """
        stored = self._db.get_setting(SETTINGS_KEY, default={}) or {}
        custom = stored.get("output_dir")
        return Path(custom) if custom else Path(self._settings.output_dir)

    def resolve_effective_settings(self, base: Settings) -> Settings:
        """Applied once, at backend startup (see backend/main.py's lifespan),
        before the TTS provider is constructed - NOT hot-reloaded into an
        already-running provider. Only `device` currently needs this: it
        changes which provider gets constructed (CUDA vs the experimental CPU
        path), which cannot safely happen mid-run. Every other Performance/
        Audio/Advanced field (retry_count, num_steps, output_dir, debug_logs)
        is instead resolved live, per request, straight from this service -
        see TTSService._run() and LongFormTTSService._run().
        """
        stored = self._db.get_setting(SETTINGS_KEY, default={}) or {}
        if stored.get("device") == "cpu" and base.omnivoice_device != "cpu":
            import dataclasses

            try:
                return dataclasses.replace(base, omnivoice_device="cpu")
            except ValueError:
                logger.warning("app_settings_invalid_device_override_ignored")
        return base

    def resolve_retry_count(self) -> int:
        stored = self._db.get_setting(SETTINGS_KEY, default={}) or {}
        value = stored.get("retry_count")
        return value if isinstance(value, int) and 1 <= value <= 3 else 2

    def resolve_num_steps(self) -> int:
        stored = self._db.get_setting(SETTINGS_KEY, default={}) or {}
        value = stored.get("num_steps")
        return value if isinstance(value, int) and 8 <= value <= 32 else 16
