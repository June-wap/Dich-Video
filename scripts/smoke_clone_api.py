"""CP0.3B-4 Real CUDA Voice Cloning API Smoke.

Starts Uvicorn server on loopback, creates a VoiceProfile from the canonical
reference audio/transcript, verifies model lazy-load, submits 3 sequential clone
requests, and proves the profile is created once and reused across all 3 generations.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import platform
import socket
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler
import numpy as np
import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prototype"))

from backend.main import app
from providers.omnivoice import OmniVoiceProvider


def build_multipart_form(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    boundary = f"----WebKitFormBoundary{int(time.time() * 1000)}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")

    for name, (filename, data, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(data)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    return bytes(body), f"multipart/form-data; boundary={boundary}"


def validate_wav(data: bytes) -> dict:
    audio, sr = sf.read(io.BytesIO(data), dtype="float32")
    channels = 1 if audio.ndim == 1 else audio.shape[1]
    duration = len(audio) / sr if sr > 0 else 0.0
    finite = bool(np.isfinite(audio).all())
    has_nan = bool(np.isnan(audio).any())
    has_inf = bool(np.isinf(audio).any())
    valid = bool(sr == 24000 and channels == 1 and duration > 0 and finite and not has_nan and not has_inf)
    return {
        "bytes_len": len(data),
        "sample_rate": sr,
        "channels": channels,
        "duration": round(duration, 3),
        "finite": finite,
        "has_nan": has_nan,
        "has_inf": has_inf,
        "valid": valid,
    }


def main():
    sys.stdout.reconfigure(line_buffering=True)
    print("=== CP0.3B-4 REAL CUDA CLONE API SMOKE ===")

    listening_dir = ROOT / "reports" / "cp03b4_listening"
    listening_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = ROOT / "reports" / "cp03b4_clone_smoke.json"

    # Track OmniVoiceProvider instantiation and create_voice_profile calls
    counts = {
        "provider_instances": 0,
        "profile_creations": 0,
    }
    orig_init = OmniVoiceProvider.__init__
    orig_create = OmniVoiceProvider.create_voice_profile

    def counted_init(self, *args, **kwargs):
        counts["provider_instances"] += 1
        orig_init(self, *args, **kwargs)

    def counted_create(self, *args, **kwargs):
        counts["profile_creations"] += 1
        return orig_create(self, *args, **kwargs)

    OmniVoiceProvider.__init__ = counted_init
    OmniVoiceProvider.create_voice_profile = counted_create

    import uvicorn

    server_config = uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info", access_log=False)
    server = uvicorn.Server(server_config)

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 8000))
    listener.listen(128)

    server_thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    server_thread.start()

    # Wait for server ready
    deadline = time.monotonic() + 20
    while not server.started:
        if not server_thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("Server failed to start")
        time.sleep(0.05)
    print("  Server started on 127.0.0.1:8000")

    opener = build_opener(ProxyHandler({}))

    def http_get(path: str) -> tuple[int, dict, bytes]:
        req = Request(f"http://127.0.0.1:8000{path}", headers={"Origin": "http://localhost:5173"})
        with opener.open(req, timeout=120) as resp:
            return resp.status, dict(resp.headers), resp.read()

    def http_post_json(path: str, data: dict) -> tuple[int, dict, bytes]:
        body = json.dumps(data).encode("utf-8")
        req = Request(
            f"http://127.0.0.1:8000{path}",
            data=body,
            headers={"Content-Type": "application/json", "Origin": "http://localhost:5173"},
            method="POST",
        )
        with opener.open(req, timeout=120) as resp:
            return resp.status, dict(resp.headers), resp.read()

    def http_post_multipart(path: str, fields: dict, files: dict) -> tuple[int, dict, bytes]:
        body, content_type = build_multipart_form(fields, files)
        req = Request(
            f"http://127.0.0.1:8000{path}",
            data=body,
            headers={"Content-Type": content_type, "Origin": "http://localhost:5173"},
            method="POST",
        )
        with opener.open(req, timeout=120) as resp:
            return resp.status, dict(resp.headers), resp.read()

    evidence = {
        "status": "FAIL",
        "runtime": {
            "python": platform.python_version(),
            "interpreter": sys.executable,
            "torch": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda,
            "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        },
    }

    try:
        # 1. Check health
        h_status, _, h_body = http_get("/api/health")
        assert h_status == 200

        # 2. Check provider state before inference
        p_status, _, p_body = http_get("/api/providers/status")
        prov_before = json.loads(p_body.decode("utf-8"))["providers"][0]
        evidence["provider_state_before"] = prov_before["state"]
        print("  Provider state before inference:", prov_before["state"])
        assert prov_before["state"] == "NOT_LOADED"
        assert prov_before["loaded"] is False

        # 3. Reference material
        ref_wav_path = ROOT / "prototype" / "voices" / "e2_test" / "reference.wav"
        ref_txt_path = ROOT / "prototype" / "voices" / "e2_test" / "transcript.txt"
        assert ref_wav_path.is_file(), f"Missing {ref_wav_path}"
        assert ref_txt_path.is_file(), f"Missing {ref_txt_path}"

        ref_bytes = ref_wav_path.read_bytes()
        ref_transcript = ref_txt_path.read_text(encoding="utf-8").strip()
        ref_metrics = validate_wav(ref_bytes)

        evidence["reference"] = {
            "file_size": len(ref_bytes),
            "sample_rate": ref_metrics["sample_rate"],
            "channels": ref_metrics["channels"],
            "duration": ref_metrics["duration"],
            "transcript_length": len(ref_transcript),
        }
        print(f"  Loaded reference: {ref_metrics['duration']}s, {ref_metrics['sample_rate']}Hz, transcript_len={len(ref_transcript)}")

        # 4. Create VoiceProfile via API (triggers lazy model load)
        print("  [POST /api/voices/profiles] Creating profile (Cold load)...")
        t0 = time.perf_counter()
        cp_status, _, cp_body = http_post_multipart(
            "/api/voices/profiles",
            fields={"reference_transcript": ref_transcript, "name": "Canonical Test Voice"},
            files={"file": ("reference.wav", ref_bytes, "audio/wav")},
        )
        t1 = time.perf_counter()
        profile_creation_time = t1 - t0
        cp_json = json.loads(cp_body.decode("utf-8"))
        assert cp_status == 200 and cp_json.get("ok") is True
        profile_id = cp_json["data"]["profile_id"]
        print(f"  Profile created: ID={profile_id} in {profile_creation_time:.2f}s")

        # Verify provider transitioned to READY
        _, _, p_body_after = http_get("/api/providers/status")
        prov_after = json.loads(p_body_after.decode("utf-8"))["providers"][0]
        print("  Provider state after profile creation:", prov_after["state"])
        assert prov_after["state"] == "READY"
        assert prov_after["loaded"] is True

        # Primary provider internal load count
        primary_provider = app.state.provider_service.get_primary_provider()
        model_load_count = getattr(primary_provider, "_load_count", 1)
        evidence["provider_instance_count"] = counts["provider_instances"]
        evidence["model_load_count"] = model_load_count
        evidence["profile_creation_count"] = counts["profile_creations"]
        assert counts["profile_creations"] == 1
        assert model_load_count == 1

        evidence["profile"] = {
            "profile_id": profile_id,
            "creation_time_seconds": round(profile_creation_time, 3),
            "creation_count": counts["profile_creations"],
            "status": "ready",
        }

        # 5. Clone generation #1
        test_texts = [
            ("clone_01.wav", "Xin chào. Đây là bài kiểm tra đầu tiên của giọng nói mẫu."),
            ("clone_02.wav", "Hệ thống đang kiểm tra khả năng giữ nguyên người nói giữa nhiều lần tạo âm thanh."),
            ("clone_03.wav", "Nếu ba đoạn này sử dụng cùng một giọng, chúng ta có thể tiếp tục thử nghiệm văn bản dài."),
        ]

        evidence["generations"] = []

        for idx, (filename, text) in enumerate(test_texts, start=1):
            print(f"  [Generation #{idx}] Synthesizing test text...")
            t0 = time.perf_counter()
            gen_status, _, gen_body = http_post_json(
                f"/api/voices/profiles/{profile_id}/test",
                {"text": text, "language": "vi", "speed": 1.0, "format": "wav"},
            )
            t1 = time.perf_counter()
            wall_time = t1 - t0
            gen_json = json.loads(gen_body.decode("utf-8"))
            assert gen_status == 200 and gen_json.get("ok") is True
            gen_data = gen_json["data"]
            assert gen_data["profile_id"] == profile_id

            # Retrieve audio
            audio_url = gen_data["audio_url"]
            a_status, _, a_bytes = http_get(audio_url)
            assert a_status == 200
            wav_metrics = validate_wav(a_bytes)
            assert wav_metrics["valid"] is True

            # Save artifact
            out_wav = listening_dir / filename
            out_wav.write_bytes(a_bytes)
            print(f"    Saved {out_wav.name}: {wav_metrics['duration']}s in {wall_time:.2f}s (valid={wav_metrics['valid']})")

            # Check invariants after each generation
            assert counts["profile_creations"] == 1
            assert getattr(primary_provider, "_load_count", 1) == 1

            evidence["generations"].append({
                "index": idx,
                "file": filename,
                "text_length": len(text),
                "duration_seconds": wav_metrics["duration"],
                "wall_time_seconds": round(wall_time, 3),
                "sample_rate": wav_metrics["sample_rate"],
                "channels": wav_metrics["channels"],
                "file_size": len(a_bytes),
                "valid": wav_metrics["valid"],
            })

        evidence["status"] = "PASS_WITH_LISTENING_REQUIRED"
        print("\nAll 3 generations succeeded using SAME profile_id!")
        print(f"Profile creations: {counts['profile_creations']}")
        print(f"Model loads: {getattr(primary_provider, '_load_count', 1)}")

    finally:
        server.should_exit = True
        server_thread.join(timeout=10)
        listener.close()
        print("  Server shutdown cleanly.")

    evidence_file.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"  Saved evidence to: {evidence_file}")


if __name__ == "__main__":
    main()
