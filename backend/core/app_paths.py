"""Single authority for mutable Voca Basic data; packaged resources are excluded."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path

    @property
    def settings_dir(self) -> Path: return self.root / "data"
    @property
    def database(self) -> Path: return self.settings_dir / "metadata.sqlite3"
    @property
    def audio_dir(self) -> Path: return self.root / "audio"
    @property
    def voice_profiles_dir(self) -> Path: return self.root / "voice-profiles"
    @property
    def reference_audio_dir(self) -> Path: return self.voice_profiles_dir / "references"
    @property
    def temp_dir(self) -> Path: return self.root / "temp"
    @property
    def logs_dir(self) -> Path: return self.root / "logs"
    @property
    def token_path(self) -> Path: return self.root / "runtime" / "session.token"

    def ensure(self, *directories: Path) -> None:
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)


def resolve_app_paths(environ: dict[str, str] | None = None, *, platform_name: str | None = None) -> AppPaths:
    """Resolve independently of cwd; LOCAL_AI_DATA_ROOT is the sole new override.

    LOCAL_AI_APP_DATA_DIR remains a compatibility alias for already-launched
    desktop builds, but has lower precedence and is never inferred from source.
    """
    env = os.environ if environ is None else environ
    override = (env.get("LOCAL_AI_DATA_ROOT") or env.get("LOCAL_AI_APP_DATA_DIR") or "").strip()
    if override:
        return AppPaths(Path(override).expanduser().resolve())
    is_windows = (platform_name or os.name) == "nt"
    if is_windows:
        local = (env.get("LOCALAPPDATA") or "").strip()
        if local:
            return AppPaths((Path(local) / "Voca Basic").resolve())
        # Only a non-production/test fallback when Windows does not expose
        # LOCALAPPDATA; never use cwd or a packaged resource root.
        return AppPaths((Path.home() / "AppData" / "Local" / "Voca Basic").resolve())
    return AppPaths((Path.home() / ".local" / "share" / "Voca Basic").resolve())
