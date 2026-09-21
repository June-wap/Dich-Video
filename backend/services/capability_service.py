"""Authoritative, cached local-machine capability detection for CP8.4.

CUDA is deliberately queried with the *Chatterbox* interpreter.  The main
runtime is CPU-oriented and must never be used to infer worker CUDA support.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import ctypes
import json
import logging
import os
from pathlib import Path
import subprocess
from threading import Lock
import time
from typing import Callable

from backend.config import Settings


logger = logging.getLogger("backend.capabilities")


@dataclass(frozen=True)
class ChatterboxRuntimeCapability:
    reachable: bool
    python_version: str | None = None
    torch_version: str | None = None
    cuda_build: str | None = None
    cuda_available: bool = False
    cuda_device_count: int = 0
    gpu_name: str | None = None
    gpu_vram_total_bytes: int | None = None
    reason: str | None = None

    @property
    def local_available(self) -> bool:
        return self.reachable and self.cuda_available and self.cuda_device_count > 0


@dataclass(frozen=True)
class HardwareCapabilitySnapshot:
    logical_cpu_count: int | None
    physical_cpu_count: int | None
    memory_total_bytes: int | None
    chatterbox: ChatterboxRuntimeCapability


_PROBE_CODE = """import json, platform
try:
 import torch
 available = bool(torch.cuda.is_available())
 count = int(torch.cuda.device_count()) if available else 0
 properties = torch.cuda.get_device_properties(0) if count else None
 print(json.dumps({'python_version': platform.python_version(), 'torch_version': torch.__version__, 'cuda_build': torch.version.cuda, 'cuda_available': available, 'cuda_device_count': count, 'gpu_name': torch.cuda.get_device_name(0) if count else None, 'gpu_vram_total_bytes': int(properties.total_memory) if properties else None}))
except Exception as exc:
 print(json.dumps({'error': type(exc).__name__ + ': ' + str(exc)}))
"""


def probe_chatterbox_runtime(python: Path, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> ChatterboxRuntimeCapability:
    """Run a narrow offline Torch probe in the configured Chatterbox runtime."""
    started = time.monotonic()
    runtime = str(python)
    if not python.is_file():
        logger.warning("capability_probe runtime=%s duration_ms=0 reason=runtime_unavailable", runtime)
        return ChatterboxRuntimeCapability(False, reason="CHATTERBOX_RUNTIME_UNAVAILABLE")
    environment = os.environ.copy()
    environment.pop("HF_TOKEN", None)
    environment["HF_HUB_OFFLINE"] = "1"
    environment["TRANSFORMERS_OFFLINE"] = "1"
    try:
        result = runner([runtime, "-c", _PROBE_CODE], capture_output=True, text=True,
                        timeout=60, shell=False, env=environment)
        duration_ms = int((time.monotonic() - started) * 1000)
        if result.returncode != 0:
            logger.warning("capability_probe runtime=%s duration_ms=%s return_code=%s reason=probe_failed", runtime, duration_ms, result.returncode)
            return ChatterboxRuntimeCapability(False, reason="CHATTERBOX_RUNTIME_PROBE_FAILED")
        data = json.loads(result.stdout.strip())
        if data.get("error"):
            logger.warning("capability_probe runtime=%s duration_ms=%s return_code=0 reason=probe_error error_type=%s", runtime, duration_ms, type(data["error"]).__name__)
            return ChatterboxRuntimeCapability(False, reason="CHATTERBOX_RUNTIME_PROBE_FAILED")
        capability = ChatterboxRuntimeCapability(True, **data)
        logger.info("capability_probe runtime=%s duration_ms=%s return_code=0 torch=%s cuda_build=%s cuda_available=%s device_count=%s gpu=%s", runtime, duration_ms, capability.torch_version, capability.cuda_build, capability.cuda_available, capability.cuda_device_count, capability.gpu_name)
        return capability
    except subprocess.TimeoutExpired:
        logger.warning("capability_probe runtime=%s duration_ms=%s reason=timeout timeout_seconds=60", runtime, int((time.monotonic() - started) * 1000))
        return ChatterboxRuntimeCapability(False, reason="CHATTERBOX_RUNTIME_PROBE_TIMEOUT")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        logger.warning("capability_probe runtime=%s duration_ms=%s reason=probe_failed error_type=%s", runtime, int((time.monotonic() - started) * 1000), type(exc).__name__)
        return ChatterboxRuntimeCapability(False, reason="CHATTERBOX_RUNTIME_PROBE_FAILED")


def _memory_total_bytes() -> int | None:
    if os.name == "nt":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = MEMORYSTATUSEX(); status.dwLength = ctypes.sizeof(status)
        return int(status.ullTotalPhys) if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) else None
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, ValueError):
        return None


class HardwareCapabilityService:
    """One app-scoped snapshot; constructor injection keeps all probes testable."""
    def __init__(self, settings: Settings, runtime_probe: Callable[[Path], ChatterboxRuntimeCapability] = probe_chatterbox_runtime,
                 cpu_probe: Callable[[], int | None] = os.cpu_count,
                 memory_probe: Callable[[], int | None] = _memory_total_bytes):
        self._settings, self._runtime_probe = settings, runtime_probe
        self._cpu_probe, self._memory_probe = cpu_probe, memory_probe
        self._snapshot: HardwareCapabilitySnapshot | None = None
        self._lock = Lock()

    def snapshot(self) -> HardwareCapabilitySnapshot:
        with self._lock:
            if self._snapshot is None:
                self._snapshot = HardwareCapabilitySnapshot(
                    logical_cpu_count=self._cpu_probe(), physical_cpu_count=None,
                    memory_total_bytes=self._memory_probe(),
                    chatterbox=self._runtime_probe(self._settings.chatterbox_python),
                )
            return self._snapshot

    def response(self) -> dict:
        snapshot = self.snapshot()
        data = asdict(snapshot)
        chatterbox = data["chatterbox"]
        chatterbox["local_available"] = snapshot.chatterbox.local_available
        chatterbox["policy"] = "cuda_required"
        data["providers"] = {
            "vieneu": {"local_available": True, "policy": "cpu"},
            "chatterbox": {"local_available": snapshot.chatterbox.local_available,
                            "policy": "cuda_required",
                            "reason": None if snapshot.chatterbox.local_available else "LOCAL_GPU_UNAVAILABLE"},
        }
        return data

    def close(self) -> None:
        with self._lock:
            self._snapshot = None
