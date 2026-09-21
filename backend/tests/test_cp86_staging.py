"""Focused regression checks for the CP8.6 clean-staging contract.

These checks deliberately inspect the release script instead of requiring the
large approved runtime/model seed to be present in a unit-test environment.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cp86_stage_requires_explicit_approved_seed_and_verifies_models():
    script = (ROOT / "scripts" / "stage_cp86_release.ps1").read_text(encoding="utf-8")

    assert "Specify -SeedRoot or LOCAL_AI_RELEASE_SEED_ROOT" in script
    assert "cp82\\runtime-main" in script
    assert "cp82\\runtime-chatterbox" in script
    assert "cp81b\\models" in script
    assert "function Assert-ModelManifest" in script
    assert "Model symlink is forbidden" in script
    assert "Approved model hash mismatch" in script
    assert "Assert-ModelManifest (Join-Path $Destination 'models')" in script


def test_cp86_stage_injects_current_production_app_and_excludes_app_test_artifacts():
    script = (ROOT / "scripts" / "stage_cp86_release.ps1").read_text(encoding="utf-8")

    assert "foreach ($item in 'backend','requirements-backend.txt')" in script
    assert "runtime-main\\app" in script
    assert "-Filter '__pycache__'" in script
    assert "-Filter 'tests'" in script
    assert "backend/core/app_paths.py" in script
    assert "backend/services/capability_service.py" in script


def test_cp86_stage_has_no_hard_coded_development_machine_path():
    script = (ROOT / "scripts" / "stage_cp86_release.ps1").read_text(encoding="utf-8")

    assert "D:\\" not in script
    assert "F:\\" not in script
