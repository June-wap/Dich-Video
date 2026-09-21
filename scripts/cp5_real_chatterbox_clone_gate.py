"""Manual CUDA gate for pinned Chatterbox V3 same/cross-language cloning."""
from __future__ import annotations

import argparse
from pathlib import Path
import time
import wave

from backend.services.chatterbox_adapter import ChatterboxAdapter


def validate(path: Path) -> tuple[int, int, float]:
    if not path.is_file() or path.stat().st_size <= 44:
        raise RuntimeError(f"Invalid output: {path}")
    with wave.open(str(path), "rb") as wav:
        channels, rate, frames = wav.getnchannels(), wav.getframerate(), wav.getnframes()
    duration = frames / rate if rate else 0.0
    if channels != 1 or rate <= 0 or duration <= 0:
        raise RuntimeError(f"Invalid WAV properties: channels={channels} rate={rate} duration={duration}")
    return channels, rate, duration


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_wav", type=Path, help="Real English reference WAV (3–60 seconds)")
    args = parser.parse_args()
    reference = args.reference_wav.resolve()
    if not reference.is_file():
        raise SystemExit(f"Reference WAV not found: {reference}")

    import torch
    if not torch.cuda.is_available():
        raise SystemExit("CP5 GATE FAIL: CUDA is unavailable; CPU fallback is forbidden.")

    output_dir = Path(".runtime")
    output_dir.mkdir(exist_ok=True)
    adapter = ChatterboxAdapter(device="cuda")
    print("=== CP5 CHATTERBOX V3 CLONE REAL GATE ===")
    print(f"provider: {adapter.provider_id}")
    print(f"source_revision: {adapter.SOURCE_REVISION}")
    print(f"model_revision: {adapter.MODEL_REVISION}")
    print(f"t3_model: {adapter.T3_MODEL}")
    print(f"checkpoint: {adapter.T3_CHECKPOINT}")
    print(f"gpu: {torch.cuda.get_device_name(0)}")
    print(f"reference: {reference}")

    profile = adapter.create_voice_profile(reference)
    cases = (("en", "This is a same-language Chatterbox voice cloning test."),
             ("es", "Esta es una prueba de clonación de voz en español."),
             ("ja", "これは日本語での音声クローニングテストです。"))
    try:
        for language, text in cases:
            target = output_dir / f"cp5_chatterbox_clone_{language}.wav"
            torch.cuda.reset_peak_memory_stats()
            started = time.perf_counter()
            result = adapter.synthesize_cloned(text, language, profile, target)
            elapsed = time.perf_counter() - started
            if result.status != "PASS" or result.provider != "chatterbox" or result.language != language:
                raise RuntimeError(f"Synthesis failed for {language}: {result.error}")
            channels, rate, duration = validate(target)
            print(f"language: {language}; sample_rate: {rate}; channels: {channels}; duration_seconds: {duration:.2f}; gen_time: {result.gen_time:.2f}; total_seconds: {elapsed:.2f}; peak_allocated_gb: {torch.cuda.max_memory_allocated() / 2**30:.2f}; peak_reserved_gb: {torch.cuda.max_memory_reserved() / 2**30:.2f}; output: {target.resolve()}")
    finally:
        adapter.unload()
    print("CP5 REAL GATE EXECUTED — HUMAN LISTENING REQUIRED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
