"""CP8.1B staging manifest guards; actual copy/synthesis gates are run separately."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def _stager_module():
    path = Path(__file__).resolve().parents[2] / "scripts" / "stage_cp81b_models.py"
    spec = importlib.util.spec_from_file_location("cp81b_stager", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cp81b_stager_has_only_pinned_production_artifacts():
    stager = _stager_module()
    names = {(item.repo_id, item.revision, item.filename) for item in stager.ARTIFACTS}
    assert ("neuphonic/distill-neucodec", stager.NEUCODEC_REVISION, "config.json") not in names
    assert all("OmniVoice" not in repo and "V3-Turbo" not in repo for repo, _, _ in names)
    assert len(names) == len(stager.ARTIFACTS)
    assert stager.OFFLINE_REFS == {
        "ntu-spml/distilhubert": {"main": stager.DISTILHUBERT_REVISION},
    }
    assert ("ResembleAI/chatterbox", stager.CHATTERBOX_REVISION, "t3_mtl23ls_v3.safetensors") in names
