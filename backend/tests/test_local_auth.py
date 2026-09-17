"""Security P0 - local API auth token (see the project's
checklist-bao-mat-truoc-dong-goi-17-09.md item 1). Off by default (see
Settings.require_local_token's docstring in backend/config.py) so every
other test file in this suite is unaffected - these are the tests that turn
it on and actually exercise it.
"""
import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.tests.provider_fakes import registry


def _settings(tmp_path, **overrides):
    return Settings(
        output_dir=tmp_path / "outputs",
        database_path=tmp_path / "app.sqlite3",
        **overrides,
    )


@pytest.fixture
def secured_client(tmp_path):
    settings = _settings(
        tmp_path, require_local_token=True, token_path=tmp_path / "runtime" / "session.token"
    )
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield app, client


def test_protected_endpoint_rejects_missing_token(secured_client):
    _, client = secured_client
    response = client.get("/api/health")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_protected_endpoint_rejects_wrong_token(secured_client):
    _, client = secured_client
    response = client.get("/api/health", headers={"X-Local-Token": "wrong"})
    assert response.status_code == 401


def test_protected_endpoint_accepts_header_token(secured_client):
    app, client = secured_client
    response = client.get("/api/health", headers={"X-Local-Token": app.state.local_token})
    assert response.status_code == 200


def test_protected_endpoint_accepts_query_token_for_no_custom_header_requests(secured_client):
    # <audio src>/<a download> against GET /api/audio/{id} cannot set a
    # custom header - this is the fallback the frontend uses for exactly
    # those two request kinds (see frontend/src/services/httpClient.ts's
    # resolveBackendUrl). /api/health stands in for any protected endpoint
    # here - the mechanism itself is generic, not audio-specific.
    app, client = secured_client
    response = client.get("/api/health", params={"token": app.state.local_token})
    assert response.status_code == 200


def test_token_file_is_written_and_matches_state(secured_client, tmp_path):
    app, _ = secured_client
    token_file = tmp_path / "runtime" / "session.token"
    assert token_file.is_file()
    assert token_file.read_text(encoding="utf-8") == app.state.local_token


def test_token_file_removed_on_shutdown(tmp_path):
    settings = _settings(
        tmp_path, require_local_token=True, token_path=tmp_path / "runtime" / "session.token"
    )
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1"):
        assert settings.token_path.is_file()
    assert not settings.token_path.exists()


def test_bootstrap_endpoint_rejects_wrong_origin(secured_client):
    _, client = secured_client
    wrong_origin = client.get("/api/auth/token", headers={"Origin": "https://arbitrary.example"})
    assert wrong_origin.status_code == 401


def test_bootstrap_endpoint_accepts_missing_origin(secured_client):
    # A same-origin GET fetch never carries an Origin header at all (WHATWG
    # Fetch spec) - this is the common case once Settings.serve_frontend
    # serves the frontend from the backend's own origin (backend/main.py).
    # See backend/api/auth.py's docstring for why "no Origin" is safe to
    # accept here without weakening the check against a *disallowed* Origin.
    app, client = secured_client
    response = client.get("/api/auth/token")
    assert response.status_code == 200
    assert response.json() == {"token": app.state.local_token}


def test_bootstrap_endpoint_returns_real_token_for_allowed_origin(secured_client):
    app, client = secured_client
    response = client.get("/api/auth/token", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.json() == {"token": app.state.local_token}


def test_bootstrap_endpoint_disabled_by_default(tmp_path):
    settings = _settings(tmp_path)  # require_local_token defaults to False
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/api/auth/token", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 404


def test_disabled_by_default_needs_no_token_anywhere(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/health").status_code == 200


def test_cors_preflight_not_blocked_by_token_check(secured_client):
    _, client = secured_client
    preflight = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert preflight.status_code == 200
