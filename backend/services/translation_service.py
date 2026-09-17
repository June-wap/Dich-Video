"""Optional machine-translation step ahead of TTS - BYOK (Bring Your Own Key)
only. This app never ships, embeds, or shares a Gemini account/API key: each
install stores its own single API key (entered by that install's owner in
Settings), used only for that install's own requests.

Why BYOK: a shared/embedded key inside distributed desktop software cannot be
protected (anyone holding the software holds the key), pools every install's
usage and liability onto one account, and cannot enforce a subscription/time
limit client-side. See claude/checklist-dong-goi-ban-short.md mục C and
claude/nghien-cuu-dich-may-mt-16-09.md for the full reasoning trail. This is a
separate, additive feature track - it never changes Vietnamese-language
short TTS or voice cloning, which never call this service.

License/privacy note (surface this to the user in Settings, do not bury it):
Gemini API free-tier usage is used by Google to improve their models unless
the install owner's own account is on a paid tier - see the terms at
https://ai.google.dev/gemini-api/terms. This is the customer's own choice
made when they supply their own key, not a decision this app makes for them.
"""
from __future__ import annotations

import logging

from backend.config import Settings
from backend.errors import ApplicationError, ErrorCode
from backend.persistence import Repository

logger = logging.getLogger("backend.translation")

SETTINGS_KEY = "gemini_api_key"
# Flash tier: far higher free-tier rate limits than Pro, and more than
# sufficient quality for short customer-service text. Change here (not
# scattered across call sites) if a newer flash-tier model should be used.
MODEL_ID = "gemini-2.5-flash"

# Matches PiperProvider.LANGUAGES + ja/hi - every non-Vietnamese language this
# app's TTS layer supports. Display names guide the model's output language
# unambiguously (a bare ISO code like "hi" is ambiguous with Croatian "hr" in
# casual prose, so we always prompt with the full English name).
LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "pt": "Portuguese", "fr": "French",
    "it": "Italian", "zh": "Chinese (Simplified)", "ja": "Japanese", "hi": "Hindi",
}


class TranslationService:
    def __init__(self, settings: Settings):
        self._db = Repository(settings)

    def get_api_key(self) -> str | None:
        stored = self._db.get_setting(SETTINGS_KEY, default={}) or {}
        key = stored.get("value")
        return key or None

    def set_api_key(self, api_key: str | None) -> None:
        cleaned = (api_key or "").strip()
        self._db.put("settings", SETTINGS_KEY, {"value": cleaned})
        logger.info("translation_key_updated configured=%s", bool(cleaned))

    def is_configured(self) -> bool:
        return bool(self.get_api_key())

    @staticmethod
    def key_preview(api_key: str) -> str:
        if len(api_key) <= 6:
            return "•" * len(api_key)
        return f"{api_key[:4]}…{api_key[-2:]}"

    def translate(self, text: str, target_language: str) -> str:
        """Translate `text` into `target_language` (an ISO code from
        LANGUAGE_NAMES). Raises ApplicationError(TRANSLATION_KEY_REQUIRED) if
        no key is configured, or ApplicationError(TRANSLATION_FAILED) for any
        SDK/network/API failure - callers never see the raw Gemini exception.
        """
        api_key = self.get_api_key()
        if not api_key:
            raise ApplicationError(ErrorCode.TRANSLATION_KEY_REQUIRED)

        language_name = LANGUAGE_NAMES.get(target_language, target_language)

        try:
            from google import genai  # Deferred: only needed once a key is set.
        except Exception as exc:
            logger.error("translation_sdk_missing error=%s", exc)
            raise ApplicationError(ErrorCode.TRANSLATION_FAILED) from None

        prompt = (
            f"Translate the following text into {language_name}. "
            "Output ONLY the translated text - no explanations, no quotation "
            "marks, no notes. Preserve the original tone and meaning "
            "faithfully.\n\n" + text
        )

        try:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(model=MODEL_ID, contents=prompt)
            translated = (getattr(response, "text", None) or "").strip()
            if not translated:
                raise ValueError("Empty translation response")
        except Exception as exc:
            # Covers invalid/revoked key, rate limiting, and network failure
            # alike - the specific cause isn't actionable for the caller,
            # only "translation didn't happen" is. Never log request text.
            logger.error("translation_call_failed language=%s error=%s", target_language, exc)
            raise ApplicationError(ErrorCode.TRANSLATION_FAILED) from None

        logger.info(
            "translation_completed language=%s source_len=%d translated_len=%d",
            target_language, len(text), len(translated),
        )
        return translated
