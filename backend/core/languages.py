"""Canonical production target-language and provider-ownership contract."""
from dataclasses import asdict, dataclass

from backend.errors import ApplicationError, ErrorCode

VERIFIED = "VERIFIED"
UNSUPPORTED = "UNSUPPORTED"
VIENEU_PROVIDER_ID = "vieneu"
CHATTERBOX_PROVIDER_ID = "chatterbox"


@dataclass(frozen=True)
class LanguageInfo:
    id: str
    display_name: str
    native_name: str


LANGUAGES = (
    LanguageInfo("vi", "Vietnamese", "Tiếng Việt"),
    LanguageInfo("ar", "Arabic", "Arabic"), LanguageInfo("da", "Danish", "Danish"),
    LanguageInfo("de", "German", "German"), LanguageInfo("el", "Greek", "Greek"),
    LanguageInfo("en", "English", "English"), LanguageInfo("es", "Spanish", "Spanish"),
    LanguageInfo("fi", "Finnish", "Finnish"), LanguageInfo("fr", "French", "French"),
    LanguageInfo("he", "Hebrew", "Hebrew"), LanguageInfo("hi", "Hindi", "Hindi"),
    LanguageInfo("it", "Italian", "Italian"), LanguageInfo("ja", "Japanese", "Japanese"),
    LanguageInfo("ko", "Korean", "Korean"), LanguageInfo("ms", "Malay", "Malay"),
    LanguageInfo("nl", "Dutch", "Dutch"), LanguageInfo("no", "Norwegian", "Norwegian"),
    LanguageInfo("pl", "Polish", "Polish"), LanguageInfo("pt", "Portuguese", "Portuguese"),
    LanguageInfo("ru", "Russian", "Russian"), LanguageInfo("sv", "Swedish", "Swedish"),
    LanguageInfo("sw", "Swahili", "Swahili"), LanguageInfo("tr", "Turkish", "Turkish"),
    LanguageInfo("zh", "Chinese", "Chinese"),
)
PRODUCTION_LANGUAGE_IDS = tuple(item.id for item in LANGUAGES)
CHATTERBOX_LANGUAGE_IDS = tuple(item for item in PRODUCTION_LANGUAGE_IDS if item != "vi")
VERIFIED_LANGUAGE_IDS = PRODUCTION_LANGUAGE_IDS
LANGUAGE_NAMES = {item.id: item.display_name for item in LANGUAGES}


def normalize_production_language(language: str) -> str:
    """Normalize the established Vietnamese aliases; reject all other aliases."""
    if not isinstance(language, str):
        raise ApplicationError(ErrorCode.LANGUAGE_NOT_SUPPORTED)
    normalized = language.strip().lower().replace("_", "-")
    if normalized in {"vi", "vi-vn"}:
        return "vi"
    if normalized not in PRODUCTION_LANGUAGE_IDS:
        raise ApplicationError(ErrorCode.LANGUAGE_NOT_SUPPORTED)
    return normalized


def resolve_tts_provider(language: str) -> str:
    """The sole production language-to-provider routing decision."""
    canonical = normalize_production_language(language)
    if canonical == "vi":
        return VIENEU_PROVIDER_ID
    if canonical in CHATTERBOX_LANGUAGE_IDS:
        return CHATTERBOX_PROVIDER_ID
    raise ApplicationError(ErrorCode.LANGUAGE_NOT_SUPPORTED)


def language_status(language):
    try:
        normalize_production_language(language)
    except ApplicationError:
        return UNSUPPORTED
    return VERIFIED


def language_metadata():
    return [dict(asdict(item), status=VERIFIED,
                 verification_scope="Production Short TTS",
                 cloned_live_verified=False,
                 production_ready=True) for item in LANGUAGES]
