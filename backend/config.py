"""Central local-backend settings, optionally overridden by LOCAL_AI_* env vars."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
from backend.core.app_paths import resolve_app_paths

def _default_app_data_dir() -> Path:
    """Per-user writable location for both installed and developer builds.

    An installed Electron host supplies LOCAL_AI_APP_DATA_DIR.  The fallback
    deliberately uses LOCALAPPDATA on Windows instead of the source checkout,
    so generated speech, private reference audio, SQLite and session tokens
    never become application files or installer payloads.
    """
    return resolve_app_paths().root


DEFAULT_APP_DATA_DIR = _default_app_data_dir()
DEFAULT_OUTPUT_DIR = resolve_app_paths().audio_dir
DEFAULT_TOKEN_PATH = resolve_app_paths().token_path
# "1 tiến trình, 1 cổng" (mục tiêu đóng gói 17/09 - xem
# checklist-dong-goi-ban-short.md): thư mục `npm run build` của frontend mà
# backend tự phục vụ khi Settings.serve_frontend bật, thay vì bắt chạy
# `npm run dev` ở một cổng riêng. Không tồn tại cho tới khi ai đó thật sự
# chạy build - xem Settings.serve_frontend/backend/main.py's catch-all route.
DEFAULT_FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _portable_chatterbox_python() -> Path | None:
    """Resolve the staged sibling worker without consulting cwd or source paths."""
    prefix = Path(sys.prefix).resolve()
    executable = Path(sys.executable).resolve()
    if (prefix.name.lower() != "runtime-main"
            or executable.parent != prefix
            or executable.name.lower() != "python.exe"):
        return None

    candidate = prefix.parent / "runtime-chatterbox" / "python.exe"
    if not candidate.is_file():
        raise RuntimeError(f"PORTABLE_CHATTERBOX_RUNTIME_MISSING: {candidate}")
    return candidate


def resolve_chatterbox_python() -> Path:
    """Select an explicit development worker or the staged sibling worker.

    Source checkouts must receive ``LOCAL_AI_CHATTERBOX_PYTHON`` from their
    stable desktop/runtime resolver.  Falling back to a checkout-local venv
    would make a release silently depend on a developer machine.
    """
    configured = os.getenv("LOCAL_AI_CHATTERBOX_PYTHON", "").strip()
    if configured:
        candidate = Path(configured)
        if not candidate.is_file():
            raise RuntimeError(f"CHATTERBOX_RUNTIME_UNAVAILABLE: {candidate}")
        return candidate

    portable = _portable_chatterbox_python()
    if portable is not None:
        return portable
    raise RuntimeError(
        "CHATTERBOX_RUNTIME_UNAVAILABLE: set LOCAL_AI_CHATTERBOX_PYTHON "
        "or run from a staged runtime-main sibling layout"
    )


@dataclass(frozen=True)
class Settings:
    app_name: str = "Voca Basic"
    app_version: str = "0.3.0-dev"
    api_prefix: str = "/api"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "::1")
    log_level: str = "INFO"
    # CP1 intentionally has no active TTS provider. CP2 installs the router.
    primary_tts_provider: str | None = None
    app_data_dir: Path = DEFAULT_APP_DATA_DIR
    output_dir: Path = DEFAULT_OUTPUT_DIR
    database_path: Path | None = None
    reference_audio_dir: Path | None = None
    temp_dir: Path | None = None
    # Security P0: require every request (other than the one bootstrap
    # exception, GET /api/auth/token) to present the local session token -
    # see backend/main.py's lifespan/request_boundary and backend/api/auth.py.
    # Defaults to False here specifically so every test file that builds
    # Settings(...) directly, or calls Settings.from_env() without setting
    # LOCAL_AI_REQUIRE_LOCAL_TOKEN (most of backend/tests/*.py do exactly
    # that - e.g. test_backend.py's `harness` fixture calls create_app() with
    # no settings at all, which falls back to from_env()), keeps working
    # completely unchanged. scripts/run_backend.ps1 - the only real launcher -
    # is what turns this on for every actual run of the product; tests that
    # want to exercise the auth layer itself opt in explicitly (see
    # backend/tests/test_local_auth.py).
    require_local_token: bool = False
    token_path: Path = DEFAULT_TOKEN_PATH
    # When True, backend/main.py's lifespan kicks
    # off a background thread per available provider right at startup that
    # calls ProviderService.ensure_loaded() - so by the time a customer has
    # opened the app and typed their first request, the model is usually
    # already loaded. Never blocks startup or the health endpoint (runs in a
    # daemon thread, not inside lifespan's own execution), and a failed
    # warm-up (e.g. CUDA unavailable) is only logged - the first real
    # request still falls back to today's on-demand ensure_loaded() exactly
    # as before. Defaults to False for the same reason as
    # require_local_token above: several tests construct Settings()/call
    # Settings.from_env() with no real TTS runtime available
    # (e.g. test_backend.py's subprocess test that forbids importing them
    # entirely at startup) and must not race a background warm-up attempt.
    # scripts/run_backend.ps1 is what turns this on for every real run.
    warm_up_on_start: bool = False
    # "1 tiến trình, 1 cổng" (mục tiêu đóng gói 17/09): khi True,
    # backend/main.py mounts a catch-all route that serves
    # frontend_dist_dir (a real `npm run build` output) for every path
    # request.url.path doesn't already route to under api_prefix, with an
    # SPA fallback to its index.html for client-side (React Router) routes -
    # so a customer opens ONE URL (the backend's own origin) instead of
    # running two separate dev servers on two ports. Defaults to False for
    # the same reason as require_local_token/warm_up_on_start above: it must
    # never depend on whether frontend/dist happens to exist on whoever's
    # machine runs the test suite (it does, right now, in this repo's own
    # checkout) - only scripts/run_backend.ps1 turns this on for a real run,
    # after making sure frontend/dist actually exists (building it first if
    # missing). When True but frontend_dist_dir still doesn't exist (e.g. the
    # env var was set without ever building), backend/main.py logs a warning
    # and skips mounting the route rather than crashing - the API itself
    # keeps working either way.
    serve_frontend: bool = False
    frontend_dist_dir: Path = DEFAULT_FRONTEND_DIST_DIR
    # Isolated CP4.5 Chatterbox runtime; never install its dependencies into
    # the VieNeu/backend environment.
    chatterbox_python: Path = field(default_factory=resolve_chatterbox_python)
    # Cloud License V2 settings
    cloud_license_url: str | None = None
    cloud_license_public_key_hex: str | None = None
    offline_lease_grace_days: int = 7

    def __post_init__(self):
        if not self.api_prefix.startswith("/") or self.api_prefix.endswith("/"):
            raise ValueError("API prefix must start with / and have no trailing /")
        # Security P0 (checklist-bao-mat-truoc-dong-goi-17-09.md muc 3 -
        # "khoa cung loopback"): this app must never be reachable from the
        # network, on principle - not just "by default". Settings.from_env()
        # reads LOCAL_AI_HOST straight from the environment with no
        # validation of its own, so a stray or malicious
        # LOCAL_AI_HOST=0.0.0.0 (or any LAN/public address) must fail loudly
        # here instead of silently binding uvicorn to every interface.
        # Deliberately no escape hatch: a developer who genuinely needs LAN
        # access for a one-off test should put a reverse proxy/tunnel in
        # front of a loopback-bound instance, not widen this check.
        if self.host not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError(
                "Backend host must be a loopback address (localhost, 127.0.0.1 or ::1) "
                "- this app must never bind to the network"
            )
        if not 1 <= self.port <= 65535:
            raise ValueError("Invalid backend port")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("Invalid log level")
        for origin in self.cors_origins:
            url = urlsplit(origin)
            if (url.scheme not in {"http", "https"}
                    or url.hostname not in {"localhost", "127.0.0.1", "::1"}
                    or url.username is not None or url.password is not None
                    or url.path or url.query or url.fragment):
                raise ValueError("CORS origins must be explicit loopback origins")
            _ = url.port  # Reject malformed ports too.

    @classmethod
    def from_env(cls):
        defaults = cls()
        paths = resolve_app_paths()
        return cls(
            app_name=os.getenv("LOCAL_AI_APP_NAME", defaults.app_name),
            app_version=os.getenv("LOCAL_AI_APP_VERSION", defaults.app_version),
            api_prefix=os.getenv("LOCAL_AI_API_PREFIX", defaults.api_prefix),
            host=os.getenv("LOCAL_AI_HOST", defaults.host),
            port=int(os.getenv("LOCAL_AI_PORT", str(defaults.port))),
            cors_origins=tuple(value.strip() for value in os.getenv(
                "LOCAL_AI_CORS_ORIGINS", ",".join(defaults.cors_origins)
            ).split(",") if value.strip()),
            log_level=os.getenv("LOCAL_AI_LOG_LEVEL", defaults.log_level).upper(),
            app_data_dir=paths.root,
            output_dir=Path(os.getenv("LOCAL_AI_OUTPUT_DIR", str(defaults.output_dir))),
            database_path=Path(os.environ['LOCAL_AI_DATABASE_PATH']) if os.getenv('LOCAL_AI_DATABASE_PATH') else None,
            reference_audio_dir=Path(os.environ['LOCAL_AI_REFERENCE_AUDIO_DIR']) if os.getenv('LOCAL_AI_REFERENCE_AUDIO_DIR') else paths.reference_audio_dir,
            temp_dir=Path(os.environ['LOCAL_AI_TEMP_DIR']) if os.getenv('LOCAL_AI_TEMP_DIR') else paths.temp_dir,
            require_local_token=os.getenv("LOCAL_AI_REQUIRE_LOCAL_TOKEN", "").strip().lower() in {"1", "true", "yes"},
            token_path=Path(os.getenv("LOCAL_AI_TOKEN_PATH", str(defaults.token_path))),
            warm_up_on_start=os.getenv("LOCAL_AI_WARM_UP_ON_START", "").strip().lower() in {"1", "true", "yes"},
            serve_frontend=os.getenv("LOCAL_AI_SERVE_FRONTEND", "").strip().lower() in {"1", "true", "yes"},
            frontend_dist_dir=Path(os.getenv("LOCAL_AI_FRONTEND_DIST_DIR", str(defaults.frontend_dist_dir))),
            chatterbox_python=resolve_chatterbox_python(),
            cloud_license_url=os.getenv("LOCAL_AI_CLOUD_LICENSE_URL", defaults.cloud_license_url),
            cloud_license_public_key_hex=os.getenv("LOCAL_AI_CLOUD_LICENSE_PUBLIC_KEY_HEX", defaults.cloud_license_public_key_hex),
            offline_lease_grace_days=int(os.getenv("LOCAL_AI_OFFLINE_LEASE_GRACE_DAYS", str(defaults.offline_lease_grace_days))),
        )
