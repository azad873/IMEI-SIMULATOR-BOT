"""
Common helpers for handlers:
- obtaining language
- replying with disclaimer
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from src.utils.i18n import add_disclaimer, get_lang_code


async def reply_with_disclaimer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    **kwargs,
):
    """
    Send a message that always includes the disclaimer.

    This central helper makes it harder to forget the legal line.
    """
    lang = get_lang_code(update)
    final_text = add_disclaimer(lang, text)
    await update.effective_message.reply_text(final_text, **kwargs)
