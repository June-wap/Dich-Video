"""CP0.2E.1 CUDA diagnostic. Does not change production inference defaults."""
from __future__ import annotations

import inspect
import json
import os
import shutil
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import soundfile as sf

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prototype"))

from core.audio_utils import BoundaryDSPConfig, merge_segments, select_pause_ms
from core.long_text import ChunkingConfig, build_chunks
from providers.omnivoice import OmniVoiceProvider


TEXT = (
    "Xin chào, đây là bài kiểm tra độ ổn định của giọng nói tiếng Việt. "
    "Mỗi câu mô tả một ý riêng để chúng ta nhận biết sự thay đổi giữa các đoạn. "
    "Người nghe cần chú ý đến cao độ, nhịp đọc và màu sắc của giọng nói. "
    "Các tệp thô được giữ nguyên trước khi cắt im lặng hoặc thêm hiệu ứng ở biên. "
    "Sau cùng, các phương án dài hơn giúp đánh giá hiện tượng đặt lại ngữ điệu."
)

OUT = ROOT / "reports" / "cp02e1_listening"


def audio_metrics(path: Path) -> dict:
    audio, rate = sf.read(path, dtype="float32", always_2d=False)
    assert rate == 24000 and audio.ndim == 1
    assert audio.size and np.isfinite(audio).all()
    rms = float(np.sqrt(np.mean(np.square(audio, dtype=np.float64))))
    peak = float(np.max(np.abs(audio)))
    zcr = float(np.mean(np.signbit(audio[1:]) != np.signbit(audio[:-1]))) if audio.size > 1 else 0.0
    spectrum = np.abs(np.fft.rfft(audio))
    frequencies = np.fft.rfftfreq(audio.size, 1 / rate)
    centroid = float(np.sum(spectrum * frequencies) / max(np.sum(spectrum), 1e-12))
    return {
        "duration_sec": round(audio.size / rate, 4),
        "sample_rate": rate,
        "channels": 1,
        "rms": round(rms, 6),
        "peak": round(peak, 6),
        "zero_crossing_rate": round(zcr, 6),
        "spectral_centroid_hz": round(centroid, 2),
    }


def boundary_plan(chunks) -> tuple[list[str], list[int]]:
    selected = [
        select_pause_ms(chunk.text, chunk.is_paragraph_end)
        for chunk in chunks[:-1]
    ]
    return [item[0] for item in selected], [item[1] for item in selected]


def merge_variant(paths, chunks, name: str, config) -> dict:
    labels, pauses = boundary_plan(chunks)
    diagnostics: list[dict] = []
    output = OUT / name
    merge_segments(
        paths,
        output,
        target_sr=24000,
        pauses_ms=pauses,
        boundary_labels=labels,
        boundary_config=config,
        diagnostics_out=diagnostics,
    )
    return {"path": str(output), "metrics": audio_metrics(output), "diagnostics": diagnostics}


def synthesize(provider, text: str, path: Path) -> dict:
    result = provider.synthesize(text, "vi", output_path=path)
    assert result.status == "PASS", result.error
    return {"result": asdict(result), "metrics": audio_metrics(path)}


def generate_num_step(provider, text: str, num_step: int, path: Path) -> dict:
    with provider._lock:
        provider._synchronize()
        started = time.perf_counter()
        generated = provider._model.generate(text=text, language="vi", num_step=num_step)
        provider._synchronize()
        elapsed = time.perf_counter() - started
    assert len(generated) == 1
    raw = generated[0]
    if hasattr(raw, "detach"):
        raw = raw.detach().cpu().numpy()
    audio = np.asarray(raw, dtype=np.float32).reshape(-1)
    assert audio.size and np.isfinite(audio).all()
    sf.write(path, audio, 24000, subtype="PCM_16")
    metrics = audio_metrics(path)
    metrics["generation_time_sec"] = round(elapsed, 4)
    metrics["rtf"] = round(elapsed / metrics["duration_sec"], 4)
    return {"path": str(path), "metrics": metrics}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    provider = OmniVoiceProvider()
    evidence: dict = {
        "checkpoint": "CP0.2E.1",
        "language": "vi",
        "provider": "omnivoice",
        "device": "cuda:0",
        "dtype": "float16",
        "model_load_count": None,
        "status": "FAIL",
        "text": TEXT,
        "tests": {},
    }
    try:
        provider.load()
        signature = inspect.signature(provider._model.generate)
        evidence["generate_signature"] = str(signature)
        evidence["declared_seed_parameter"] = any(
            name in signature.parameters for name in ("seed", "generator", "random_seed")
        )

        configs = {
            "A_1_sentence": ChunkingConfig(target_chars=500, max_chars=500, max_sentences_per_chunk=1),
            "B_2_sentences": ChunkingConfig(target_chars=500, max_chars=500, max_sentences_per_chunk=2),
            "C_250_350_chars": ChunkingConfig(target_chars=250, max_chars=350, max_sentences_per_chunk=10),
        }
        plans = {name: build_chunks(TEXT, config) for name, config in configs.items()}
        evidence["chunk_plans"] = {
            name: [{"index": c.index, "chars": len(c.text), "sentences": c.sentence_count} for c in chunks]
            for name, chunks in plans.items()
        }
        assert 3 <= len(plans["A_1_sentence"]) <= 5

        raw_paths = []
        raw_runs = []
        for index, chunk in enumerate(plans["A_1_sentence"], start=1):
            path = OUT / f"raw_chunk_{index:02d}.wav"
            raw_runs.append(synthesize(provider, chunk.text, path))
            raw_paths.append(path)
        evidence["tests"]["raw_chunks"] = raw_runs

        no_fade = BoundaryDSPConfig(edge_fade_ms=0, crossfade_ms=0, target_dbfs=None)
        current = BoundaryDSPConfig(crossfade_ms=0, target_dbfs=None)
        evidence["tests"]["raw_merge"] = merge_variant(raw_paths, plans["A_1_sentence"], "raw_merge.wav", None)
        evidence["tests"]["trim"] = merge_variant(raw_paths, plans["A_1_sentence"], "trim_merge.wav", no_fade)
        evidence["tests"]["trim_fade"] = merge_variant(raw_paths, plans["A_1_sentence"], "trim_fade_merge.wav", current)
        evidence["tests"]["processed"] = merge_variant(raw_paths, plans["A_1_sentence"], "processed_merge.wav", current)

        shutil.copyfile(OUT / "processed_merge.wav", OUT / "chunk_size_A_1_sentence.wav")
        evidence["tests"]["chunk_size_A"] = {
            "path": str(OUT / "chunk_size_A_1_sentence.wav"),
            "metrics": audio_metrics(OUT / "chunk_size_A_1_sentence.wav"),
        }
        for key, filename in (
            ("B_2_sentences", "chunk_size_B_2_sentences.wav"),
            ("C_250_350_chars", "chunk_size_C_250_350_chars.wav"),
        ):
            paths = []
            runs = []
            for index, chunk in enumerate(plans[key], start=1):
                path = OUT / f"{key}_chunk_{index:02d}.wav"
                runs.append(synthesize(provider, chunk.text, path))
                paths.append(path)
            merged = merge_variant(paths, plans[key], filename, current)
            merged["chunks"] = runs
            evidence["tests"][key] = merged

        representative = plans["B_2_sentences"][0].text
        evidence["tests"]["num_step"] = {}
        for step in (16, 24, 32):
            path = OUT / f"num_step_{step}.wav"
            evidence["tests"]["num_step"][str(step)] = generate_num_step(
                provider, representative, step, path
            )

        evidence["tests"]["repeatability"] = []
        for index in range(1, 4):
            path = OUT / f"repeat_{index}.wav"
            evidence["tests"]["repeatability"].append(synthesize(provider, representative, path))

        health = provider.health_check()
        assert health["load_count"] == 1
        evidence["provider_health"] = health
        evidence["model_load_count"] = health["load_count"]
        evidence["status"] = "PASS"
    finally:
        evidence["final_health"] = provider.health_check()
        (OUT / "diagnostics.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        provider.unload()


if __name__ == "__main__":
    main()
