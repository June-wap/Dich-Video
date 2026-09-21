from __future__ import annotations

from pathlib import Path
import subprocess

from backend.config import Settings
from backend.services.capability_service import (
    ChatterboxRuntimeCapability, HardwareCapabilityService, probe_chatterbox_runtime,
)


def test_runtime_probe_uses_configured_worker_and_offline_environment(tmp_path):
    executable = tmp_path / "python.exe"; executable.touch()
    calls = []
    def runner(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args[0], 0, '{"python_version":"3.12", "torch_version":"2", "cuda_build":"12.8", "cuda_available":true, "cuda_device_count":1, "gpu_name":"GPU", "gpu_vram_total_bytes":123}')
    result = probe_chatterbox_runtime(executable, runner)
    assert result.local_available and result.gpu_name == "GPU"
    assert calls[0][0][0][:2] == [str(executable), "-c"]
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["env"]["HF_HUB_OFFLINE"] == "1"
    assert "HF_TOKEN" not in calls[0][1]["env"]


def test_runtime_probe_reports_unavailable_for_no_cuda_or_unreachable(tmp_path):
    missing = probe_chatterbox_runtime(tmp_path / "missing.exe")
    assert not missing.reachable and not missing.local_available
    executable = tmp_path / "python.exe"; executable.touch()
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, '{"python_version":"3.12", "torch_version":"2", "cuda_build":null, "cuda_available":false, "cuda_device_count":0, "gpu_name":null, "gpu_vram_total_bytes":null}')
    assert not probe_chatterbox_runtime(executable, runner).local_available


def test_snapshot_is_cached_and_provider_policy_is_explicit(tmp_path):
    executable = tmp_path / "python.exe"; executable.touch()
    calls = []
    def runtime_probe(path):
        calls.append(path)
        return ChatterboxRuntimeCapability(True, cuda_available=False, cuda_device_count=0)
    service = HardwareCapabilityService(Settings(chatterbox_python=executable), runtime_probe, lambda: 8, lambda: 32)
    first, second = service.response(), service.response()
    assert first == second and calls == [executable]
    assert first["logical_cpu_count"] == 8 and first["memory_total_bytes"] == 32
    assert first["providers"]["vieneu"] == {"local_available": True, "policy": "cpu"}
    assert first["providers"]["chatterbox"]["reason"] == "LOCAL_GPU_UNAVAILABLE"
    service.close()
    service.response()
    assert calls == [executable, executable]
