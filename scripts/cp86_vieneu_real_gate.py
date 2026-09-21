"""Real offline VieNeu acceptance gate for a staged CP8.6 runtime."""
from __future__ import annotations

import os
import sys
import wave
from pathlib import Path


def main() -> int:
    evidence_log = Path(os.environ["CP86_VIENEU_LOG"])
    def record(message: str) -> None:
        with evidence_log.open("a", encoding="utf-8") as stream:
            stream.write(message + "\n")
        print(message, flush=True)

    record("CP86_VIENEU_GATE=START")
    output = Path(os.environ["CP86_VIENEU_OUTPUT"])
    output.parent.mkdir(parents=True, exist_ok=True)
    runtime_app = Path(sys.executable).resolve().parent / "app"
    sys.path.insert(0, str(runtime_app))

    record("CP86_VIENEU_GATE=IMPORT_ADAPTER")
    from backend.services.vieneu_adapter import VieNeuAdapter

    record("CP86_VIENEU_GATE=SYNTHESIS")
    result = VieNeuAdapter(device="cpu").synthesize(
        "Xin chao, day la kiem tra VieNeu ngoai tuyen.",
        "vi",
        output_path=output,
    )
    record(f"STATUS={result.status}")
    record(f"ERROR={result.error}")
    record(f"WAV_PATH={result.wav_path}")
    if result.status != "PASS" or not output.is_file() or output.stat().st_size <= 44:
        return 1
    with wave.open(str(output), "rb") as audio:
        record(f"CHANNELS={audio.getnchannels()}")
        record(f"SAMPLE_RATE={audio.getframerate()}")
        record(f"FRAMES={audio.getnframes()}")
        if audio.getnchannels() != 1 or audio.getframerate() != 24_000 or audio.getnframes() <= 0:
            return 1
    record("CP86_VIENEU_REAL_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
