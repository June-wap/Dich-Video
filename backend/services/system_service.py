"""Cache hardware metadata only; lifecycle state comes live from ProviderService."""
from dataclasses import dataclass, asdict
import logging
import platform
from threading import Lock
from typing import Callable

from backend.schemas.system import SystemStatus
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
    # CUDA is owned by capability_service's isolated Chatterbox-runtime
    # probe.  This lightweight status endpoint must not import Torch from the
    # CPU/main runtime and accidentally report that as worker capability.
    return RuntimeInfo(platform.python_version(), None, False, None)


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
        primary = statuses.get(registry.primary) if registry.primary else None
        # The primary provider is CPU VieNeu.  Its readiness is independent
        # of Chatterbox's CUDA-only capability policy.
        ready = bool(primary and primary.available
                     and primary.state not in {ProviderState.ERROR, ProviderState.UNAVAILABLE})
        return SystemStatus(
            **asdict(runtime), status="ready" if ready else "degraded",
            primary_provider=registry.primary, provider_state=primary.state if primary else None,
        )

    def close(self) -> None:
        with self._lock:
            self._snapshot = None
