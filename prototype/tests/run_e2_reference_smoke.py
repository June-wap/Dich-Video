"""CP0.2E.2 reference preflight and one short cloned-voice smoke only."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "prototype"))

from providers.omnivoice import OmniVoiceProvider


def main() -> None:
    import numpy as np
    import soundfile as sf
    import torch

    reference_path = ROOT / "prototype" / "voices" / "e2_test" / "reference.wav"
    transcript_path = ROOT / "prototype" / "voices" / "e2_test" / "transcript.txt"
    output_dir = ROOT / "reports" / "cp02e2_listening"
    output_path = output_dir / "reference_smoke.wav"
    evidence_path = output_dir / "reference_smoke_diagnostics.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    transcript = transcript_path.read_text(encoding="utf-8")
    if not transcript.strip():
        raise ValueError("Reference transcript is empty")

    reference, reference_rate = sf.read(
        reference_path, dtype="float32", always_2d=True
    )
    if (
        not reference.size
        or reference_rate <= 0
        or not np.isfinite(reference).all()
        or not np.any(reference)
    ):
        raise ValueError("Reference audio is empty or invalid")

    provider = OmniVoiceProvider()
    evidence = {
        "checkpoint": "CP0.2E.2_REFERENCE_SMOKE",
        "status": "FAIL",
        "reference_preflight": {
            "decodable": True,
            "sample_rate": reference_rate,
            "channels": reference.shape[1],
            "duration_sec": round(len(reference) / reference_rate, 3),
            "finite": True,
            "non_empty": True,
            "transcript_non_empty": True,
            "transcript_chars": len(transcript.strip()),
        },
        "python": sys.version,
        "torch": torch.__version__,
        "gpu": torch.cuda.get_device_name(0),
    }

    try:
        provider.load()
        profile = provider.create_voice_profile(reference_path, transcript)
        result = provider.synthesize_cloned(
            "Xin chào, đây là phép thử ngắn để xác nhận giọng nói tham chiếu.",
            "vi",
            profile,
            output_path=output_path,
        )
        assert result.status == "PASS", result.error

        audio, sample_rate = sf.read(output_path, dtype="float32", always_2d=False)
        assert sample_rate == 24000
        assert audio.ndim == 1 and audio.size > 0
        assert np.isfinite(audio).all() and np.max(np.abs(audio)) > 0

        health = provider.health_check()
        assert health["load_count"] == 1
        assert len(provider._profiles) == 1
        evidence["voice_profile"] = {
            "created_count": 1,
            "reference_duration_sec": round(profile.reference_duration, 3),
        }
        evidence["output"] = {
            "path": str(output_path),
            "sample_rate": sample_rate,
            "channels": 1,
            "sample_count": int(audio.size),
            "duration_sec": round(audio.size / sample_rate, 3),
            "finite": True,
            "non_empty": True,
            "peak": round(float(np.max(np.abs(audio))), 6),
            "generation_time_sec": round(result.gen_time, 3),
            "rtf": round(result.rtf, 4),
        }
        evidence["provider_health"] = health
        evidence["model_load_count"] = health["load_count"]
        evidence["status"] = "REFERENCE_SMOKE_LISTENING_REQUIRED"
    finally:
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        provider.unload()


if __name__ == "__main__":
    main()
