from pathlib import Path

import pytest

import backend.config as config
from backend.config import Settings


def test_chatterbox_runtime_can_be_supplied_without_a_development_venv(monkeypatch, tmp_path):
    executable = tmp_path / "runtime-chatterbox" / "python.exe"
    executable.parent.mkdir()
    executable.touch()
    monkeypatch.setenv("LOCAL_AI_CHATTERBOX_PYTHON", str(executable))
    assert Settings.from_env().chatterbox_python == executable


def _portable_layout(monkeypatch, tmp_path, *, sibling: bool = True):
    main = tmp_path / "cp82" / "runtime-main"
    executable = main / "python.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    if sibling:
        worker = tmp_path / "cp82" / "runtime-chatterbox" / "python.exe"
        worker.parent.mkdir()
        worker.touch()
    else:
        worker = tmp_path / "cp82" / "runtime-chatterbox" / "python.exe"
    monkeypatch.setattr(config.sys, "prefix", str(main))
    monkeypatch.setattr(config.sys, "executable", str(executable))
    return executable, worker


def test_portable_main_resolves_staged_sibling_without_override(monkeypatch, tmp_path):
    _main, worker = _portable_layout(monkeypatch, tmp_path)
    monkeypatch.delenv("LOCAL_AI_CHATTERBOX_PYTHON", raising=False)
    assert Settings.from_env().chatterbox_python == worker


def test_portable_missing_sibling_fails_explicitly(monkeypatch, tmp_path):
    _portable_layout(monkeypatch, tmp_path, sibling=False)
    monkeypatch.delenv("LOCAL_AI_CHATTERBOX_PYTHON", raising=False)
    with pytest.raises(RuntimeError, match="PORTABLE_CHATTERBOX_RUNTIME_MISSING"):
        Settings.from_env()


def test_portable_resolution_does_not_depend_on_cwd(monkeypatch, tmp_path):
    _main, worker = _portable_layout(monkeypatch, tmp_path)
    monkeypatch.chdir(tmp_path / "unrelated") if (tmp_path / "unrelated").exists() else (tmp_path / "unrelated").mkdir()
    monkeypatch.chdir(tmp_path / "unrelated")
    monkeypatch.delenv("LOCAL_AI_CHATTERBOX_PYTHON", raising=False)
    assert Settings.from_env().chatterbox_python == worker


def test_source_mode_requires_explicit_staged_worker_path(monkeypatch, tmp_path):
    source_python = tmp_path / "source-python.exe"
    source_python.touch()
    monkeypatch.setattr(config.sys, "prefix", str(tmp_path / "source-venv"))
    monkeypatch.setattr(config.sys, "executable", str(source_python))
    monkeypatch.delenv("LOCAL_AI_CHATTERBOX_PYTHON", raising=False)
    with pytest.raises(RuntimeError, match="CHATTERBOX_RUNTIME_UNAVAILABLE"):
        Settings.from_env()
