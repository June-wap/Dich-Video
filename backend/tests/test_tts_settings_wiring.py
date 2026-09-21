"""Generic settings propagation; provider routing is intentionally absent in CP1."""
from backend.config import Settings
from backend.services.app_settings_service import AppSettingsService

def test_unsaved_settings_keep_generic_defaults(tmp_path):
    settings = Settings(app_data_dir=tmp_path, output_dir=tmp_path / "audio")
    service = AppSettingsService(settings)
    assert service.resolve_effective_settings(settings) == settings
    assert service.resolve_retry_count() == 1
    assert service.resolve_num_steps() is None
    assert service.resolve_silence_trim() is False
