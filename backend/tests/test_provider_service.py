"""Generic provider-registry behavior after CP1."""
import pytest
from backend.errors import ApplicationError, ErrorCode
from backend.services.provider_service import ProviderService
from backend.tests.provider_fakes import FakeProvider, TEST_PROVIDER_ID

def test_empty_registry_is_controlled():
    service = ProviderService()
    assert service.status().primary is None and service.status().providers == []
    with pytest.raises(ApplicationError) as error: service.get_primary_provider()
    assert error.value.code == ErrorCode.PROVIDER_NOT_FOUND

def test_generic_provider_registration_and_availability():
    service = ProviderService(); provider = FakeProvider()
    service.register(provider, device="test", available=True); service.select_primary(TEST_PROVIDER_ID)
    assert service.get_primary_provider() is provider
    assert service.status().primary == TEST_PROVIDER_ID

def test_unavailable_generic_provider_is_rejected():
    service = ProviderService(); service.register(FakeProvider(), device="test", available=False); service.select_primary(TEST_PROVIDER_ID)
    with pytest.raises(ApplicationError) as error: service.get_primary_provider()
    assert error.value.code == ErrorCode.PROVIDER_UNAVAILABLE
