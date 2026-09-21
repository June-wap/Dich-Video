"""Security P1 (checklist-bao-mat-truoc-dong-goi-17-09.md muc 7): reject an
oversized request by its declared Content-Length before the body is ever
read/parsed - see MAX_REQUEST_BODY_BYTES and the check in
backend/main.py's request_boundary middleware.
"""
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import MAX_REQUEST_BODY_BYTES, create_app
from backend.tests.provider_fakes import registry


def _settings(tmp_path, **overrides):
    return Settings(
        output_dir=tmp_path / "outputs",
        database_path=tmp_path / "app.sqlite3",
        **overrides,
    )


def test_declared_content_length_under_limit_is_not_rejected_by_this_guard(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/api/health")
        assert response.status_code == 200


def test_declared_content_length_over_limit_is_rejected_before_reaching_the_route(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        # The actual body sent is tiny; only the *declared* Content-Length
        # header is oversized. This is exactly the case the guard exists
        # for: a client can claim any size upfront, and the middleware must
        # act on that claim before FastAPI/Starlette attempt to buffer or
        # parse a body of that size.
        response = client.post(
            "/api/voices/profiles",
            headers={"content-length": str(MAX_REQUEST_BODY_BYTES + 1)},
            content=b"tiny-body-does-not-matter-here",
        )
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "REFERENCE_AUDIO_TOO_LARGE"


def test_declared_content_length_exactly_at_limit_is_not_rejected_by_this_guard(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/voices/profiles",
            headers={"content-length": str(MAX_REQUEST_BODY_BYTES)},
            content=b"tiny-body-does-not-matter-here",
        )
        # Not 413: exactly-at-limit is allowed through this guard. It still
        # fails downstream (no real multipart file attached), but with the
        # route's own validation error, not this middleware's 413.
        assert response.status_code != 413


def test_malformed_content_length_header_does_not_crash_the_middleware(tmp_path):
    settings = _settings(tmp_path)
    app = create_app(settings, provider_service_factory=lambda _: registry())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post(
            "/api/voices/profiles",
            headers={"content-length": "not-a-number"},
            content=b"tiny-body-does-not-matter-here",
        )
        # A malformed header must never itself crash the request - it is
        # simply treated as "no usable declared size" and falls through to
        # ordinary route handling/validation.
        assert response.status_code != 500
