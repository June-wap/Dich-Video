"""Canonical language IDs shared by API validation and future TTS routing."""
from dataclasses import asdict, dataclass

VERIFIED = "VERIFIED"
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


def language_status(language):
    # Strict IDs: no aliases, trimming, case folding or language-agnostic mode.
    if not isinstance(language, str):
        return UNSUPPORTED
    if language in VERIFIED_LANGUAGE_IDS:
        return VERIFIED
    return UNSUPPORTED


def language_metadata():
    return [dict(asdict(item), status=VERIFIED,
                 verification_scope="No production engine configured during CP1",
                 cloned_live_verified=False,
                 production_ready=False) for item in LANGUAGES]
