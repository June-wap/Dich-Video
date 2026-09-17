"""Serving the built frontend from the backend itself (see
Settings.serve_frontend's docstring in backend/config.py) - the "1 tiến
trình, 1 cổng" mode used by scripts/run_backend.ps1 for a real run. Off by
default so every other test file - which never sets it, and never points
frontend_dist_dir anywhere real - keeps working unchanged; these are the
tests that turn it on and actually exercise it.
"""
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


def _make_dist(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>spa-shell</html>", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg>fav</svg>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    return dist


def test_disabled_by_default_root_path_is_still_404(tmp_path):
    settings = _settings(tmp_path)  # serve_frontend defaults to False
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/").status_code == 404


def test_enabled_but_dist_missing_does_not_crash_and_api_still_works(tmp_path):
    settings = _settings(
        tmp_path, serve_frontend=True, frontend_dist_dir=tmp_path / "no-such-dist"
    )
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/health").status_code == 200


def test_enabled_serves_index_html_at_root(tmp_path):
    dist = _make_dist(tmp_path)
    settings = _settings(tmp_path, serve_frontend=True, frontend_dist_dir=dist)
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "spa-shell" in response.text


def test_enabled_serves_a_real_static_asset(tmp_path):
    dist = _make_dist(tmp_path)
    settings = _settings(tmp_path, serve_frontend=True, frontend_dist_dir=dist)
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/assets/app.js")
        assert response.status_code == 200
        assert "console.log" in response.text


def test_enabled_falls_back_to_index_html_for_client_side_routes(tmp_path):
    # React Router routes like "/history" only exist client-side - there is
    # no history.html in dist - so the server must still return the SPA
    # shell for the browser's JS to take over and render the right screen.
    dist = _make_dist(tmp_path)
    settings = _settings(tmp_path, serve_frontend=True, frontend_dist_dir=dist)
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/history")
        assert response.status_code == 200
        assert "spa-shell" in response.text


def test_enabled_does_not_leak_files_outside_dist_via_path_traversal(tmp_path):
    dist = _make_dist(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("do-not-serve-me", encoding="utf-8")
    settings = _settings(tmp_path, serve_frontend=True, frontend_dist_dir=dist)
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        # Percent-encoded so the HTTP client itself doesn't normalize the
        # ".." away before sending - this is what actually exercises the
        # is_relative_to(dist_dir) guard in backend/main.py's serve_frontend,
        # rather than just the ordinary "unknown path" SPA-fallback case.
        response = client.get("/%2e%2e/secret.txt")
        assert "do-not-serve-me" not in response.text
        assert "spa-shell" in response.text


def test_enabled_does_not_require_local_token_but_api_still_does(tmp_path):
    # The page has to load BEFORE it can fetch a token at all (see
    # frontend/src/services/localToken.ts) - static files must stay
    # reachable with no token even when require_local_token is on.
    dist = _make_dist(tmp_path)
    settings = _settings(
        tmp_path,
        serve_frontend=True,
        frontend_dist_dir=dist,
        require_local_token=True,
        token_path=tmp_path / "runtime" / "session.token",
    )
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/").status_code == 200
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/api/health").status_code == 401
