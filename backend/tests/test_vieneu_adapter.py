"""Regression coverage for VieNeu's pinned Neucodec loading boundary."""

from __future__ import annotations

from unittest.mock import Mock

from backend.services.vieneu_adapter import VieNeuAdapter


def test_pinned_neucodec_loader_uses_its_official_direct_loader(monkeypatch):
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)
    loader = Mock(return_value=object())
    codec = type("Codec", (), {"_from_pretrained": loader})

    loaded = VieNeuAdapter._load_pinned_neucodec(
        codec,
        VieNeuAdapter.CODEC_REPOSITORY,
        VieNeuAdapter.CODEC_REVISION,
    )

    assert loaded is loader.return_value
    loader.assert_called_once_with(
        model_id="neuphonic/distill-neucodec",
        revision="6f2b93b3fa2bc74740ba1bd10622e1ee37dbbe46",
        local_files_only=False,
    )


def test_pinned_neucodec_loader_forbids_network_when_offline(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    loader = Mock(return_value=object())
    codec = type("Codec", (), {"_from_pretrained": loader})

    VieNeuAdapter._load_pinned_neucodec(
        codec,
        VieNeuAdapter.CODEC_REPOSITORY,
        VieNeuAdapter.CODEC_REVISION,
    )

    loader.assert_called_once_with(
        model_id="neuphonic/distill-neucodec",
        revision="6f2b93b3fa2bc74740ba1bd10622e1ee37dbbe46",
        local_files_only=True,
    )
