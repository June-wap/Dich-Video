"""Backend startup tests for the intentional zero-provider state."""
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.services.provider_service import ProviderService

def test_backend_starts_with_the_lazy_vieneu_registry(tmp_path):
    settings = Settings(app_data_dir=tmp_path, output_dir=tmp_path / "audio")
    # TestClient's default host is ``testserver``.  Production accepts only
    # explicit loopback hosts, so keep the security boundary active in tests.
    with TestClient(create_app(settings), base_url="http://127.0.0.1") as client:
        status = client.get("/api/system/status").json()
        assert status["status"] == "ready"
        assert status["primary_provider"] == "vieneu"
        assert status["provider_state"] == "NOT_LOADED"
        providers = client.get("/api/providers/status").json()
        assert providers["primary"] == "vieneu"
        assert providers["providers"][0]["id"] == "vieneu"
        assert providers["providers"][0]["loaded"] is False
        capabilities = client.get("/api/system/capabilities").json()
        assert capabilities["providers"]["vieneu"]["policy"] == "cpu"
        assert capabilities["providers"]["chatterbox"]["policy"] == "cuda_required"

def test_tts_without_provider_returns_controlled_error(tmp_path):
    settings = Settings(app_data_dir=tmp_path, output_dir=tmp_path / "audio")
    # This test deliberately injects an empty registry: it verifies the
    # controlled unavailable contract without triggering real VieNeu loading.
    with TestClient(create_app(
        settings, provider_service_factory=lambda _: ProviderService()),
        base_url="http://127.0.0.1",
    ) as client:
        response = client.post("/api/tts", json={"text":"Xin chào", "language":"vi", "voice_id":"test_auto"})
        assert response.status_code == 404

