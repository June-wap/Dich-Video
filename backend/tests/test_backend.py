import importlib
import json
import logging
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.errors import ApplicationError, ErrorCode
from backend.logging_config import configure_logging
from backend.main import create_app
from dataclasses import asdict
from backend.config import OMNIVOICE_PROVIDER_ID
from backend.tests.provider_fakes import registry
from backend.services import system_service
from backend.services.system_service import RuntimeInfo, SystemService


def snapshot(cuda=True, available=True):
    return RuntimeInfo(python_version="3.12.10", torch_version="2.8.0+cu128",
                       cuda_available=cuda, gpu_name="test GPU" if cuda else None)


@pytest.fixture
def harness():
    probe = Mock(return_value=snapshot())
    providers = registry()
    service = SystemService(providers, probe)
    app = create_app(service_factory=lambda _: service, provider_service_factory=lambda _: providers)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield app, client, probe, service


def test_fresh_process_import_startup_health_and_shutdown_without_ai_imports():
    code = '''
import sys
from fastapi.testclient import TestClient
class BlockAI:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'omnivoice'}:
            from importlib.machinery import ModuleSpec
            return ModuleSpec(fullname, self)
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        raise AssertionError('AI runtime import forbidden during startup: ' + module.__name__)
sys.meta_path.insert(0, BlockAI())
from backend.main import app
with TestClient(app, base_url='http://127.0.0.1') as client:
    assert client.get('/api/health').status_code == 200
    assert app.state.system_service._snapshot is None
assert app.state.system_service is None
assert app.state.provider_service is None
assert 'torch' not in sys.modules and 'omnivoice' not in sys.modules
print('No model/runtime imports during import, startup, health or shutdown: PASS')
'''
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_health_schema_and_no_probe(harness):
    _, client, probe, _ = harness
    for _ in range(2):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "local-ai-voice-api", "version": "0.3.0-dev"}
    probe.assert_not_called()


def test_system_schema_cache_and_no_internal_fields(harness):
    _, client, probe, _ = harness
    response = client.get("/api/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data == {**asdict(snapshot()), "status": "ready", "omnivoice_available": True,
                    "omnivoice_model_loaded": False, "primary_provider": OMNIVOICE_PROVIDER_ID,
                    "provider_state": "NOT_LOADED", "audio": {"sample_rate": 24000, "channels": 1},
                    "runtime_mode": "local"}
    assert data["python_version"]
    assert type(data["cuda_available"]) is bool
    assert data["omnivoice_available"] is True
    assert data["omnivoice_model_loaded"] is False
    assert data["audio"] == {"sample_rate": 24000, "channels": 1}
    assert data["runtime_mode"] == "local"
    assert client.get("/api/system/status").json() == data
    probe.assert_called_once()


def test_runtime_probe_does_not_construct_or_load_models(monkeypatch):
    forbidden = Mock(side_effect=AssertionError("Model access forbidden"))
    fake = {
        "torch": SimpleNamespace(__version__="2.8.0+cu128", cuda=SimpleNamespace(
            is_available=lambda: True, get_device_name=lambda index: "Detected GPU")),
        "omnivoice": SimpleNamespace(OmniVoice=SimpleNamespace(
            from_pretrained=forbidden, generate=forbidden)),
    }
    imports = Mock(side_effect=lambda name: fake[name])
    monkeypatch.setattr(system_service, "importlib", SimpleNamespace(import_module=imports))
    result = system_service.probe_runtime()
    assert result.cuda_available is True
    assert result.gpu_name == "Detected GPU"
    forbidden.assert_not_called()
    assert [call.args[0] for call in imports.call_args_list] == ["torch"]


def test_missing_runtime_is_degraded_and_sanitized(monkeypatch):
    imports = Mock(side_effect=ImportError("private C:/secret/model/path"))
    monkeypatch.setattr(system_service, "importlib", SimpleNamespace(import_module=imports))
    result = SystemService(registry(available=False)).status()
    assert result.status == "degraded"
    assert result.cuda_available is False
    assert result.gpu_name is None
    assert result.omnivoice_available is False
    assert "secret" not in result.model_dump_json()


def test_cpu_only_runtime_does_not_probe_device_name(monkeypatch):
    get_name = Mock(side_effect=AssertionError("No CUDA device"))
    fake_torch = SimpleNamespace(__version__="test", cuda=SimpleNamespace(
        is_available=lambda: False, get_device_name=get_name))
    monkeypatch.setattr(system_service, "importlib", SimpleNamespace(import_module=lambda name:
        fake_torch if name == "torch" else SimpleNamespace(OmniVoice=object)))
    result = system_service.probe_runtime()
    assert result.cuda_available is False and result.gpu_name is None
    get_name.assert_not_called()


def test_unknown_route_normalized(harness):
    response = harness[1].get("/missing?secret=do-not-reflect")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["ok"] is False
    assert "secret" not in response.text


def test_method_not_allowed(harness):
    response = harness[1].post("/api/health")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in response.headers["allow"]


def test_validation_error_sanitized(harness):
    app, client, _, _ = harness

    @app.get("/test-validation")
    def validate(count: int):
        return {"count": count}

    response = client.get("/test-validation", params={"count": "private-client-value"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "private-client-value" not in response.text
    assert "traceback" not in response.text.lower()


def test_unexpected_error_is_safe_and_has_cors(harness):
    app, client, _, _ = harness

    @app.get("/test-error")
    def fail():
        raise RuntimeError("private C:/secret/model traceback")

    response = client.get("/test-error", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 500
    assert response.json() == {"ok": False, "error": {
        "code": "INTERNAL_ERROR", "message": "Đã xảy ra lỗi trong quá trình xử lý."}}
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "secret" not in response.text and "traceback" not in response.text.lower()


def test_unavailable_service_error(harness):
    app, client, _, _ = harness
    service = app.state.system_service
    app.state.system_service = None
    try:
        response = client.get("/api/system/status")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    finally:
        app.state.system_service = service


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_allowed_cors_origins(harness, origin):
    response = harness[1].get("/api/health", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin
    assert "access-control-allow-credentials" not in response.headers
    preflight = harness[1].options("/api/health", headers={
        "Origin": origin, "Access-Control-Request-Method": "GET"})
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin


def test_disallowed_cors_origin(harness):
    headers = {"Origin": "https://arbitrary.example"}
    response = harness[1].get("/api/health", headers=headers)
    assert "access-control-allow-origin" not in response.headers
    preflight = harness[1].options("/api/health", headers={
        **headers, "Access-Control-Request-Method": "GET"})
    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers


def test_disallowed_host(harness):
    response = harness[1].get("/api/health", headers={"Host": "arbitrary.example"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_openapi_only_checkpoint_routes(harness):
    client = harness[1]
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {
        # Security P0 (checklist-bao-mat-truoc-dong-goi-17-09.md item 1) -
        # registered unconditionally; whether it actually hands out a token
        # depends on Settings.require_local_token at request time (see
        # backend/tests/test_local_auth.py), not on whether the route exists.
        "/api/auth/token",
        "/api/health",
        "/api/system/status",
        # NOTE: this exact-set assertion had already drifted out of date
        # before this session (missing /api/settings/translation, which
        # already existed) - updated here to the full, accurate current
        # route set rather than left silently wrong.
        "/api/system/logs",
        "/api/providers/status",
        "/api/tts",
        "/api/tts/jobs",
        "/api/tts/jobs/{job_id}",
        "/api/audio/{artifact_id}",
        "/api/voices/profiles",
        "/api/voices/profiles/{profile_id}",
        "/api/voices/profiles/{profile_id}/test",
        "/api/tts/long-form",
        "/api/tts/long-form/{job_id}",
        "/api/settings/translation",
        "/api/settings/app",
    }
    assert schema["info"] == {"title": "Local AI Voice API", "version": "0.3.0-dev"}
    assert client.get("/docs").status_code == 200


def test_lifespan_releases_service_and_logs_once():
    services = []
    def factory(providers):
        service = SystemService(providers, Mock(return_value=snapshot()))
        services.append(service)
        return service
    app = create_app(service_factory=factory, provider_service_factory=lambda _: registry())
    for _ in range(2):
        with TestClient(app, base_url="http://127.0.0.1") as client:
            assert client.get("/api/system/status").status_code == 200
        assert app.state.system_service is None
        assert services[-1]._snapshot is None
    handlers = [h for h in logging.getLogger("backend").handlers if getattr(h, "_local_ai_backend", False)]
    assert len(handlers) == 1


def test_settings_defaults_and_environment(monkeypatch):
    assert Settings().host == "127.0.0.1"
    assert Settings().port == 8000
    monkeypatch.setenv("LOCAL_AI_PORT", "8123")
    monkeypatch.setenv("LOCAL_AI_CORS_ORIGINS", "http://localhost:5174")
    monkeypatch.setenv("LOCAL_AI_LOG_LEVEL", "warning")
    settings = Settings.from_env()
    assert settings.port == 8123 and settings.log_level == "WARNING"
    assert settings.cors_origins == ("http://localhost:5174",)


@pytest.mark.parametrize("origin", ["*", "https://arbitrary.example", "http://localhost:5173/path",
                                  "http://user:password@localhost:5173"])
def test_cors_config_rejects_broad_or_invalid_origins(origin):
    with pytest.raises(ValueError):
        Settings(cors_origins=(origin,))
