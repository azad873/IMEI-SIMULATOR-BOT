"""
Handler for "Report abuse" button.
"""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes

from src.models.base import get_session
from src.models.user import AbuseReport, User
from src.utils.config import settings
from src.utils.i18n import add_disclaimer, get_lang_code, t
from src.utils.time_utils import utc_now


async def report_abuse_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle 'Report abuse' inline button.

    We:
    - log a simple AbuseReport row
    - notify admins with a summary
    """
    lang = get_lang_code(update)
    query = update.callback_query
    await query.answer()

    suffix = ""
    if query.data and query.data.startswith("report_"):
        suffix = query.data[len("report_") :]

    async for db in get_session():
        tg_user = update.effective_user
        if tg_user is None:
            break

        user = await db.get(User, tg_user.id)
        if user is None:
            user = User(id=tg_user.id, language_code=tg_user.language_code)
            db.add(user)
            await db.commit()

        report = AbuseReport(
            user_id=user.id,
            imei_prefix=f"*{suffix}" if suffix else None,
            reason=None,
            created_at=utc_now(),
        )
        db.add(report)
        await db.commit()

    # Notify admins
    for admin_id in settings.admin_ids_list:
        try:
            msg = f"Abuse report from user {update.effective_user.id}, IMEI suffix: {suffix}"
            await context.bot.send_message(admin_id, msg)
        except Exception:
            continue

    await query.edit_message_text(add_disclaimer(lang, t(lang, "report_received")))
