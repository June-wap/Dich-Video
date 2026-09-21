"""Unit tests for the isolated, CUDA-only Chatterbox V3 adapter.

Every Chatterbox, CUDA, Hugging Face, and audio dependency below is a fake.
These tests must remain runnable in the normal VieNeu environment, where the
real Chatterbox package and its model snapshot are deliberately absent.
"""
from __future__ import annotations

import sys
import types
import wave
import json
import hashlib
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.services.chatterbox_adapter import (
    ChatterboxAdapter,
    ChatterboxGpuResourceInsufficient,
    ChatterboxLocalGpuUnavailable,
)


class _FakeAudio:
    def detach(self):
        return self

    def cpu(self):
        return self


class _FakeRuntime:
    sr = 24_000

    def __init__(self, error: Exception | None = None):
        self.generate = Mock(side_effect=error) if error else Mock(return_value=_FakeAudio())
        self.prepare_conditionals = Mock(side_effect=self._prepare)
        self.conds = object()

    def _prepare(self, _path):
        self.conds = object()


def _write_fake_wav(
    path: str,
    _audio: _FakeAudio,
    sample_rate: int,
    *,
    format: str | None = None,
    encoding: str | None = None,
    bits_per_sample: int | None = None,
) -> None:
    """Match torchaudio.save's production keyword contract, not a loose fake."""
    assert format == "wav"
    assert encoding == "PCM_S"
    assert bits_per_sample == 16
    with wave.open(path, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(b"\x00\x00" * (sample_rate // 10))


def _install_fake_runtime(monkeypatch, tmp_path: Path, *, cuda_available=True,
                          runtime=None, load_error: Exception | None = None):
    """Install only test doubles for imports performed lazily by ``load``."""
    snapshot = Mock(return_value=str(tmp_path))
    for filename in ChatterboxAdapter._MODEL_FILES:
        path = tmp_path / filename
        if filename == "Cangjie5_TC.json":
            path.write_text(json.dumps(["你\tO"]), encoding="utf-8")
        else:
            path.touch()
    cangjie = tmp_path / "Cangjie5_TC.json"
    monkeypatch.setattr(ChatterboxAdapter, "CANGJIE_SIZE_BYTES", cangjie.stat().st_size)
    monkeypatch.setattr(ChatterboxAdapter, "CANGJIE_SHA256", hashlib.sha256(cangjie.read_bytes()).hexdigest())

    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: cuda_available)

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.snapshot_download = snapshot

    model = runtime or _FakeRuntime()
    from_local = Mock(side_effect=load_error) if load_error else Mock(return_value=model)
    fake_mtl = types.ModuleType("chatterbox.mtl_tts")
    fake_mtl.ChatterboxMultilingualTTS = types.SimpleNamespace(from_local=from_local)
    fake_chatterbox = types.ModuleType("chatterbox")
    fake_chatterbox.mtl_tts = fake_mtl
    fake_models = types.ModuleType("chatterbox.models")
    fake_tokenizers = types.ModuleType("chatterbox.models.tokenizers")
    fake_tokenizer = types.ModuleType("chatterbox.models.tokenizers.tokenizer")

    class FakeChineseCangjieConverter:
        def _load_cangjie_mapping(self, _model_dir=None):
            raise AssertionError("upstream Hub lookup should be replaced by the adapter shim")

    fake_tokenizer.ChineseCangjieConverter = FakeChineseCangjieConverter

    fake_torchaudio = types.ModuleType("torchaudio")
    fake_torchaudio.save = Mock(side_effect=_write_fake_wav)

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)
    monkeypatch.setitem(sys.modules, "chatterbox", fake_chatterbox)
    monkeypatch.setitem(sys.modules, "chatterbox.mtl_tts", fake_mtl)
    monkeypatch.setitem(sys.modules, "chatterbox.models", fake_models)
    monkeypatch.setitem(sys.modules, "chatterbox.models.tokenizers", fake_tokenizers)
    monkeypatch.setitem(sys.modules, "chatterbox.models.tokenizers.tokenizer", fake_tokenizer)
    monkeypatch.setitem(sys.modules, "torchaudio", fake_torchaudio)
    return snapshot, from_local, model, fake_torchaudio


def test_identity_and_pins_are_immutable():
    assert ChatterboxAdapter.PROVIDER_ID == "chatterbox"
    assert ChatterboxAdapter.SOURCE_REVISION == "5de7a54aa4e5e2baadb0182dde554908b48b85c2"
    assert ChatterboxAdapter.MODEL_REVISION == "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
    assert ChatterboxAdapter.T3_MODEL == "v3"
    assert ChatterboxAdapter.T3_CHECKPOINT == "t3_mtl23ls_v3.safetensors"


def test_construction_is_lazy_and_requires_no_optional_runtime(monkeypatch):
    real_import = __import__

    def forbid_optional_runtime(name, *args, **kwargs):
        if name.split(".")[0] in {"chatterbox", "huggingface_hub", "torch", "torchaudio"}:
            raise AssertionError(f"unexpected eager import: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", forbid_optional_runtime)
    adapter = ChatterboxAdapter()
    assert adapter.provider_id == "chatterbox"
    assert adapter.is_loaded() is False


@pytest.mark.parametrize("language", ["vi", "VI", "vi-VN", "vi_VN"])
def test_vietnamese_is_reserved_for_vieneu(language):
    result = ChatterboxAdapter().synthesize("Xin chào", language, output_path="ignored.wav")
    assert result.status == "FAIL"
    assert result.error == "VIETNAMESE_OWNED_BY_VIENEU"


def test_supported_non_vietnamese_language_is_exposed():
    voices = ChatterboxAdapter().list_voices("en")
    assert len(voices) == 1
    assert voices[0].provider == "chatterbox"
    assert voices[0].language == "en"
    assert ChatterboxAdapter().list_voices("ja")[0].language == "ja"


def test_invalid_language_is_rejected_without_loading():
    result = ChatterboxAdapter().synthesize("Hello", "xx", output_path="ignored.wav")
    assert result.status == "FAIL"
    assert result.error == "LANGUAGE_NOT_SUPPORTED"


def test_cuda_unavailable_is_explicit_and_never_falls_back(monkeypatch, tmp_path):
    snapshot, from_local, _, _ = _install_fake_runtime(monkeypatch, tmp_path, cuda_available=False)
    adapter = ChatterboxAdapter()

    with pytest.raises(ChatterboxLocalGpuUnavailable, match="LOCAL_GPU_UNAVAILABLE"):
        adapter.load()
    assert snapshot.call_count == 0
    assert from_local.call_count == 0

    result = adapter.synthesize("Hello", "en", output_path=tmp_path / "out.wav")
    assert result.error == "LOCAL_GPU_UNAVAILABLE"
    assert result.device == "cuda"


def test_load_downloads_exact_immutable_snapshot_and_explicitly_selects_v3(monkeypatch, tmp_path):
    snapshot, from_local, _, _ = _install_fake_runtime(monkeypatch, tmp_path)
    adapter = ChatterboxAdapter()

    assert adapter.load() is adapter
    snapshot.assert_called_once_with(
        repo_id="ResembleAI/chatterbox",
        repo_type="model",
        revision="5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18",
        allow_patterns=list(ChatterboxAdapter._MODEL_FILES),
        local_files_only=False,
    )
    from_local.assert_called_once_with(tmp_path, device="cuda", t3_model="v3")


def test_offline_load_explicitly_forbids_snapshot_network_access(monkeypatch, tmp_path):
    snapshot, _, _, _ = _install_fake_runtime(monkeypatch, tmp_path)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    ChatterboxAdapter().load()

    assert snapshot.call_args.kwargs["local_files_only"] is True


def test_synthesis_loads_once_reuses_model_and_writes_native_wav(monkeypatch, tmp_path):
    snapshot, from_local, runtime, torchaudio = _install_fake_runtime(monkeypatch, tmp_path)
    adapter = ChatterboxAdapter()
    first = adapter.synthesize("Hello from Chatterbox.", "en", output_path=tmp_path / "one.wav")
    second = adapter.synthesize("Bonjour.", "fr", output_path=tmp_path / "two.wav")

    assert first.status == second.status == "PASS"
    assert first.provider == "chatterbox"
    assert first.language == "en"
    assert second.language == "fr"
    assert first.sample_rate == 24_000
    assert first.duration > 0
    assert Path(first.wav_path).is_file()
    assert snapshot.call_count == 1
    assert from_local.call_count == 1
    assert runtime.generate.call_count == 2
    assert torchaudio.save.call_count == 2
    _, save_kwargs = torchaudio.save.call_args
    assert save_kwargs == {
        "format": "wav",
        "encoding": "PCM_S",
        "bits_per_sample": 16,
    }


def test_cuda_oom_during_load_maps_to_explicit_resource_error(monkeypatch, tmp_path):
    snapshot, from_local, _, _ = _install_fake_runtime(
        monkeypatch, tmp_path, load_error=RuntimeError("CUDA out of memory"))
    adapter = ChatterboxAdapter()

    with pytest.raises(ChatterboxGpuResourceInsufficient, match="GPU_RESOURCE_INSUFFICIENT"):
        adapter.load()
    assert snapshot.call_count == 1
    assert from_local.call_count == 1
    result = adapter.synthesize("Hello", "en", output_path=tmp_path / "out.wav")
    assert result.error == "GPU_RESOURCE_INSUFFICIENT"


def test_cuda_oom_during_generation_maps_to_explicit_resource_error(monkeypatch, tmp_path):
    runtime = _FakeRuntime(error=RuntimeError("CUDA out of memory"))
    _install_fake_runtime(monkeypatch, tmp_path, runtime=runtime)
    result = ChatterboxAdapter().synthesize("Hello", "en", output_path=tmp_path / "out.wav")
    assert result.status == "FAIL"
    assert result.error == "GPU_RESOURCE_INSUFFICIENT"


def test_synthesis_holds_the_adapter_lock_without_timing(monkeypatch, tmp_path):
    _install_fake_runtime(monkeypatch, tmp_path)
    adapter = ChatterboxAdapter()

    class RecordingLock:
        entries = 0

        def __enter__(self):
            self.entries += 1
            return self

        def __exit__(self, *_):
            return False

    lock = RecordingLock()
    adapter._lock = lock
    result = adapter.synthesize("Hello", "en", output_path=tmp_path / "out.wav")

    assert result.status == "PASS"
    # One entry for synthesis and one nested entry for lazy load.
    assert lock.entries == 2


def test_clone_conditions_are_cached_and_reused_across_supported_languages(monkeypatch, tmp_path):
    _, _, runtime, _ = _install_fake_runtime(monkeypatch, tmp_path)
    reference = tmp_path / "reference.wav"; reference.write_bytes(b"reference")
    adapter = ChatterboxAdapter()
    profile = adapter.create_voice_profile(reference)
    english = adapter.synthesize_cloned("Hello", "en", profile, tmp_path / "en.wav")
    spanish = adapter.synthesize_cloned("Hola", "es", profile, tmp_path / "es.wav")
    assert english.status == spanish.status == "PASS"
    assert english.language == "en" and spanish.language == "es"
    assert runtime.prepare_conditionals.call_count == 1
    assert english.metadata["cloned"] is True


def test_clone_rejects_vietnamese_without_loading(monkeypatch, tmp_path):
    reference = tmp_path / "reference.wav"; reference.write_bytes(b"reference")
    result = ChatterboxAdapter().synthesize_cloned("Xin chào", "vi", {"reference_audio": str(reference)}, tmp_path / "out.wav")
    assert result.status == "FAIL" and result.error == "VIETNAMESE_OWNED_BY_VIENEU"


def test_cuda_oom_during_clone_generation_maps_to_explicit_resource_error(monkeypatch, tmp_path):
    runtime = _FakeRuntime(error=RuntimeError("CUDA out of memory"))
    _install_fake_runtime(monkeypatch, tmp_path, runtime=runtime)
    reference = tmp_path / "reference.wav"; reference.write_bytes(b"reference")
    result = ChatterboxAdapter().synthesize_cloned(
        "Hello", "en", {"reference_audio": str(reference)}, tmp_path / "out.wav")
    assert result.status == "FAIL"
    assert result.error == "GPU_RESOURCE_INSUFFICIENT"
