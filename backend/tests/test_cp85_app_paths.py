"""CP8.5 production-data boundary regressions (no real user data touched)."""
from __future__ import annotations

from pathlib import Path

from backend.config import Settings
from backend.core.app_paths import resolve_app_paths
from backend.persistence import Repository


def test_windows_production_root_is_localappdata_and_cwd_independent(monkeypatch, tmp_path):
    env = {"LOCALAPPDATA": r"C:\Users\Example\AppData\Local"}
    first = resolve_app_paths(env, platform_name="nt")
    monkeypatch.chdir(tmp_path)
    second = resolve_app_paths(env, platform_name="nt")
    assert first.root == second.root
    assert "Voca Basic" in str(first.root)
    assert "Tool Dich Cho Khach" not in str(first.root)


def test_explicit_data_root_override_and_mutable_paths_are_separate(tmp_path):
    root = tmp_path / "isolated-data"
    paths = resolve_app_paths({"LOCAL_AI_DATA_ROOT": str(root)}, platform_name="nt")
    paths.ensure(paths.audio_dir, paths.reference_audio_dir, paths.temp_dir, paths.logs_dir, paths.settings_dir)
    assert paths.root == root.resolve()
    assert paths.audio_dir != paths.reference_audio_dir != paths.temp_dir
    assert all(item.is_dir() for item in (paths.audio_dir, paths.reference_audio_dir, paths.temp_dir, paths.logs_dir))


def test_settings_and_profile_metadata_survive_repository_restart(tmp_path):
    paths = resolve_app_paths({"LOCAL_AI_DATA_ROOT": str(tmp_path)}, platform_name="nt")
    settings = Settings(app_data_dir=paths.root, output_dir=paths.audio_dir, database_path=paths.database,
                        reference_audio_dir=paths.reference_audio_dir, temp_dir=paths.temp_dir)
    first = Repository(settings)
    reference = paths.reference_audio_dir / "safe-id.wav"
    reference.parent.mkdir(parents=True); reference.write_bytes(b"managed")
    first.put("settings", "app_settings", {"debug_logs": False})
    first.put("voice_profiles", "safe-id", {"profile_id": "safe-id", "reference_path": str(reference)})
    second = Repository(settings)
    assert second.get_setting("app_settings")["debug_logs"] is False
    assert second.profiles()[0]["reference_path"] == str(reference)
    assert reference.is_file() and reference.is_relative_to(paths.root)


def test_data_root_is_not_an_immutable_packaged_resource(tmp_path):
    app_root, data_root = tmp_path / "Program Files" / "Voca Basic", tmp_path / "user-data"
    paths = resolve_app_paths({"LOCAL_AI_DATA_ROOT": str(data_root)}, platform_name="nt")
    assert not paths.root.is_relative_to(app_root)
    assert not paths.database.is_relative_to(app_root)
