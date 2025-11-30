"""
Very small i18n layer that loads translations from JSON files.

We don't use heavy frameworks here; we just:
- load locales/en.json, locales/es.json, etc.
- pick messages by key and language code
- fall back to English or configured fallback
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict

from telegram import Update

from .config import settings

LOCALES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "locales")


@lru_cache
def load_locale(lang: str) -> Dict[str, str]:
    """
    Load a locale JSON file and return its dictionary.

    If the file doesn't exist, fall back to English.
    """
    file_path = os.path.join(LOCALES_DIR, f"{lang}.json")
    if not os.path.exists(file_path):
        # Fallback to configured locale or English
        file_path = os.path.join(LOCALES_DIR, f"{settings.LOCALE_FALLBACK}.json")

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_lang_code(update: Update, explicit_lang: str | None = None) -> str:
    """
    Decide which language to use for this update.

    Order:
    1. Explicit language (when user changed via /lang)
    2. Telegram user.language_code
    3. Configured fallback (e.g. 'en')
    """
    if explicit_lang:
        return explicit_lang

    tg_lang = update.effective_user.language_code if update.effective_user else None
    if tg_lang and os.path.exists(os.path.join(LOCALES_DIR, f"{tg_lang}.json")):
        return tg_lang

    return settings.LOCALE_FALLBACK


def t(lang: str, key: str, **kwargs: Any) -> str:
    """
    Translate a key into a text for the given language.

    kwargs are used to format placeholders, e.g. {time_left}.
    """
    data = load_locale(lang)
    text = data.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            # If formatting fails due to missing key, just return raw text.
            pass
    return text


def add_disclaimer(lang: str, text: str) -> str:
    """
    Append the disclaimer line from locale to any outgoing message.

    This helps us obey the rule that EVERY user-facing message must include it.
    """
    disclaimer = t(lang, "disclaimer")
    # Separate message and disclaimer with a blank line for readability.
    return f"{text}\n\n{disclaimer}"
