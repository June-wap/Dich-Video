"""Canonical IDs and scoped OmniVoice validation status. No runtime imports."""
import json
from dataclasses import asdict, dataclass
from pathlib import Path

VERIFIED = "VERIFIED"
EXPERIMENTAL_UPSTREAM = "EXPERIMENTAL-UPSTREAM"
UNSUPPORTED = "UNSUPPORTED"


@dataclass(frozen=True)
class LanguageInfo:
    id: str
    display_name: str
    native_name: str


LANGUAGES = (
    LanguageInfo("vi", "Vietnamese", "Tiếng Việt"),
    LanguageInfo("en", "English", "English"),
    LanguageInfo("zh", "Chinese", "中文"),
    LanguageInfo("ja", "Japanese", "日本語"),
    LanguageInfo("es", "Spanish", "Español"),
    LanguageInfo("pt", "Portuguese", "Português"),
    LanguageInfo("it", "Italian", "Italiano"),
    LanguageInfo("fr", "French", "Français"),
    LanguageInfo("hi", "Hindi", "हिन्दी"),
)
VERIFIED_LANGUAGE_IDS = tuple(item.id for item in LANGUAGES)
LANGUAGE_NAMES = {item.id: item.display_name for item in LANGUAGES}
_UPSTREAM = json.loads(Path(__file__).with_name("omnivoice_upstream_languages.json").read_text(encoding="utf-8"))
UPSTREAM_LANGUAGE_IDS = frozenset(_UPSTREAM["language_ids"])
EXPERIMENTAL_LANGUAGE_IDS = tuple(sorted(UPSTREAM_LANGUAGE_IDS - set(VERIFIED_LANGUAGE_IDS)))


def language_status(language):
    # Strict IDs: no aliases, trimming, case folding or language-agnostic mode.
    if not isinstance(language, str):
        return UNSUPPORTED
    if language in VERIFIED_LANGUAGE_IDS:
        return VERIFIED
    if language in UPSTREAM_LANGUAGE_IDS:
        return EXPERIMENTAL_UPSTREAM
    return UNSUPPORTED


def language_metadata():
    return [dict(asdict(item), status=VERIFIED,
                 verification_scope="CUDA normal short TTS baseline",
                 cloned_live_verified=item.id == "vi",
                 production_ready=False) for item in LANGUAGES]
