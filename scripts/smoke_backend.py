"""CP0.3B-2 real bootstrap/loopback HTTP smoke; no model load or inference.

Run with the official backend Python from the repository root.
Owns and gracefully stops only its own Uvicorn server; fails if port 8000 is busy.
"""
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import platform
import socket
import sys
import threading
import time
from urllib.request import build_opener, ProxyHandler, Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prototype"))


def main() -> None:
    import uvicorn
    from backend.main import app
    from providers.omnivoice import OmniVoiceProvider

    evidence = {"status": "FAIL", "python": platform.python_version(),
                "interpreter": sys.executable, "fastapi": importlib.metadata.version("fastapi"),
                "uvicorn": uvicorn.__version__}
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = None
    thread = None
    original_connect = socket.socket.connect
    original_init = OmniVoiceProvider.__init__
    original_load = OmniVoiceProvider.load
    counts = {"provider_instances": 0, "load_calls": 0}

    def counted_init(self, *args, **kwargs):
        counts["provider_instances"] += 1
        original_init(self, *args, **kwargs)

    def forbidden_load(self):
        counts["load_calls"] += 1
        raise AssertionError("Model loading forbidden in bootstrap smoke")

    def local_connect(sock, address):
        if address[0] not in {"127.0.0.1", "localhost", "::1"}:
            raise AssertionError("External networking forbidden in backend smoke")
        return original_connect(sock, address)

    try:
        # Do not take over another process's port or kill another server.
        listener.bind(("127.0.0.1", 8000))
        listener.listen(128)
        config = uvicorn.Config(app, host="127.0.0.1", port=8000, access_log=False)
        server = uvicorn.Server(config)
        OmniVoiceProvider.__init__ = counted_init
        OmniVoiceProvider.load = forbidden_load
        socket.socket.connect = local_connect
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 20
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("Backend failed to start")
            time.sleep(0.05)
        evidence["startup_no_ai_imports"] = all(
            name not in sys.modules for name in ("torch", "omnivoice", "core.tts_manager"))
        assert evidence["startup_no_ai_imports"]
        provider_service = app.state.provider_service
        provider = provider_service.get_primary_provider()
        evidence["startup_provider_state"] = provider_service.status().providers[0].state.value
        assert evidence["startup_provider_state"] == "NOT_LOADED"
        assert not provider.is_loaded() and provider._model is None
        assert provider._torch is None
        opener = build_opener(ProxyHandler({}))

        def get(path):
            request = Request("http://127.0.0.1:8000" + path,
                              headers={"Origin": "http://localhost:5173"})
            with opener.open(request, timeout=120) as response:
                assert response.status == 200
                assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
                return json.load(response)

        evidence["health"] = get("/api/health")
        evidence["health_no_ai_imports"] = "torch" not in sys.modules and "omnivoice" not in sys.modules
        assert evidence["health_no_ai_imports"]
        evidence["providers"] = get("/api/providers/status")
        assert len(evidence["providers"]["providers"]) == 1
        assert evidence["providers"]["providers"][0]["loaded"] is False
        evidence["system"] = get("/api/system/status")
        status = evidence["system"]
        assert status["status"] == "ready"
        assert status["cuda_available"] is True
        assert "RTX 4050" in status["gpu_name"]
        assert status["omnivoice_available"] is True
        assert status["omnivoice_model_loaded"] is False
        assert status["primary_provider"] == provider.provider_name()
        assert status["provider_state"] == "NOT_LOADED"
        assert status["audio"] == {"sample_rate": 24000, "channels": 1}
        assert get("/api/system/status") == status
        evidence["openapi_paths"] = sorted(get("/openapi.json")["paths"])
        assert evidence["openapi_paths"] == [
            "/api/audio/{artifact_id}",
            "/api/health",
            "/api/providers/status",
            "/api/system/status",
            "/api/tts",
        ]
        import torch
        evidence["cuda_allocated_bytes"] = torch.cuda.memory_allocated(0)
        evidence["no_model_runtime_or_manager_imports"] = (
            "omnivoice" not in sys.modules and "core.tts_manager" not in sys.modules)
        assert evidence["cuda_allocated_bytes"] == 0
        assert evidence["no_model_runtime_or_manager_imports"]
        assert provider_service.get_primary_provider() is provider
        assert counts == {"provider_instances": 1, "load_calls": 0}
        evidence["lifecycle_counts"] = dict(counts)
        evidence["model_load_count"] = provider.health_check()["load_count"]
        assert evidence["model_load_count"] == 0
        evidence["model_vram_bytes"] = 0
        evidence["vram_scope"] = "No model instance/load; tensor allocation measured after status. Not total driver/context memory."
        evidence["status"] = "PASS"
    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(timeout=15)
            evidence["server_stopped"] = not thread.is_alive()
            if thread.is_alive():
                evidence["status"] = "FAIL"
        listener.close()
        socket.socket.connect = original_connect
        OmniVoiceProvider.__init__ = original_init
        OmniVoiceProvider.load = original_load
        evidence["service_released"] = getattr(app.state, "system_service", None) is None
        evidence["provider_service_released"] = getattr(app.state, "provider_service", None) is None
        if not evidence["service_released"]:
            evidence["status"] = "FAIL"
        (ROOT / "reports/cp03b2_http_smoke.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    assert evidence["status"] == "PASS"


if __name__ == "__main__":
    main()
