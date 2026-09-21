from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _stager():
    path = Path(__file__).resolve().parents[2] / "scripts" / "stage_cp82_runtimes.py"
    spec = importlib.util.spec_from_file_location("cp82_stager", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("contents, expected", [
    ("cuda = '12.8'\n", "12.8"),
    ("cuda: Optional[str] = '12.4'\n", "12.4"),
])
def test_cuda_manifest_parser_supports_generated_torch_syntax(tmp_path, contents, expected):
    version = tmp_path / "version.py"
    version.write_text(contents, encoding="utf-8")
    assert _stager()._cuda_build(version) == expected


def test_cuda_manifest_parser_fails_clearly_when_metadata_is_absent(tmp_path):
    version = tmp_path / "version.py"
    version.write_text("git_version = 'abc'\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="Unable to determine CUDA build"):
        _stager()._cuda_build(version)
