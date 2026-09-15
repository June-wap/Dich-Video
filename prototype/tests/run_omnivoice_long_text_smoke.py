"""Real CP0.2D CUDA smoke. Run with external/OmniVoice/.venv312 Python."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prototype"))

from core.long_text import ChunkingConfig
from core.tts_manager import TTSManager
from providers.omnivoice import OmniVoiceProvider


def main() -> None:
    import numpy as np
    import soundfile as sf
    import torch

    output_path = ROOT / "prototype" / "outputs" / "cp02d_long_vi.wav"
    evidence_path = ROOT / "reports" / "cp02d_omnivoice_long_text_smoke.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)

    provider = OmniVoiceProvider()
    manager = TTSManager(ROOT)
    manager.register_provider(provider)
    evidence = {
        "status": "FAIL",
        "python": sys.version,
        "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(0),
    }

    try:
        result = manager.synthesize_long_text(
            text=(
                "Xin chào, đây là phép thử văn bản dài bằng tiếng Việt. "
                "Mỗi câu được tạo thành một đoạn âm thanh riêng. "
                "Các đoạn sau đó được ghép đúng thứ tự thành một tệp hoàn chỉnh."
            ),
            language="vi",
            voice_id="omnivoice_auto",
            filename=output_path.name,
            chunk_config=ChunkingConfig(
                target_chars=120,
                max_chars=160,
                max_sentences_per_chunk=1,
            ),
            max_retries=0,
            keep_temp=False,
        )
        evidence["result"] = result
        assert result["status"] == "COMPLETED", result["error"]
        assert result["language"] == "vi"
        assert result["provider"] == "omnivoice"
        assert result["chunk_count"] == 3
        assert result["completed_chunks"] == result["chunk_count"]
        assert [chunk["index"] for chunk in result["chunks"]] == [0, 1, 2]
        assert all(chunk["status"] == "COMPLETED" for chunk in result["chunks"])

        samples, sample_rate = sf.read(output_path, dtype="float32", always_2d=False)
        duration = len(samples) / sample_rate
        health = provider.health_check()
        assert sample_rate == 24000
        assert samples.ndim == 1
        assert samples.size > 0 and np.isfinite(samples).all()
        assert np.max(np.abs(samples)) > 0
        assert health["load_count"] == 1

        evidence["audio"] = {
            "path": str(output_path),
            "sample_rate": sample_rate,
            "channels": 1,
            "duration_sec": round(duration, 3),
            "generation_time_sec": result["elapsed_sec"],
            "rtf": round(result["elapsed_sec"] / duration, 4),
        }
        evidence["provider_health"] = health
        evidence["status"] = "PASS"
        print(json.dumps(evidence, ensure_ascii=False, indent=2), flush=True)
    finally:
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        provider.unload()


if __name__ == "__main__":
    main()
