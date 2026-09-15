"""Cache hardware metadata only; lifecycle state comes live from ProviderService."""
from dataclasses import dataclass, asdict
import importlib
import logging
import platform
from threading import Lock
from typing import Callable

from backend.schemas.system import SystemStatus
from backend.config import OMNIVOICE_PROVIDER_ID
from backend.schemas.providers import ProviderState
from backend.services.provider_service import ProviderService

logger = logging.getLogger("backend.system")


@dataclass(frozen=True)
class RuntimeInfo:
    python_version: str
    torch_version: str | None
    cuda_available: bool
    gpu_name: str | None


def probe_runtime() -> RuntimeInfo:
    torch_version = None
    cuda_available = False
    gpu_name = None
    try:
        torch = importlib.import_module("torch")
        torch_version = torch.__version__
        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            gpu_name = torch.cuda.get_device_name(0)
    except Exception:
        cuda_available = False
        logger.exception("runtime_probe_failed component=torch")
    return RuntimeInfo(platform.python_version(), torch_version, cuda_available, gpu_name)


class SystemService:
    def __init__(self, providers: ProviderService, probe: Callable[[], RuntimeInfo] = probe_runtime):
        self._providers = providers
        self._probe = probe
        self._snapshot: RuntimeInfo | None = None
        self._lock = Lock()

    def status(self) -> SystemStatus:
        with self._lock:
            if self._snapshot is None:
                self._snapshot = self._probe()
            runtime = self._snapshot
        registry = self._providers.status()
        statuses = {provider.id: provider for provider in registry.providers}
        primary = statuses[registry.primary]
        omni = statuses.get(OMNIVOICE_PROVIDER_ID)
        ready = (runtime.torch_version and runtime.cuda_available and primary.available
                 and primary.state not in {ProviderState.ERROR, ProviderState.UNAVAILABLE})
        return SystemStatus(
            **asdict(runtime), status="ready" if ready else "degraded",
            omnivoice_available=bool(omni and omni.available),
            omnivoice_model_loaded=bool(omni and omni.loaded),
            primary_provider=registry.primary, provider_state=primary.state,
        )

    def close(self) -> None:
        with self._lock:
            self._snapshot = None
