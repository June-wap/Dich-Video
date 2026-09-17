"""Settings > General/Audio/Performance/Storage/Advanced tabs (Task 1/7):
backend/schemas/app_settings.py, backend/services/app_settings_service.py,
backend/api/app_settings.py. Mirrors test_backend.py's harness style.

Deliberately does NOT touch backend/api/settings.py (Gemini BYOK translation
key) - that has its own tests and its own security handling.
"""
import dataclasses
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.services.app_settings_service import SETTINGS_KEY, AppSettingsService
from backend.services.system_service import RuntimeInfo, SystemService
from backend.tests.provider_fakes import registry


@pytest.fixture
def harness(tmp_path):
    settings = Settings(output_dir=tmp_path / "outputs", database_path=tmp_path / "app.sqlite3")
    probe = Mock(return_value=RuntimeInfo("3.12.10", "2.8.0+cu128", True, "test GPU"))
    providers = registry()
    service = SystemService(providers, probe)
    app = create_app(settings=settings, service_factory=lambda _: service,
                     provider_service_factory=lambda _: providers)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, settings


# ---------------------------------------------------------------------------
# GET returns real, honest defaults - not the frontend's old hardcoded values
# ---------------------------------------------------------------------------

def test_get_returns_defaults_matching_prior_hardcoded_behavior(harness):
    client, settings = harness
    response = client.get("/api/settings/app")
    assert response.status_code == 200
    data = response.json()
    assert data["app_lang"] == "vi"
    assert data["app_theme"] == "light"
    assert data["device"] == "gpu"
    assert data["retry_count"] == 2
    assert data["num_steps"] == 16
    assert data["output_format"] == "wav+mp3"
    # Real values, not the old frontend's hardcoded placeholder strings.
    assert data["actual_db_path"]
    assert data["actual_output_dir"] == str(settings.output_dir)
    assert data["output_dir_bytes"] == 0  # nothing generated yet
    assert "sqlite_wal" not in data  # removed from the UI entirely - see schema docstring


# ---------------------------------------------------------------------------
# POST persists across requests (and would survive a restart - same DB file)
# ---------------------------------------------------------------------------

def test_save_persists_and_is_read_back(harness):
    client, _ = harness
    payload = {
        "app_lang": "en", "app_theme": "dark", "notify_completion": False, "notify_errors": True,
        "output_format": "mp3", "pause_policy_ms": 600, "silence_trim": False, "output_dir": None,
        "device": "cpu", "quality_preset": "high", "retry_count": 3,
        "num_steps": 32, "debug_logs": True,
    }
    saved = client.post("/api/settings/app", json=payload)
    assert saved.status_code == 200
    assert saved.json()["app_lang"] == "en"
    assert saved.json()["device"] == "cpu"

    reread = client.get("/api/settings/app")
    assert reread.json()["app_theme"] == "dark"
    assert reread.json()["retry_count"] == 3
    assert reread.json()["num_steps"] == 32


def test_extra_fields_rejected(harness):
    client, _ = harness
    response = client.post("/api/settings/app", json={"unknown_field": 1})
    assert response.status_code == 422


def test_out_of_range_values_rejected(harness):
    client, _ = harness
    response = client.post("/api/settings/app", json={"retry_count": 99})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Storage tab: real disk usage, not a fake "348 MB"
# ---------------------------------------------------------------------------

def test_output_dir_bytes_reflects_real_files_on_disk(harness):
    client, settings = harness
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    (settings.output_dir / "a.wav").write_bytes(b"x" * 100)
    (settings.output_dir / "b.wav").write_bytes(b"y" * 250)
    response = client.get("/api/settings/app")
    assert response.json()["output_dir_bytes"] == 350


def test_custom_output_dir_bytes_computed_for_the_configured_directory(harness, tmp_path):
    client, _ = harness
    custom = tmp_path / "custom_audio"
    custom.mkdir()
    (custom / "c.wav").write_bytes(b"z" * 40)
    client.post("/api/settings/app", json={"output_dir": str(custom)})
    response = client.get("/api/settings/app")
    assert response.json()["actual_output_dir"] == str(custom)
    assert response.json()["output_dir_bytes"] == 40


# ---------------------------------------------------------------------------
# resolve_effective_settings(): Task 6's device override, applied only at
# startup (never hot-swapped) - see backend/main.py's lifespan.
# ---------------------------------------------------------------------------

def test_resolve_effective_settings_overrides_device_only_when_cpu_chosen(tmp_path):
    settings = Settings(output_dir=tmp_path / "out", database_path=tmp_path / "settings.sqlite3")
    service = AppSettingsService(settings)

    # Default ("gpu") leaves the configured settings untouched.
    assert service.resolve_effective_settings(settings) is settings

    from backend.schemas.app_settings import AppSettings
    service.save(AppSettings(device="cpu"))
    effective = service.resolve_effective_settings(settings)
    assert effective.omnivoice_device == "cpu"
    assert effective is not settings
    # Nothing else about the settings object changed.
    assert effective == dataclasses.replace(settings, omnivoice_device="cpu")


# ---------------------------------------------------------------------------
# resolve_* helpers TTSService/LongFormTTSService call per-job
# ---------------------------------------------------------------------------

def test_resolve_helpers_preserve_legacy_behavior_when_nothing_ever_saved(tmp_path):
    """A customer who has never opened Settings at all - including right
    after a fresh install, before AppSettingsService's own __init__ has
    written anything - must get IDENTICAL behavior to before this endpoint
    existed: single-attempt synthesis (no retry loop) and the provider's own
    per-mode num_step default (16 for normal TTS, 24 for voice cloning - see
    prototype/providers/omnivoice.py), not a uniform retry_count=2/num_steps=16
    the instant AppSettingsService is constructed. See this module's schema
    docstring and resolve_retry_count()/resolve_num_steps()'s own comments.
    """
    settings = Settings(output_dir=tmp_path / "out", database_path=tmp_path / "s.sqlite3")
    service = AppSettingsService(settings)
    assert service.resolve_retry_count() == 1
    assert service.resolve_num_steps() is None
    assert service.resolve_silence_trim() is False
    assert service.resolve_output_dir() == settings.output_dir
    assert service.resolve_debug_logs() is False


def test_resolve_silence_trim_only_turns_on_after_an_explicit_save(tmp_path):
    """silence_trim's schema default is True, but - like retry_count and
    num_steps above - that must only take effect once the customer has
    actually saved Settings at least once, not from process start.
    """
    from backend.schemas.app_settings import AppSettings

    settings = Settings(output_dir=tmp_path / "out", database_path=tmp_path / "s3.sqlite3")
    service = AppSettingsService(settings)
    assert service.resolve_silence_trim() is False

    service.save(AppSettings(silence_trim=True))
    assert service.resolve_silence_trim() is True

    service.save(AppSettings(silence_trim=False))
    assert service.resolve_silence_trim() is False


def test_resolve_helpers_fall_back_to_schema_defaults_once_something_is_saved_but_corrupt(tmp_path):
    """Once the user HAS saved Settings at least once (so the invariant above
    no longer applies), a corrupted/out-of-range value for one field falls
    back to a safe value instead of crashing - out-of-range retry_count
    behaves like the schema's own default (2); out-of-range num_steps still
    prefers None (the provider's own per-mode default) over guessing a
    number, for the same reason resolve_num_steps() never guesses 16.
    """
    settings = Settings(output_dir=tmp_path / "out", database_path=tmp_path / "s2.sqlite3")
    service = AppSettingsService(settings)
    service._db.put("settings", SETTINGS_KEY, {"retry_count": "not-a-number", "num_steps": 999})
    assert service.resolve_retry_count() == 2
    assert service.resolve_num_steps() is None


# ---------------------------------------------------------------------------
# Debug Logging really changes the "backend" logger's effective level
# ---------------------------------------------------------------------------

def test_debug_logs_toggle_changes_real_logger_level(harness):
    import logging
    client, _ = harness
    logger = logging.getLogger("backend")
    client.post("/api/settings/app", json={"debug_logs": True})
    assert logger.level == logging.DEBUG
    client.post("/api/settings/app", json={"debug_logs": False})
    assert logger.level == logging.INFO  # Settings().log_level default
