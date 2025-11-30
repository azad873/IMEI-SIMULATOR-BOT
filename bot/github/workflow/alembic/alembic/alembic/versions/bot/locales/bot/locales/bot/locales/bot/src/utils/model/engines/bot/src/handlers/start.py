"""
Handler for /start command and initial inline keyboard flow.
"""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ContextTypes

from src.utils.i18n import add_disclaimer, get_lang_code, t
from src.utils.imei import is_valid_imei
from src.utils.time_utils import seconds_until_midnight_utc
from .common import reply_with_disclaimer


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start command handler.

    Sends a cute sticker (you can replace with your file_id) and an inline keyboard.
    """
    lang = get_lang_code(update)
    # Cute sticker: you should replace FILE_ID with your own sticker ID.
    # We ignore errors if sticker fails to send.
    try:
        await update.message.reply_sticker("CAACAgUAAxkBAAIBQ2d_sticker_example")
    except Exception:
        pass

    keyboard = [
        [
            InlineKeyboardButton(t(lang, "btn_track_imei"), callback_data="track_imei"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = f"{t(lang, 'start_welcome')}\n\n{t(lang, 'start_cta')}"
    await update.message.reply_text(
        add_disclaimer(lang, text),
        reply_markup=reply_markup,
    )


async def start_track_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle inline keyboard 'Track IMEI' press.

    We ask user to send 15-digit IMEI.
    """
    lang = get_lang_code(update)
    query = update.callback_query
    await query.answer()

    text = t(lang, "prompt_imei")
    await query.edit_message_text(add_disclaimer(lang, text))


async def handle_invalid_imei(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Helper for invalid IMEI responses.

    Shows a GIF and a 'Try again' button.
    """
    lang = get_lang_code(update)

    # Send a cute GIF from Telegram (replace with your own file_id or URL)
    try:
        await update.message.reply_animation("CgACAgQAAxkBAAIBRmd_gif_example")
    except Exception:
        pass

    keyboard = [[InlineKeyboardButton(t(lang, "btn_try_again"), callback_data="track_imei")]]
    markup = InlineKeyboardMarkup(keyboard)

    await reply_with_disclaimer(update, context, t(lang, "invalid_imei"), reply_markup=markup)
