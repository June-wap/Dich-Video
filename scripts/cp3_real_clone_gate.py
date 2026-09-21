"""CP3 Real VieNeu Clone Gate.

Validates the ACTUAL production VieNeuAdapter
(backend/services/vieneu_adapter.py) against the pinned VieNeu v1.1.5
source/model/codec, using REAL reference audio + a matching transcript
already vendored with that pinned source. No mocking, no other model,
no other source/revision.

Usage (from the pinned venv, run from the project root so `backend` and
`.vendor-vieneu` resolve):

    .\\.venv312\\Scripts\\python.exe scripts\\cp3_real_clone_gate.py

Exits 0 on PASS, 1 on FAIL/BLOCKED.
"""
from __future__ import annotations

import json
import sys
import traceback
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.services.vieneu_adapter import VieNeuAdapter  # noqa: E402


# Real reference audio + matching transcript vendored with the pinned VieNeu
# v1.1.5 source itself - CP3 spec section 9 explicitly forbids "proving"
# clone quality with TTS-synthesized audio, so this never synthesizes a
# reference; it only uses audio that ships with the pinned repo.
REFERENCE_CANDIDATES = [
    (
        ROOT / ".vendor-vieneu" / "examples" / "audio_ref" / "example.wav",
        ROOT / ".vendor-vieneu" / "examples" / "audio_ref" / "example.txt",
    ),
    (
        ROOT / ".vendor-vieneu" / "vieneu" / "assets" / "samples" / "Bình (nam miền Bắc).wav",
        ROOT / ".vendor-vieneu" / "vieneu" / "assets" / "samples" / "Bình (nam miền Bắc).txt",
    ),
]

CLONE_TEXT = "Xin chào, đây là bài kiểm tra nhân bản giọng nói bằng VieNeu."
OUT_DIR = ROOT / ".cp0" / "audio" / "cp3_real_clone_gate"


def find_reference():
    for audio_path, text_path in REFERENCE_CANDIDATES:
        if audio_path.is_file() and text_path.is_file():
            transcript = text_path.read_text(encoding="utf-8").strip()
            if transcript:
                return audio_path, transcript
    return None, None


def main() -> int:
    audio_path, transcript = find_reference()
    if audio_path is None:
        print("REAL CLONE GATE BLOCKED - REFERENCE AUDIO REQUIRED")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_wav = OUT_DIR / "cloned_output.wav"

    report = {
        "source_revision": VieNeuAdapter.SOURCE_REVISION,
        "model_repo": VieNeuAdapter.MODEL_REPOSITORY,
        "model_revision": VieNeuAdapter.MODEL_REVISION,
        "codec_repo": VieNeuAdapter.CODEC_REPOSITORY,
        "codec_revision": VieNeuAdapter.CODEC_REVISION,
        "provider": VieNeuAdapter.PROVIDER_ID,
        "reference_audio": str(audio_path),
        "reference_transcript": transcript,
    }

    adapter = VieNeuAdapter(device="cpu")
    try:
        print(f"[1] Loading pinned VieNeu ({VieNeuAdapter.MODEL_REPOSITORY}@{VieNeuAdapter.MODEL_REVISION}) on cpu ...")
        adapter.load()

        print("[2] Creating real voice profile from reference audio ...")
        profile = adapter.create_voice_profile(audio_path, transcript)
        assert isinstance(profile, dict) and "codes" in profile and "text" in profile, \
            f"Unexpected profile shape: {type(profile)}"

        print("[3] Synthesizing a NEW Vietnamese sentence with the cloned profile ...")
        result = adapter.synthesize_cloned(
            text=CLONE_TEXT, language="vi", profile=profile, output_path=out_wav,
        )
        if result.status != "PASS":
            report["status"] = "FAIL"
            report["error"] = result.error
            print(json.dumps(report, indent=2, ensure_ascii=False))
            print("REAL CLONE GATE FAILED")
            return 1

        print("[4] Validating WAV output (mono / 24000 Hz / duration > 0) ...")
        exists = out_wav.is_file()
        size = out_wav.stat().st_size if exists else 0
        channels = sample_rate = 0
        duration = 0.0
        if exists:
            with wave.open(str(out_wav), "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                duration = n_frames / sample_rate if sample_rate > 0 else 0.0

        ok = exists and size > 0 and channels == 1 and sample_rate == 24000 and duration > 0
        report.update({
            "language": "vi",
            "cloned": True,
            "wav_exists": exists,
            "wav_size_bytes": size,
            "channels": channels,
            "sample_rate": sample_rate,
            "duration_seconds": round(duration, 3),
            "status": "PASS" if ok else "FAIL",
        })
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print("REAL CLONE GATE PASSED" if ok else "REAL CLONE GATE FAILED")
        return 0 if ok else 1
    except Exception as exc:
        report["status"] = "FAIL"
        report["error"] = str(exc)
        report["traceback"] = traceback.format_exc()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print("REAL CLONE GATE FAILED")
        return 1
    finally:
        adapter.unload()


if __name__ == "__main__":
    sys.exit(main())
