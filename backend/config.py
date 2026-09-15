"""Central local-backend settings, optionally overridden by LOCAL_AI_* env vars."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

OMNIVOICE_PROVIDER_ID = "omnivoice"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "prototype" / "outputs" / "api"


@dataclass(frozen=True)
class Settings:
    app_name: str = "Local AI Voice API"
    app_version: str = "0.3.0-dev"
    api_prefix: str = "/api"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1", "::1")
    log_level: str = "INFO"
    primary_tts_provider: str = OMNIVOICE_PROVIDER_ID
    omnivoice_device: str = "cuda:0"
    output_dir: Path = DEFAULT_OUTPUT_DIR
    database_path: Path | None = None

    def __post_init__(self):
        if not re.fullmatch(r"cuda:\d+", self.omnivoice_device):
            raise ValueError("OmniVoice backend requires an explicit CUDA device; no CPU fallback")
        if not self.primary_tts_provider:
            raise ValueError("Primary TTS provider is required")
        if not self.api_prefix.startswith("/") or self.api_prefix.endswith("/"):
            raise ValueError("API prefix must start with / and have no trailing /")
        if not self.host or not 1 <= self.port <= 65535:
            raise ValueError("Invalid backend host/port")
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
            primary_tts_provider=os.getenv("LOCAL_AI_PRIMARY_TTS_PROVIDER", defaults.primary_tts_provider),
            omnivoice_device=os.getenv("LOCAL_AI_OMNIVOICE_DEVICE", defaults.omnivoice_device),
            output_dir=Path(os.getenv("LOCAL_AI_OUTPUT_DIR", str(defaults.output_dir))),
            database_path=Path(os.environ['LOCAL_AI_DATABASE_PATH']) if os.getenv('LOCAL_AI_DATABASE_PATH') else None,
        )
