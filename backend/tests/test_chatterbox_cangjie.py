from __future__ import annotations

import json
import hashlib
import os
import sys
import types

import pytest

from backend.services.chatterbox_adapter import ChatterboxAdapter


def _snapshot(tmp_path):
    root = tmp_path / "hub"
    snapshot = root / "models--ResembleAI--chatterbox" / "snapshots" / ChatterboxAdapter.MODEL_REVISION
    snapshot.mkdir(parents=True)
    return root, snapshot


def _mapping(monkeypatch, snapshot, contents='["你\\tO", "好\\tVND"]'):
    path = snapshot / ChatterboxAdapter.CANGJIE_FILENAME
    path.write_text(contents, encoding="utf-8")
    monkeypatch.setattr(ChatterboxAdapter, "CANGJIE_SIZE_BYTES", path.stat().st_size)
    monkeypatch.setattr(ChatterboxAdapter, "CANGJIE_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
    return path


def test_pinned_cangjie_mapping_reads_local_artifact_without_hub(monkeypatch, tmp_path):
    _, snapshot = _snapshot(tmp_path)
    _mapping(monkeypatch, snapshot)
    word2cj, cj2word = ChatterboxAdapter._read_pinned_cangjie_mapping(snapshot)
    assert word2cj == {"你": "O", "好": "VND"}
    assert cj2word == {"O": ["你"], "VND": ["好"]}


def test_missing_pinned_cangjie_mapping_fails_explicitly(tmp_path):
    _, tmp_path = _snapshot(tmp_path)
    with pytest.raises(RuntimeError, match="invalid"):
        ChatterboxAdapter._read_pinned_cangjie_mapping(tmp_path)


def test_hf_snapshot_symlink_to_cache_blob_is_accepted(monkeypatch, tmp_path):
    root, snapshot = _snapshot(tmp_path)
    blob = root / "blobs" / "approved"; blob.parent.mkdir(parents=True, exist_ok=True)
    blob.write_text('["你\\tO"]', encoding="utf-8")
    logical = snapshot / ChatterboxAdapter.CANGJIE_FILENAME
    os.symlink(blob, logical)
    monkeypatch.setattr(ChatterboxAdapter, "CANGJIE_SIZE_BYTES", blob.stat().st_size)
    monkeypatch.setattr(ChatterboxAdapter, "CANGJIE_SHA256", hashlib.sha256(blob.read_bytes()).hexdigest())
    assert ChatterboxAdapter._read_pinned_cangjie_mapping(snapshot)[0] == {"你": "O"}


def test_external_cangjie_symlink_is_rejected(monkeypatch, tmp_path):
    _, snapshot = _snapshot(tmp_path)
    external = tmp_path / "external.json"; external.write_text('["你\\tO"]', encoding="utf-8")
    os.symlink(external, snapshot / ChatterboxAdapter.CANGJIE_FILENAME)
    monkeypatch.setattr(ChatterboxAdapter, "CANGJIE_SIZE_BYTES", external.stat().st_size)
    monkeypatch.setattr(ChatterboxAdapter, "CANGJIE_SHA256", hashlib.sha256(external.read_bytes()).hexdigest())
    with pytest.raises(RuntimeError, match="invalid"):
        ChatterboxAdapter._read_pinned_cangjie_mapping(snapshot)


def test_wrong_cangjie_hash_is_rejected(monkeypatch, tmp_path):
    _, snapshot = _snapshot(tmp_path)
    _mapping(monkeypatch, snapshot)
    monkeypatch.setattr(ChatterboxAdapter, "CANGJIE_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="SHA256"):
        ChatterboxAdapter._read_pinned_cangjie_mapping(snapshot)


def test_shim_injects_mapping_and_restores_upstream_method(monkeypatch, tmp_path):
    _, snapshot = _snapshot(tmp_path)
    _mapping(monkeypatch, snapshot)
    module = types.ModuleType("chatterbox.models.tokenizers.tokenizer")
    class Converter:
        def _load_cangjie_mapping(self, _model_dir=None): pass
    original = Converter._load_cangjie_mapping
    module.ChineseCangjieConverter = Converter
    monkeypatch.setitem(sys.modules, "chatterbox", types.ModuleType("chatterbox"))
    monkeypatch.setitem(sys.modules, "chatterbox.models", types.ModuleType("chatterbox.models"))
    monkeypatch.setitem(sys.modules, "chatterbox.models.tokenizers", types.ModuleType("chatterbox.models.tokenizers"))
    monkeypatch.setitem(sys.modules, "chatterbox.models.tokenizers.tokenizer", module)
    with ChatterboxAdapter()._pinned_cangjie_loader(snapshot):
        converter = Converter(); converter.word2cj = {}; converter.cj2word = {}
        converter._load_cangjie_mapping()
        assert converter.word2cj == {"你": "O", "好": "VND"}
    assert Converter._load_cangjie_mapping is original
