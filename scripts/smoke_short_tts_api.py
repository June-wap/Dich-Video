"""CP0.3B-3 Real CUDA Short TTS API Smoke.

Starts Uvicorn server in-process, submits live TTS requests to OmniVoice on CUDA,
validates WAV audio output, verifies lazy loading, model reuse, and security.
Writes reports/cp03b3_short_tts_smoke.json and audio samples to reports/cp03b3_listening/.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import platform
import shutil
import socket
import sys
import threading
import time
from urllib.request import build_opener, HTTPError, ProxyHandler, Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prototype"))


def main() -> None:
    import numpy as np
    import soundfile as sf
    import torch
    import uvicorn

    from backend.main import app
    from providers.omnivoice import OmniVoiceProvider

    evidence = {
        "status": "FAIL",
        "python": platform.python_version(),
        "interpreter": sys.executable,
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "cuda_version": torch.version.cuda,
    }

    if not evidence["cuda_available"]:
        evidence["error"] = "CUDA unavailable for real inference smoke"
        print(json.dumps(evidence, indent=2))
        sys.exit(1)

    # Track provider instance creation
    counts = {"provider_instances": 0}
    original_init = OmniVoiceProvider.__init__

    def counted_init(self, *args, **kwargs):
        counts["provider_instances"] += 1
        original_init(self, *args, **kwargs)

    OmniVoiceProvider.__init__ = counted_init

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = None
    thread = None

    listening_dir = ROOT / "reports" / "cp03b3_listening"
    listening_dir.mkdir(parents=True, exist_ok=True)

    try:
        listener.bind(("127.0.0.1", 8000))
        listener.listen(128)
        config = uvicorn.Config(app, host="127.0.0.1", port=8000, access_log=False)
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()

        deadline = time.monotonic() + 20
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Backend failed to start")
            time.sleep(0.05)

        provider_service = app.state.provider_service
        provider = provider_service.get_primary_provider()

        opener = build_opener(ProxyHandler({}))

        def http_get(path: str):
            req = Request(f"http://127.0.0.1:8000{path}", headers={"Origin": "http://localhost:5173"})
            with opener.open(req, timeout=180) as resp:
                return resp.status, dict(resp.headers), resp.read()

        def http_post(path: str, data: dict):
            body = json.dumps(data).encode("utf-8")
            req = Request(
                f"http://127.0.0.1:8000{path}",
                data=body,
                headers={"Content-Type": "application/json", "Origin": "http://localhost:5173"},
                method="POST",
            )
            with opener.open(req, timeout=180) as resp:
                return resp.status, dict(resp.headers), resp.read()

        # 1. Verify initial status: NOT_LOADED
        status_code, _, body = http_get("/api/providers/status")
        assert status_code == 200
        providers_status = json.loads(body.decode("utf-8"))
        evidence["provider_state_before"] = providers_status["providers"][0]["state"]
        evidence["loaded_before"] = providers_status["providers"][0]["loaded"]
        assert evidence["provider_state_before"] == "NOT_LOADED"
        assert evidence["loaded_before"] is False
        assert provider.health_check()["load_count"] == 0

        # 2. Request 1: Short Vietnamese text
        text1 = "Xin chào. Đây là bài kiểm tra hệ thống tổng hợp giọng nói."
        payload1 = {
            "text": text1,
            "language": "vi",
            "voice_id": "omnivoice_auto",
            "speed": 1.0,
            "format": "wav",
        }

        t0 = time.perf_counter()
        status_code, _, body = http_post("/api/tts", payload1)
        req1_wall_time = time.perf_counter() - t0
        assert status_code == 200
        resp1 = json.loads(body.decode("utf-8"))
        assert resp1["ok"] is True
        data1 = resp1["data"]
        gen_id_1 = data1["generation_id"]

        # Validate audio download 1
        status_code, headers1, audio_bytes1 = http_get(f"/api/audio/{gen_id_1}.wav")
        assert status_code == 200
        assert headers1.get("Content-Type", "").startswith("audio/wav") or headers1.get("content-type", "").startswith("audio/wav")
        assert len(audio_bytes1) > 0

        # Validate WAV audio properties with soundfile
        audio_data1, sr1 = sf.read(io.BytesIO(audio_bytes1), dtype="float32", always_2d=True)
        assert sr1 == 24000
        assert audio_data1.shape[1] == 1
        assert np.isfinite(audio_data1).all()
        dur1 = len(audio_data1) / sr1
        assert dur1 > 0

        # Save listening file 1
        target_wav_1 = listening_dir / "short_tts_01.wav"
        target_wav_1.write_bytes(audio_bytes1)

        evidence["request_1"] = {
            "text_length": len(text1),
            "language": "vi",
            "voice": "omnivoice_auto",
            "generation_id": gen_id_1,
            "wall_time_seconds": round(req1_wall_time, 3),
            "reported_duration_seconds": data1["duration_seconds"],
            "measured_duration_seconds": round(dur1, 3),
            "sample_rate": sr1,
            "channels": audio_data1.shape[1],
            "file_size_bytes": len(audio_bytes1),
            "finite_samples": bool(np.isfinite(audio_data1).all()),
            "listening_artifact": str(target_wav_1.relative_to(ROOT)),
        }

        # Verify provider state after request 1: READY
        status_code, _, body = http_get("/api/providers/status")
        providers_status_after1 = json.loads(body.decode("utf-8"))
        state_after1 = providers_status_after1["providers"][0]["state"]
        loaded_after1 = providers_status_after1["providers"][0]["loaded"]
        assert state_after1 == "READY"
        assert loaded_after1 is True
        load_count_after1 = provider.health_check()["load_count"]
        assert load_count_after1 == 1

        # 3. Request 2: Second short text (model reuse)
        text2 = "Đây là câu thứ hai nhằm xác nhận mô hình được tái sử dụng mà không cần nạp lại."
        payload2 = {
            "text": text2,
            "language": "vi",
            "voice_id": "omnivoice_auto",
            "speed": 1.0,
            "format": "wav",
        }

        t0 = time.perf_counter()
        status_code, _, body = http_post("/api/tts", payload2)
        req2_wall_time = time.perf_counter() - t0
        assert status_code == 200
        resp2 = json.loads(body.decode("utf-8"))
        assert resp2["ok"] is True
        data2 = resp2["data"]
        gen_id_2 = data2["generation_id"]

        # Validate audio download 2
        status_code, headers2, audio_bytes2 = http_get(f"/api/audio/{gen_id_2}.wav")
        assert status_code == 200
        audio_data2, sr2 = sf.read(io.BytesIO(audio_bytes2), dtype="float32", always_2d=True)
        assert sr2 == 24000
        assert audio_data2.shape[1] == 1
        assert np.isfinite(audio_data2).all()
        dur2 = len(audio_data2) / sr2
        assert dur2 > 0

        # Save listening file 2
        target_wav_2 = listening_dir / "short_tts_02.wav"
        target_wav_2.write_bytes(audio_bytes2)

        evidence["request_2"] = {
            "text_length": len(text2),
            "language": "vi",
            "voice": "omnivoice_auto",
            "generation_id": gen_id_2,
            "wall_time_seconds": round(req2_wall_time, 3),
            "reported_duration_seconds": data2["duration_seconds"],
            "measured_duration_seconds": round(dur2, 3),
            "sample_rate": sr2,
            "channels": audio_data2.shape[1],
            "file_size_bytes": len(audio_bytes2),
            "finite_samples": bool(np.isfinite(audio_data2).all()),
            "listening_artifact": str(target_wav_2.relative_to(ROOT)),
        }

        # Check provider state after request 2
        load_count_after2 = provider.health_check()["load_count"]
        evidence["provider_state_after"] = state_after1
        evidence["provider_instance_count"] = counts["provider_instances"]
        evidence["model_load_count"] = load_count_after2
        assert load_count_after2 == 1  # Reused!

        # 4. Security checks on running server
        # Path traversal
        try:
            http_get("/api/audio/../../secret.txt")
            traversal_blocked = False
        except HTTPError as e:
            traversal_blocked = e.code in (404, 422)
        evidence["security_path_traversal_blocked"] = traversal_blocked
        assert traversal_blocked

        # Missing artifact
        try:
            http_get("/api/audio/00000000-0000-0000-0000-000000000000.wav")
            missing_safe = False
        except HTTPError as e:
            missing_safe = e.code == 404
        evidence["security_missing_artifact_404"] = missing_safe
        assert missing_safe

        evidence["status"] = "PASS"

    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=15)
            evidence["server_stopped"] = not thread.is_alive()
        listener.close()
        OmniVoiceProvider.__init__ = original_init

        evidence_file = ROOT / "reports" / "cp03b3_short_tts_smoke.json"
        evidence_file.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    assert evidence["status"] == "PASS"


if __name__ == "__main__":
    main()
