"""Real CUDA gate for the pinned CP4 Chatterbox production adapter.

Run from the repository root with ``.venv-chatterbox``.  This intentionally
uses only ChatterboxAdapter's public lifecycle and synthesis methods; it does
not import or invoke the upstream Chatterbox runtime directly.
"""
from __future__ import annotations

import sys
import time
import wave
from pathlib import Path

import torch

from backend.services.chatterbox_adapter import ChatterboxAdapter


TEXT = "This is a real Chatterbox Multilingual V3 synthesis test."
LANGUAGE = "en"
OUTPUT_PATH = Path(".runtime") / "cp4_chatterbox_adapter_en.wav"


def _gb(value: int) -> float:
    return round(value / (1024 ** 3), 3)


def _sync() -> None:
    torch.cuda.synchronize()


def _fail(message: str) -> int:
    print(f"CP4 PRODUCTION ADAPTER REAL GATE FAIL: {message}")
    return 1


def main() -> int:
    print("=== CP4 PRODUCTION ADAPTER REAL GATE ===")
    if not torch.cuda.is_available():
        return _fail("LOCAL_GPU_UNAVAILABLE")

    device = "cuda"
    properties = torch.cuda.get_device_properties(0)
    free_before, total_before = torch.cuda.mem_get_info(0)
    adapter = ChatterboxAdapter(device=device)

    print(f"provider: {adapter.provider_id}")
    print(f"source_revision: {adapter.SOURCE_REVISION}")
    print(f"model_revision: {adapter.MODEL_REVISION}")
    print(f"t3_model: {adapter.T3_MODEL}")
    print(f"t3_checkpoint: {adapter.T3_CHECKPOINT}")
    print(f"torch_version: {torch.__version__}")
    print(f"cuda_runtime: {torch.version.cuda}")
    print("cuda_available: True")
    print(f"gpu_name: {properties.name}")
    print(f"total_vram_gb: {_gb(total_before)}")
    print(f"free_vram_before_load_gb: {_gb(free_before)}")

    # Fail closed if the adapter identity ever drifts.  These checks prove V3
    # selection from its pinned production configuration, not its filename.
    if adapter.T3_MODEL != "v3":
        return _fail("adapter did not select Chatterbox V3")
    if adapter.T3_CHECKPOINT != "t3_mtl23ls_v3.safetensors":
        return _fail("adapter V3 checkpoint identity mismatch")
    if adapter.MODEL_REVISION == "main":
        return _fail("mutable model revision is forbidden")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.unlink(missing_ok=True)

    try:
        torch.cuda.reset_peak_memory_stats(0)
        load_started = time.perf_counter()
        adapter.load()
        _sync()
        load_seconds = time.perf_counter() - load_started
        load_peak_allocated = torch.cuda.max_memory_allocated(0)
        load_peak_reserved = torch.cuda.max_memory_reserved(0)

        # Reset after loading so these are synthesis peaks above the loaded
        # model baseline; load peaks are reported separately above.
        torch.cuda.reset_peak_memory_stats(0)
        synth_started = time.perf_counter()
        result = adapter.synthesize(TEXT, LANGUAGE, output_path=OUTPUT_PATH)
        _sync()
        synthesis_seconds = time.perf_counter() - synth_started
        synth_peak_allocated = torch.cuda.max_memory_allocated(0)
        synth_peak_reserved = torch.cuda.max_memory_reserved(0)
    except Exception as exc:
        return _fail(f"adapter exception: {exc}")

    if result.status != "PASS":
        return _fail(f"adapter synthesis: {result.error}")
    if result.provider != "chatterbox" or result.language != LANGUAGE:
        return _fail("adapter result identity mismatch")
    if not OUTPUT_PATH.is_file() or OUTPUT_PATH.stat().st_size <= 44:
        return _fail("missing or invalid WAV output")

    try:
        with wave.open(str(OUTPUT_PATH), "rb") as audio:
            channels = audio.getnchannels()
            sample_rate = audio.getframerate()
            frames = audio.getnframes()
        duration = frames / sample_rate if sample_rate else 0.0
    except (OSError, wave.Error) as exc:
        return _fail(f"WAV validation: {exc}")

    if channels != 1:
        return _fail(f"expected mono WAV, got {channels} channels")
    if sample_rate != result.sample_rate:
        return _fail("WAV sample rate differs from adapter result")
    if duration <= 0:
        return _fail("WAV duration is not positive")

    print(f"provider: {result.provider}")
    print(f"language: {result.language}")
    print(f"device: {adapter.device}")
    print(f"model_load_seconds: {load_seconds:.3f}")
    print(f"synthesis_seconds: {synthesis_seconds:.3f}")
    print(f"load_peak_allocated_gb: {_gb(load_peak_allocated)}")
    print(f"load_peak_reserved_gb: {_gb(load_peak_reserved)}")
    print(f"synthesis_peak_allocated_gb: {_gb(synth_peak_allocated)}")
    print(f"synthesis_peak_reserved_gb: {_gb(synth_peak_reserved)}")
    print(f"sample_rate: {sample_rate}")
    print(f"channels: {channels}")
    print(f"duration_seconds: {duration:.3f}")
    print(f"file_size: {OUTPUT_PATH.stat().st_size}")
    print(f"output: {OUTPUT_PATH.resolve()}")
    print("CP4 PRODUCTION ADAPTER REAL GATE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
