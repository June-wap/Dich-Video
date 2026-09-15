from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from backend.config import OMNIVOICE_PROVIDER_ID, Settings
from backend.errors import ApplicationError, ErrorCode
from backend.main import create_app
from backend.schemas.providers import ProviderState
from backend.services.provider_service import ProviderService, create_provider_service
from backend.services.system_service import RuntimeInfo, SystemService
from backend.tests.provider_fakes import FakeProvider, registry
from core.languages import VERIFIED_LANGUAGE_IDS, language_metadata, language_status


def state(service):
    return service.status().providers[0]


def expect_error(code, call):
    with pytest.raises(ApplicationError) as caught:
        call()
    assert caught.value.code == code
    assert "secret" not in str(caught.value)


def test_bootstrap_one_primary_adapter_and_never_loads(monkeypatch):
    from providers import omnivoice
    fake = FakeProvider()
    constructor = Mock(return_value=fake)
    monkeypatch.setattr(omnivoice, "OmniVoiceProvider", constructor)
    app = create_app()
    constructor.assert_not_called()
    with TestClient(app, base_url="http://127.0.0.1") as client:
        service = app.state.provider_service
        for _ in range(3):
            response = client.get("/api/providers/status")
            assert response.status_code == 200
            data = response.json()
            assert data["primary"] == OMNIVOICE_PROVIDER_ID
            assert len(data["providers"]) == 1
            assert data["providers"][0]["state"] == "NOT_LOADED"
            assert data["providers"][0]["loaded"] is False
            assert data["providers"][0]["available"] is True
            assert service.get_primary_provider() is fake
        constructor.assert_called_once_with(device="cuda:0")
        assert fake.load_calls == 0
    assert fake.unload_calls == 0
    assert app.state.provider_service is None


def test_capabilities_preserve_verified_language_scope():
    service = registry()
    metadata = state(service)
    assert metadata.languages == VERIFIED_LANGUAGE_IDS
    assert [item.model_dump() for item in metadata.language_metadata] == language_metadata()
    assert metadata.experimental_languages_enabled is False
    assert metadata.production_ready is False
    assert {language_status(code) for code in metadata.languages} == {"VERIFIED"}
    assert "model_path" not in metadata.model_dump()


def test_unknown_primary_does_not_fallback():
    expect_error(ErrorCode.PROVIDER_NOT_FOUND, lambda:
                 create_provider_service(Settings(primary_tts_provider="unknown")))


def test_lookup_and_duplicate_registration():
    service = registry()
    provider = service.get_primary_provider()
    service.register(provider, device="cuda:0")
    assert len(service.status().providers) == 1
    expect_error(ErrorCode.PROVIDER_NOT_READY, lambda: service.register(FakeProvider(), device="cuda:0"))
    expect_error(ErrorCode.PROVIDER_NOT_FOUND, lambda: service.get_provider("missing"))


def test_no_primary_selected_is_normalized():
    service = ProviderService()
    for call in (service.status, service.get_primary_provider, service.ensure_primary_provider_loaded):
        expect_error(ErrorCode.PROVIDER_NOT_FOUND, call)


def test_unavailable_provider_never_loads_or_falls_back():
    service = registry(available=False)
    assert state(service).state == ProviderState.UNAVAILABLE
    expect_error(ErrorCode.PROVIDER_UNAVAILABLE, service.get_primary_provider)
    expect_error(ErrorCode.PROVIDER_UNAVAILABLE, service.ensure_primary_provider_loaded)
    service.shutdown()
    assert state(service).loaded is False


def test_missing_package_marks_unavailable(monkeypatch):
    monkeypatch.setattr("backend.services.provider_service.importlib.util.find_spec", lambda _: None)
    service = create_provider_service(Settings())
    assert state(service).available is False
    assert state(service).state == ProviderState.UNAVAILABLE


def test_repeated_ensure_reuses_one_load_and_same_instance():
    fake = FakeProvider()
    service = registry(fake)
    for _ in range(5):
        assert service.ensure_primary_provider_loaded() is fake
    assert fake.load_calls == 1
    assert fake.health_check()["load_count"] == 1
    assert state(service).state == ProviderState.READY and state(service).loaded


def test_loading_state_is_visible_and_concurrent_ensure_calls_load_once():
    fake = FakeProvider()
    service = registry(fake)
    started, release = Event(), Event()
    original_load = fake.load
    def load():
        started.set()
        assert release.wait(5)
        return original_load()
    fake.load = load
    barrier = Barrier(6)
    def ensure():
        barrier.wait(timeout=5)
        return service.ensure_primary_provider_loaded()
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(ensure) for _ in range(6)]
        try:
            assert started.wait(5)
            assert state(service).state == ProviderState.LOADING
            assert state(service).loaded is False
        finally:
            release.set()
        assert all(future.result(timeout=5) is fake for future in futures)
    assert fake.load_calls == 1
    assert state(service).state == ProviderState.READY


def test_failure_is_sticky_until_explicit_retry():
    fake = FakeProvider()
    fake.fail_load = True
    service = registry(fake)
    expect_error(ErrorCode.PROVIDER_LOAD_FAILED, service.ensure_primary_provider_loaded)
    assert state(service).state == ProviderState.ERROR
    assert state(service).error_code == "PROVIDER_LOAD_FAILED"
    assert state(service).loaded is False
    fake.fail_load = False
    expect_error(ErrorCode.PROVIDER_LOAD_FAILED, service.ensure_primary_provider_loaded)
    assert fake.load_calls == 1
    assert service.ensure_primary_provider_loaded(retry=True) is fake
    assert fake.load_calls == 2
    assert state(service).state == ProviderState.READY
    assert state(service).error_code is None


def test_concurrent_load_failure_is_shared_without_automatic_retries():
    fake = FakeProvider()
    fake.fail_load = True
    service = registry(fake)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(service.ensure_primary_provider_loaded) for _ in range(5)]
        for future in futures:
            expect_error(ErrorCode.PROVIDER_LOAD_FAILED, lambda: future.result(timeout=5))
    assert fake.load_calls == 1


def test_load_without_actual_loaded_state_is_an_error():
    fake = FakeProvider()
    fake.load = Mock(return_value=fake)
    service = registry(fake)
    expect_error(ErrorCode.PROVIDER_LOAD_FAILED, service.ensure_primary_provider_loaded)
    assert state(service).state == ProviderState.ERROR


def test_unload_transitions_and_can_load_again():
    fake = FakeProvider()
    service = registry(fake)
    service.ensure_primary_provider_loaded()
    original_unload = fake.unload
    def unload():
        assert state(service).state == ProviderState.UNLOADING
        original_unload()
    fake.unload = unload
    service.unload(OMNIVOICE_PROVIDER_ID)
    assert state(service).state == ProviderState.NOT_LOADED and not state(service).loaded
    service.unload(OMNIVOICE_PROVIDER_ID)
    assert fake.unload_calls == 1
    service.ensure_primary_provider_loaded()
    assert fake.load_calls == 2


def test_shutdown_unloads_once_and_refuses_new_loads():
    fake = FakeProvider()
    service = registry(fake)
    service.ensure_primary_provider_loaded()
    service.shutdown()
    service.shutdown()
    assert fake.unload_calls == 1
    assert state(service).state == ProviderState.NOT_LOADED
    expect_error(ErrorCode.PROVIDER_NOT_READY, service.ensure_primary_provider_loaded)
    expect_error(ErrorCode.PROVIDER_NOT_READY, service.get_primary_provider)


def test_shutdown_handles_load_failure_and_partial_model_cleanup():
    fake = FakeProvider()
    def partial_load():
        fake._model = object()
        raise RuntimeError("partial load")
    fake.load = partial_load
    service = registry(fake)
    expect_error(ErrorCode.PROVIDER_LOAD_FAILED, service.ensure_primary_provider_loaded)
    assert state(service).loaded is True
    service.shutdown()
    assert fake.unload_calls == 1
    assert not fake.is_loaded()


def test_shutdown_cleanup_failure_is_safe_and_remains_error():
    fake = FakeProvider()
    service = registry(fake)
    service.ensure_primary_provider_loaded()
    fake.fail_unload = True
    service.shutdown()
    assert state(service).state == ProviderState.ERROR
    assert state(service).loaded is True
    assert state(service).error_code == "PROVIDER_NOT_READY"
    expect_error(ErrorCode.PROVIDER_NOT_READY, service.ensure_primary_provider_loaded)


def test_shutdown_waits_for_loading_and_blocks_new_requests():
    fake = FakeProvider()
    service = registry(fake)
    started, release, shutdown_started = Event(), Event(), Event()
    load, unload = fake.load, service._unload
    def delayed_load():
        started.set()
        assert release.wait(5)
        return load()
    def signal_shutdown(*args, **kwargs):
        shutdown_started.set()
        return unload(*args, **kwargs)
    fake.load = delayed_load
    service._unload = signal_shutdown
    with ThreadPoolExecutor(max_workers=2) as pool:
        loading = pool.submit(service.ensure_primary_provider_loaded)
        try:
            assert started.wait(5)
            closing = pool.submit(service.shutdown)
            assert shutdown_started.wait(5)
            expect_error(ErrorCode.PROVIDER_NOT_READY, service.get_primary_provider)
        finally:
            release.set()
        expect_error(ErrorCode.PROVIDER_NOT_READY, lambda: loading.result(timeout=5))
        closing.result(timeout=5)
    assert fake.load_calls == 1 and fake.unload_calls == 1
    assert state(service).state == ProviderState.NOT_LOADED


def test_system_status_tracks_live_state_after_hardware_cache():
    fake = FakeProvider()
    service = registry(fake)
    hardware = Mock(return_value=RuntimeInfo("3.12.10", "2.8.0+cu128", True, "GPU"))
    app = create_app(provider_service_factory=lambda _: service,
                     service_factory=lambda providers: SystemService(providers, hardware))
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/system/status").json()["provider_state"] == "NOT_LOADED"
        service.ensure_primary_provider_loaded()
        data = client.get("/api/system/status").json()
        assert data["primary_provider"] == OMNIVOICE_PROVIDER_ID
        assert data["omnivoice_model_loaded"] is True and data["provider_state"] == "READY"
        service.unload(OMNIVOICE_PROVIDER_ID)
        assert client.get("/api/system/status").json()["omnivoice_model_loaded"] is False
        fake.fail_load = True
        expect_error(ErrorCode.PROVIDER_LOAD_FAILED, service.ensure_primary_provider_loaded)
        data = client.get("/api/system/status").json()
        assert data["provider_state"] == "ERROR" and data["status"] == "degraded"
        hardware.assert_called_once()


def test_lifespan_unloads_ready_provider():
    fake = FakeProvider()
    service = registry(fake)
    app = create_app(provider_service_factory=lambda _: service)
    with TestClient(app, base_url="http://127.0.0.1"):
        service.ensure_primary_provider_loaded()
    assert fake.unload_calls == 1
    assert app.state.provider_service is None


def test_system_service_startup_failure_still_cleans_provider():
    fake = FakeProvider()
    service = registry(fake)
    def fail_system(_):
        service.ensure_primary_provider_loaded()
        raise RuntimeError("system startup failed")
    app = create_app(provider_service_factory=lambda _: service, service_factory=fail_system)
    with pytest.raises(RuntimeError, match="system startup failed"):
        with TestClient(app, base_url="http://127.0.0.1"):
            pass
    assert fake.unload_calls == 1
    assert app.state.provider_service is None


@pytest.mark.parametrize("code,status_code", [(ErrorCode.PROVIDER_NOT_FOUND, 404),
    (ErrorCode.PROVIDER_UNAVAILABLE, 503), (ErrorCode.PROVIDER_LOAD_FAILED, 503),
    (ErrorCode.PROVIDER_NOT_READY, 503)])
def test_provider_errors_use_existing_http_contract(code, status_code):
    app = create_app(provider_service_factory=lambda _: registry())
    @app.get("/test-provider-error")
    def fail():
        raise ApplicationError(code)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/test-provider-error")
        assert response.status_code == status_code
        assert response.json()["ok"] is False
        assert response.json()["error"]["code"] == code.value


def test_load_error_response_hides_original_exception():
    fake = FakeProvider()
    fake.fail_load = True
    service = registry(fake)
    app = create_app(provider_service_factory=lambda _: service)
    @app.get("/test-only-load")
    def load():
        service.ensure_primary_provider_loaded()
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.get("/test-only-load")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "PROVIDER_LOAD_FAILED"
        assert "secret" not in response.text and "traceback" not in response.text.lower()


def test_device_override_has_no_cpu_fallback(monkeypatch):
    monkeypatch.setenv("LOCAL_AI_OMNIVOICE_DEVICE", "cuda:1")
    assert Settings.from_env().omnivoice_device == "cuda:1"
    with pytest.raises(ValueError, match="no CPU fallback"):
        Settings(omnivoice_device="cpu")


def test_real_adapter_api_reuses_load_once_without_real_model(monkeypatch):
    from providers.omnivoice import OmniVoiceProvider
    provider = OmniVoiceProvider()
    model = Mock(sampling_rate=24000)
    loader = Mock(return_value=model)
    monkeypatch.setattr(provider, "_load_model", loader)
    service = registry(provider)
    assert service.ensure_primary_provider_loaded() is provider
    assert service.ensure_primary_provider_loaded() is provider
    assert provider.is_loaded()
    loader.assert_called_once()
    assert provider.health_check()["load_count"] == 1
    service.shutdown()
    assert not provider.is_loaded()
