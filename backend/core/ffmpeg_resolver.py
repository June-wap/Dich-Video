"""Authoritative FFmpeg binary resolution for Voca Basic backend services.

Production must resolve the bundled FFmpeg binary deterministically and must
never depend on or consult the customer's PATH.
Development fallback to PATH is strictly isolated to non-production environments.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import sys

logger = logging.getLogger("backend.core.ffmpeg")


def is_packaged_production(environ: dict[str, str] | None = None) -> bool:
    """Determine whether the backend is running in packaged production layout."""
    env = os.environ if environ is None else environ

    # Explicit flag passed by desktop/backend-launch.cjs
    flag = env.get("LOCAL_AI_PRODUCTION") or env.get("LOCAL_AI_PACKAGED") or ""
    if flag.strip().lower() in {"1", "true", "yes"}:
        return True

    # Check filesystem layout relative to this file
    # Packaged layout: <AppRoot>/resources/backend/core/ffmpeg_resolver.py
    try:
        resolved_file = Path(__file__).resolve()
        backend_dir = resolved_file.parents[1]
        resources_dir = resolved_file.parents[2]
        app_root = resources_dir.parent

        if resources_dir.name.lower() == "resources":
            exe_names = ("voca basic.exe", "vocabasic.exe")
            if any((app_root / exe).is_file() for exe in exe_names):
                return True
            if (resources_dir / "frontend").is_dir() and (resources_dir / "backend").is_dir():
                return True
    except Exception:
        pass

    return False


def resolve_ffmpeg_path(environ: dict[str, str] | None = None) -> Path | None:
    """Resolve the authoritative FFmpeg executable path.

    Order of resolution:
    1. Explicit environment override: LOCAL_AI_FFMPEG_PATH or FFMPEG_PATH.
       If set and exists, it is returned. If set but nonexistent, returns None (fail-closed).
    2. Packaged Core App candidates:
       - <resources>/bin/ffmpeg.exe
       - <resources>/ffmpeg/ffmpeg.exe
       - <resources>/ffmpeg/bin/ffmpeg.exe
       - <app_root>/ffmpeg.exe
       - <app_root>/bin/ffmpeg.exe
    3. Development repository candidates:
       - <repo_root>/release/bin/ffmpeg.exe
       - <repo_root>/bin/ffmpeg.exe
       - Python prefix sibling: <sys.prefix>/../bin/ffmpeg.exe or <sys.prefix>/../../resources/bin/ffmpeg.exe
    4. Development PATH fallback:
       STRICTLY permitted only when not running in packaged production.
       In production, PATH is NEVER consulted.
    """
    env = os.environ if environ is None else environ

    # 1. Explicit override
    override = (env.get("LOCAL_AI_FFMPEG_PATH") or env.get("FFMPEG_PATH") or "").strip()
    if override:
        override_path = Path(override).expanduser().resolve()
        if override_path.is_file():
            return override_path
        logger.warning("Configured FFmpeg path does not exist: %s", override)
        return None

    # Determine filesystem anchors
    this_file = Path(__file__).resolve()
    core_dir = this_file.parent
    backend_dir = core_dir.parent
    candidate_root_1 = backend_dir.parent  # In packaged: <AppRoot>/resources; In dev: <repo_root>
    candidate_root_2 = candidate_root_1.parent  # In packaged: <AppRoot>; In dev: parent of repo

    is_windows = sys.platform == "win32"
    exe_name = "ffmpeg.exe" if is_windows else "ffmpeg"

    bundled_candidates: list[Path] = [
        # Resources directory candidates (packaged production layout)
        candidate_root_1 / "bin" / exe_name,
        candidate_root_1 / "ffmpeg" / "bin" / exe_name,
        candidate_root_1 / "ffmpeg" / exe_name,
        candidate_root_1 / exe_name,
        # App root candidates
        candidate_root_2 / exe_name,
        candidate_root_2 / "bin" / exe_name,
        candidate_root_2 / "resources" / "bin" / exe_name,
        # Dev repo candidate
        candidate_root_1 / "release" / "bin" / exe_name,
    ]

    # Python prefix siblings
    try:
        prefix = Path(sys.prefix).resolve()
        bundled_candidates.extend([
            prefix.parent / "bin" / exe_name,
            prefix.parent.parent / "bin" / exe_name,
            prefix.parent.parent / "resources" / "bin" / exe_name,
        ])
    except Exception:
        pass

    for candidate in bundled_candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue

    # In production, NEVER fall back to customer's PATH
    if is_packaged_production(env):
        logger.error(
            "Packaged production FFmpeg binary not found in bundled locations. "
            "PATH consultation is blocked in production mode."
        )
        return None

    # 4. Development fallback: consultation of PATH allowed only outside production
    found_on_path = shutil.which("ffmpeg", path=env.get("PATH"))
    if found_on_path:
        path_obj = Path(found_on_path).resolve()
        if path_obj.is_file():
            logger.debug("Resolved development FFmpeg from PATH: %s", path_obj)
            return path_obj

    return None


def require_ffmpeg_path(environ: dict[str, str] | None = None) -> Path:
    """Resolve FFmpeg or raise FileNotFoundError with actionable diagnostic message."""
    resolved = resolve_ffmpeg_path(environ)
    if resolved is None:
        if is_packaged_production(environ):
            raise FileNotFoundError(
                "BUNDLED_FFMPEG_MISSING: The bundled FFmpeg binary was not found in the Voca Basic installation. "
                "Ensure resources/bin/ffmpeg.exe is present."
            )
        raise FileNotFoundError(
            "FFMPEG_UNAVAILABLE: FFmpeg binary not found in bundled paths or system PATH. "
            "Please install FFmpeg or set LOCAL_AI_FFMPEG_PATH."
        )
    return resolved
