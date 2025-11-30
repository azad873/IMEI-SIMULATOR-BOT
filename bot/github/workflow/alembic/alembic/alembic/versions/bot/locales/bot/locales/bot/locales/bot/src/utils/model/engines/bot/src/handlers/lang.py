"""
Handler for /lang command.

Shows simple list of supported languages and updates DB.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.models.base import get_session
from src.models.user import User
from src.utils.i18n import add_disclaimer, get_lang_code, t


SUPPORTED_LANGS = {
    "en": "English",
    "es": "Español",
    "ru": "Русский",
    "hi": "हिन्दी",
}


async def lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show language selection keyboard."""
    lang = get_lang_code(update)

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"lang_{code}")]
        for code, name in SUPPORTED_LANGS.items()
    ]
    markup = InlineKeyboardMarkup(keyboard)

    await update.effective_message.reply_text(
        add_disclaimer(lang, t(lang, "choose_language")),
        reply_markup=markup,
    )


async def lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline selection of language."""
    query = update.callback_query
    await query.answer()

    lang = get_lang_code(update)
    data = query.data or ""
    if not data.startswith("lang_"):
        return
    new_lang = data.split("_", 1)[1]

    # Update user in DB
    async for db in get_session():
        tg_user = update.effective_user
        if tg_user is None:
            break
        user = await db.get(User, tg_user.id)
        if user is None:
            user = User(id=tg_user.id, language_code=new_lang)
            db.add(user)
        else:
            user.language_code = new_lang
        await db.commit()

    # Use new language for confirmation
    text = t(new_lang, "lang_updated", lang=SUPPORTED_LANGS.get(new_lang, new_lang))
    await query.edit_message_text(add_disclaimer(new_lang, text))
