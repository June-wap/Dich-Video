"""Mock-only CP4.5 routing and isolated-worker regression coverage."""
from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend.errors import ApplicationError, ErrorCode
from backend.services.chatterbox_worker_provider import ChatterboxWorkerProvider
from backend.services.capability_service import (
    ChatterboxRuntimeCapability, HardwareCapabilitySnapshot,
)
from backend.services.provider_service import ProviderService
from backend.services import chatterbox_worker
from backend.services.tts_service import TTSService, _normalize_language


class _Provider:
    def __init__(self, provider_id, languages=()): self._id, self._languages = provider_id, languages
    def provider_name(self): return self._id
    def list_languages(self): return list(self._languages)


class _Registry:
    def __init__(self):
        self.vieneu = _Provider("vieneu", ("vi",)); self.chatterbox = _Provider("chatterbox", ("en", "ja", "fr"))
    def get_provider(self, provider_id): return getattr(self, provider_id)


@pytest.mark.parametrize("raw", ["vi", "VI", "vi-VN", "vi_VN"])
def test_vietnamese_aliases_route_only_to_vieneu(raw):
    service = object.__new__(TTSService); service._provider_service = _Registry()
    assert service._select_provider(_normalize_language(raw)).provider_name() == "vieneu"


@pytest.mark.parametrize("language", ["en", "ja", "fr"])
def test_supported_non_vietnamese_routes_only_to_chatterbox(language):
    service = object.__new__(TTSService); service._provider_service = _Registry()
    assert service._select_provider(language).provider_name() == "chatterbox"


def test_unsupported_language_is_rejected_not_fallen_back():
    service = object.__new__(TTSService); service._provider_service = _Registry()
    with pytest.raises(ApplicationError) as caught: service._select_provider("xx")
    assert caught.value.code is ErrorCode.LANGUAGE_NOT_SUPPORTED


class _Process:
    def __init__(self, response):
        self.stdin = io.StringIO(); self.stdout = io.StringIO(response + "\n"); self.stderr = io.StringIO(); self.returncode = None
        self.terminated = False
    def poll(self): return None if self.returncode is None else self.returncode
    def terminate(self): self.terminated = True; self.returncode = 0
    def wait(self, timeout=None): return 0
    def kill(self): self.returncode = -9


class _CapabilityService:
    def __init__(self, capability):
        self.calls = 0
        self._snapshot = HardwareCapabilitySnapshot(
            logical_cpu_count=8,
            physical_cpu_count=None,
            memory_total_bytes=32,
            chatterbox=capability,
        )

    def snapshot(self):
        self.calls += 1
        return self._snapshot


def test_worker_uses_configured_executable_json_lines_and_reuses_process(monkeypatch, tmp_path):
    executable = tmp_path / "python.exe"; executable.touch()
    process = _Process(json.dumps({"status":"PASS", "wav_path":"x.wav", "sample_rate":24000, "duration":1, "gen_time":.1, "provider":"chatterbox", "language":"en", "voice":"chatterbox_default"}))
    popen = Mock(return_value=process)
    monkeypatch.setattr("backend.services.chatterbox_worker_provider.subprocess.Popen", popen)
    provider = ChatterboxWorkerProvider(executable, tmp_path)
    first = provider.synthesize("one", "en", output_path=tmp_path / "one.wav")
    process.stdout = io.StringIO(json.dumps({"status":"PASS", "wav_path":"x.wav", "sample_rate":24000, "duration":1, "gen_time":.1, "provider":"chatterbox", "language":"en", "voice":"chatterbox_default"}) + "\n")
    second = provider.synthesize("two", "en", output_path=tmp_path / "two.wav")
    assert first.status == second.status == "PASS"
    popen.assert_called_once()
    args, kwargs = popen.call_args
    assert args[0] == [str(executable), "-m", "backend.services.chatterbox_worker"]
    assert kwargs["shell"] is False
    assert json.loads(process.stdin.getvalue().splitlines()[0])["action"] == "synthesize"
    provider.unload(); assert process.terminated


@pytest.mark.parametrize("error", ["LOCAL_GPU_UNAVAILABLE", "GPU_RESOURCE_INSUFFICIENT"])
def test_worker_errors_are_returned_without_provider_fallback(monkeypatch, tmp_path, error):
    executable = tmp_path / "python.exe"; executable.touch()
    process = _Process(json.dumps({"status":"FAIL", "error":error, "provider":"chatterbox"}))
    monkeypatch.setattr("backend.services.chatterbox_worker_provider.subprocess.Popen", Mock(return_value=process))
    result = ChatterboxWorkerProvider(executable, tmp_path).synthesize("hello", "en", output_path=tmp_path / "x.wav")
    assert result.status == "FAIL" and result.error == error and result.provider == "chatterbox"


def test_worker_does_not_start_when_cuda_capability_is_unavailable(monkeypatch, tmp_path):
    executable = tmp_path / "python.exe"; executable.touch()
    popen = Mock(); monkeypatch.setattr("backend.services.chatterbox_worker_provider.subprocess.Popen", popen)
    capability_service = _CapabilityService(
        ChatterboxRuntimeCapability(True, cuda_available=False, cuda_device_count=0))
    provider = ChatterboxWorkerProvider(executable, tmp_path,
        capability_service=capability_service)
    result = provider.synthesize("hello", "en", output_path=tmp_path / "x.wav")
    assert result.error == "LOCAL_GPU_UNAVAILABLE"
    assert capability_service.calls == 1
    popen.assert_not_called()


def test_registry_preserves_local_gpu_unavailable_policy_error(tmp_path):
    executable = tmp_path / "python.exe"; executable.touch()
    provider = ChatterboxWorkerProvider(executable, tmp_path,
        capability_service=_CapabilityService(ChatterboxRuntimeCapability(False)))
    registry = ProviderService(); registry.register(provider, device="cuda"); registry.select_primary("chatterbox")
    with pytest.raises(ApplicationError) as caught:
        registry.ensure_loaded("chatterbox")
    assert caught.value.code is ErrorCode.LOCAL_GPU_UNAVAILABLE


def test_worker_keeps_model_diagnostics_out_of_json_protocol(monkeypatch, tmp_path):
    diagnostics = io.StringIO()
    protocol = io.StringIO()

    class _Adapter:
        DEFAULT_VOICE_ID = "chatterbox_default"
        def __init__(self, device): assert device == "cuda"
        def synthesize(self, *args, **kwargs):
            print("model loading diagnostic")
            return SimpleNamespace(status="PASS", error=None, wav_path="x.wav", sample_rate=24000,
                                   duration=1.0, gen_time=0.1, provider="chatterbox",
                                   language="en", voice="chatterbox_default")
        def unload(self): pass

    request = json.dumps({"action": "synthesize", "text": "hello", "language": "en",
                          "output_path": str(tmp_path / "x.wav")}) + "\n"
    monkeypatch.setattr(chatterbox_worker.sys, "stdout", diagnostics)
    assert chatterbox_worker.main(adapter_factory=_Adapter, input_stream=io.StringIO(request), protocol_stdout=protocol) == 0
    response = json.loads(protocol.getvalue())
    assert response["status"] == "PASS" and "model loading diagnostic" in diagnostics.getvalue()


def test_stderr_diagnostics_do_not_corrupt_valid_worker_response(monkeypatch, tmp_path):
    executable = tmp_path / "python.exe"; executable.touch()
    response = json.dumps({"status":"PASS", "wav_path":"x.wav", "sample_rate":24000, "duration":1, "gen_time":.1, "provider":"chatterbox", "language":"en", "voice":"chatterbox_default"})
    process = _Process(response)
    process.stderr = io.StringIO("loading pinned model\nCUDA diagnostic\n")
    monkeypatch.setattr("backend.services.chatterbox_worker_provider.subprocess.Popen", Mock(return_value=process))
    result = ChatterboxWorkerProvider(executable, tmp_path).synthesize("hello", "en", output_path=tmp_path / "x.wav")
    assert result.status == "PASS" and result.provider == "chatterbox"


def test_worker_eof_is_reported_as_protocol_failure_not_json_decode_error(monkeypatch, tmp_path):
    executable = tmp_path / "python.exe"; executable.touch()
    process = _Process("")
    process.stdout = io.StringIO("")
    process.stderr = io.StringIO("worker terminated after CUDA failure\n")
    process.returncode = 17
    monkeypatch.setattr("backend.services.chatterbox_worker_provider.subprocess.Popen", Mock(return_value=process))
    result = ChatterboxWorkerProvider(executable, tmp_path).synthesize("hello", "en", output_path=tmp_path / "x.wav")
    assert result.status == "FAIL"
    assert "CHATTERBOX_WORKER_PROTOCOL_EOF exit_code=17" in result.error
    assert "JSONDecodeError" not in result.error


def test_stdout_contamination_is_explicit_protocol_failure(monkeypatch, tmp_path):
    executable = tmp_path / "python.exe"; executable.touch()
    process = _Process("model progress: 100%")
    monkeypatch.setattr("backend.services.chatterbox_worker_provider.subprocess.Popen", Mock(return_value=process))
    result = ChatterboxWorkerProvider(executable, tmp_path).synthesize("hello", "en", output_path=tmp_path / "x.wav")
    assert result.status == "FAIL"
    assert "CHATTERBOX_WORKER_PROTOCOL_INVALID_JSON" in result.error
    assert "model progress: 100%" in result.error


def test_worker_clone_request_uses_json_protocol_and_returns_clone_result(monkeypatch, tmp_path):
    executable = tmp_path / "python.exe"; executable.touch()
    response = json.dumps({"status":"PASS", "wav_path":"clone.wav", "sample_rate":24000, "duration":1, "gen_time":.1, "provider":"chatterbox", "language":"es", "voice":"chatterbox_clone"})
    process = _Process(response)
    monkeypatch.setattr("backend.services.chatterbox_worker_provider.subprocess.Popen", Mock(return_value=process))
    profile = {"reference_audio": str(tmp_path / "ref.wav")}
    result = ChatterboxWorkerProvider(executable, tmp_path).synthesize_cloned("Hola", "es", profile, tmp_path / "clone.wav")
    request = json.loads(process.stdin.getvalue())
    assert result.status == "PASS" and result.language == "es"
    assert request["action"] == "synthesize_clone" and request["profile"] == profile
