"""App-scoped registry/lifecycle. No provider construction until lifespan startup.

One Condition protects application state, load admission and shutdown. Model
operations run outside it, retaining the adapter's own RLock. Status never waits
on the model lock and can observe LOADING/UNLOADING without triggering work.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import logging
from threading import Condition, RLock
from typing import TYPE_CHECKING

from backend.config import OMNIVOICE_PROVIDER_ID, Settings
from backend.errors import ApplicationError, ErrorCode
from backend.schemas.providers import ProviderState, ProviderStatus, ProvidersResponse, VerifiedLanguage

if TYPE_CHECKING:
    from providers.base import ManagedTTSProvider

logger = logging.getLogger("backend.providers")
BUSY = {ProviderState.LOADING, ProviderState.UNLOADING}


@dataclass
class _Entry:
    provider: ManagedTTSProvider
    status: ProviderStatus


class ProviderService:
    def __init__(self):
        self._entries: dict[str, _Entry] = {}
        self._primary: str | None = None
        self._condition = Condition()
        self.inference_lock = RLock()
        self._closing = False
        self._shutdown_complete = False

    def _entry(self, provider_id: str) -> _Entry:
        try:
            return self._entries[provider_id]
        except KeyError:
            raise ApplicationError(ErrorCode.PROVIDER_NOT_FOUND) from None

    def _check_open(self):
        if self._closing:
            raise ApplicationError(ErrorCode.PROVIDER_NOT_READY)

    def register(self, provider: ManagedTTSProvider, *, device: str, available: bool = True):
        with self._condition:
            self._check_open()
            provider_id = provider.provider_name()
            if provider_id in self._entries:
                if self._entries[provider_id].provider is provider:
                    return
                raise ApplicationError(ErrorCode.PROVIDER_NOT_READY)
            capabilities = provider.capabilities()
            loaded = bool(provider.is_loaded())
            self._entries[provider_id] = _Entry(provider, ProviderStatus(
                id=provider_id, available=available, loaded=loaded, device=device,
                state=(ProviderState.UNAVAILABLE if not available else
                       ProviderState.READY if loaded else ProviderState.NOT_LOADED),
                languages=tuple(capabilities["verified_languages"]),
                language_metadata=tuple(VerifiedLanguage.model_validate(item)
                                        for item in capabilities["language_metadata"]),
                experimental_languages_enabled=capabilities["experimental_languages_enabled"],
                production_ready=capabilities["production_ready"],
            ))
            logger.info("provider_registered provider=%s state=%s", provider_id,
                        self._entries[provider_id].status.state.value)

    def select_primary(self, provider_id: str):
        with self._condition:
            self._check_open()
            self._entry(provider_id)
            self._primary = provider_id

    def get_provider(self, provider_id: str) -> ManagedTTSProvider:
        with self._condition:
            self._check_open()
            entry = self._entry(provider_id)
            if not entry.status.available:
                raise ApplicationError(ErrorCode.PROVIDER_UNAVAILABLE)
            return entry.provider

    def get_primary_provider(self) -> ManagedTTSProvider:
        with self._condition:
            if self._primary is None:
                raise ApplicationError(ErrorCode.PROVIDER_NOT_FOUND)
            return self.get_provider(self._primary)

    def status(self) -> ProvidersResponse:
        with self._condition:
            if self._primary is None:
                raise ApplicationError(ErrorCode.PROVIDER_NOT_FOUND)
            return ProvidersResponse(primary=self._primary,
                                     providers=[entry.status for entry in self._entries.values()])

    def _transition(self, entry: _Entry, state: ProviderState, *, loaded: bool | None = None,
                    error: ErrorCode | None = None):
        # Caller holds the Condition. Never serialize the provider or its health dict.
        entry.status = entry.status.model_copy(update={
            "state": state, "loaded": entry.status.loaded if loaded is None else loaded,
            "error_code": error.value if error else None,
        })
        logger.info("provider_transition provider=%s state=%s", entry.status.id, state.value)
        self._condition.notify_all()

    @staticmethod
    def _loaded_after_failure(entry: _Entry) -> bool:
        try:
            return bool(entry.provider.is_loaded())
        except Exception:
            logger.exception("provider_state_check_failed provider=%s", entry.status.id)
            return entry.status.loaded

    def ensure_primary_provider_loaded(self, *, retry: bool = False) -> ManagedTTSProvider:
        with self._condition:
            provider_id = self._primary
        if provider_id is None:
            raise ApplicationError(ErrorCode.PROVIDER_NOT_FOUND)
        return self.ensure_loaded(provider_id, retry=retry)

    def ensure_loaded(self, provider_id: str, *, retry: bool = False) -> ManagedTTSProvider:
        with self._condition:
            self._check_open()
            entry = self._entry(provider_id)
            waited = False
            while entry.status.state in BUSY:
                waited = True
                self._condition.wait()
                self._check_open()
            if not entry.status.available:
                raise ApplicationError(ErrorCode.PROVIDER_UNAVAILABLE)
            if entry.status.state == ProviderState.READY:
                return entry.provider
            if entry.status.state == ProviderState.ERROR and (not retry or waited):
                # Concurrent waiters see the same failure; never create a retry storm.
                raise ApplicationError(ErrorCode(entry.status.error_code or ErrorCode.PROVIDER_LOAD_FAILED.value))
            self._transition(entry, ProviderState.LOADING)
        try:
            entry.provider.load()
            if not entry.provider.is_loaded():
                raise RuntimeError("Provider load returned without a loaded model")
        except Exception:
            logger.exception("provider_load_failed provider=%s", provider_id)
            loaded = self._loaded_after_failure(entry)
            with self._condition:
                self._transition(entry, ProviderState.ERROR, loaded=loaded, error=ErrorCode.PROVIDER_LOAD_FAILED)
            raise ApplicationError(ErrorCode.PROVIDER_LOAD_FAILED) from None
        with self._condition:
            self._transition(entry, ProviderState.READY, loaded=True)
            self._check_open()
            return entry.provider

    def unload(self, provider_id: str):
        with self.inference_lock:
            self._unload(provider_id, shutdown=False)

    def _unload(self, provider_id: str, *, shutdown: bool):
        with self._condition:
            if not shutdown:
                self._check_open()
            entry = self._entry(provider_id)
            while entry.status.state in BUSY:
                self._condition.wait()
                if not shutdown:
                    self._check_open()
            if entry.status.state in {ProviderState.NOT_LOADED, ProviderState.UNAVAILABLE}:
                return
            self._transition(entry, ProviderState.UNLOADING)
        try:
            entry.provider.unload()
            if entry.provider.is_loaded():
                raise RuntimeError("Provider unload left model loaded")
        except Exception:
            logger.exception("provider_unload_failed provider=%s", provider_id)
            loaded = self._loaded_after_failure(entry)
            with self._condition:
                self._transition(entry, ProviderState.ERROR, loaded=loaded, error=ErrorCode.PROVIDER_NOT_READY)
            raise ApplicationError(ErrorCode.PROVIDER_NOT_READY) from None
        with self._condition:
            self._transition(entry, ProviderState.NOT_LOADED, loaded=False)

    def shutdown(self):
        with self._condition:
            if self._closing:
                while not self._shutdown_complete:
                    self._condition.wait()
                return
            self._closing = True
            self._condition.notify_all()
            provider_ids = list(self._entries)
        try:
            for provider_id in provider_ids:
                try:
                    self._unload(provider_id, shutdown=True)
                except Exception:
                    # Error remains observable; cleanup failure must not crash lifespan.
                    logger.exception("provider_shutdown_cleanup_failed provider=%s", provider_id)
        finally:
            with self._condition:
                self._shutdown_complete = True
                self._condition.notify_all()


def create_provider_service(settings: Settings) -> ProviderService:
    # Adapter import/construction: numpy and metadata only, no Torch/model load.
    from providers.omnivoice import OmniVoiceProvider

    provider = OmniVoiceProvider(device=settings.omnivoice_device)
    if provider.provider_name() != OMNIVOICE_PROVIDER_ID:
        raise ApplicationError(ErrorCode.PROVIDER_NOT_FOUND)
    service = ProviderService()
    available = all(importlib.util.find_spec(name) is not None for name in ("torch", "omnivoice"))
    service.register(provider, device=settings.omnivoice_device, available=available)
    service.select_primary(settings.primary_tts_provider)
    return service
