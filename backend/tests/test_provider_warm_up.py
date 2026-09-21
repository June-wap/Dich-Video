"""Startup warm-up (see Settings.warm_up_on_start's docstring in
backend/config.py). Off by default so every other test file - which never
sets it - keeps working unchanged; these are the tests that turn it on and
actually exercise it.
"""
import time

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.tests.provider_fakes import FakeAdditionalProvider, FakeProvider, registry


def _settings(tmp_path, **overrides):
    return Settings(
        output_dir=tmp_path / "outputs",
        database_path=tmp_path / "app.sqlite3",
        **overrides,
    )


def _wait_until(predicate, *, timeout=2.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_disabled_by_default_never_loads_on_startup(tmp_path):
    fake = FakeProvider()
    settings = _settings(tmp_path)  # warm_up_on_start defaults to False
    app = create_app(settings, provider_service_factory=lambda _: registry(fake))
    with TestClient(app, base_url="http://127.0.0.1"):
        # No request was made either - this is the same "never loads until a
        # real request asks for it" behavior the rest of the suite relies on.
        time.sleep(0.1)
        assert fake.load_calls == 0


def test_enabled_loads_the_primary_provider_in_the_background(tmp_path):
    fake = FakeProvider()
    settings = _settings(tmp_path, warm_up_on_start=True)
    app = create_app(settings, provider_service_factory=lambda _: registry(fake))
    with TestClient(app, base_url="http://127.0.0.1"):
        assert _wait_until(lambda: fake.load_calls == 1)
        # A real request arriving after the background warm-up finished must
        # see the already-loaded model, not trigger a second, redundant load.
        app.state.provider_service.ensure_primary_provider_loaded()
        assert fake.load_calls == 1


def test_enabled_also_warms_up_other_available_providers(tmp_path):
    fake = FakeProvider()
    additional = FakeAdditionalProvider()
    settings = _settings(tmp_path, warm_up_on_start=True)
    app = create_app(settings, provider_service_factory=lambda _: registry(fake, additional_provider=additional))
    with TestClient(app, base_url="http://127.0.0.1"):
        assert _wait_until(lambda: fake.is_loaded() and additional.is_loaded())


def test_enabled_skips_unavailable_providers(tmp_path):
    fake = FakeProvider()
    settings = _settings(tmp_path, warm_up_on_start=True)
    app = create_app(settings, provider_service_factory=lambda _: registry(fake, available=False))
    with TestClient(app, base_url="http://127.0.0.1"):
        time.sleep(0.2)
        assert fake.load_calls == 0


def test_enabled_does_not_block_startup_or_health_when_load_is_slow(tmp_path, monkeypatch):
    fake = FakeProvider()
    real_load = fake.load

    def slow_load():
        time.sleep(0.5)
        return real_load()

    monkeypatch.setattr(fake, "load", slow_load)
    settings = _settings(tmp_path, warm_up_on_start=True)
    app = create_app(settings, provider_service_factory=lambda _: registry(fake))
    started = time.monotonic()
    with TestClient(app, base_url="http://127.0.0.1") as client:
        elapsed = time.monotonic() - started
        assert elapsed < 0.5, "lifespan startup must not block on the warm-up load"
        response = client.get("/api/health")
        assert response.status_code == 200
        assert fake.load_calls == 0  # still loading in the background
        assert _wait_until(lambda: fake.load_calls == 1)


def test_enabled_logs_and_survives_a_failed_warm_up(tmp_path):
    fake = FakeProvider()
    fake.fail_load = True
    settings = _settings(tmp_path, warm_up_on_start=True)
    app = create_app(settings, provider_service_factory=lambda _: registry(fake))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert _wait_until(lambda: fake.load_calls == 1)
        # The app itself must still be usable - a warm-up failure is only
        # logged, never fatal to the process.
        assert client.get("/api/health").status_code == 200
