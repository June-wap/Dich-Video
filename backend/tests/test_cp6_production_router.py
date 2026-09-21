"""CP6 canonical target-language/provider resolver contract (no model runtime)."""
from __future__ import annotations

import pytest

from backend.core.languages import CHATTERBOX_LANGUAGE_IDS, PRODUCTION_LANGUAGE_IDS, normalize_production_language, resolve_tts_provider
from backend.errors import ApplicationError, ErrorCode


def test_production_language_set_is_exactly_24_canonical_ids():
    assert PRODUCTION_LANGUAGE_IDS == (
        "vi", "ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it",
        "ja", "ko", "ms", "nl", "no", "pl", "pt", "ru", "sv", "sw", "tr", "zh",
    )
    assert len(CHATTERBOX_LANGUAGE_IDS) == 23


def test_vietnamese_aliases_normalize_and_resolve_to_vieneu():
    for language in ("vi", "VI", "vi-VN", "vi_VN"):
        assert normalize_production_language(language) == "vi"
        assert resolve_tts_provider(language) == "vieneu"


@pytest.mark.parametrize("language", CHATTERBOX_LANGUAGE_IDS)
def test_every_supported_non_vietnamese_target_resolves_to_chatterbox(language):
    assert normalize_production_language(language) == language
    assert resolve_tts_provider(language) == "chatterbox"


@pytest.mark.parametrize("language", ("", "xx", "en-US", "pt-BR", "zh-CN", None))
def test_unsupported_ids_are_rejected_explicitly(language):
    with pytest.raises(ApplicationError) as caught:
        resolve_tts_provider(language)
    assert caught.value.code == ErrorCode.LANGUAGE_NOT_SUPPORTED
