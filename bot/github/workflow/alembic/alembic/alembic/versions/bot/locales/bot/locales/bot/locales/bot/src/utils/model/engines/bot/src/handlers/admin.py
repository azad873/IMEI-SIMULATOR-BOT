"""
Admin commands:
- /adminstats
- /broadcast
"""

from __future__ import annotations

from typing import List

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from src.models.base import get_session
from src.models.user import AbuseReport, IMEIQuery, User
from src.utils.config import settings
from src.utils.i18n import add_disclaimer, get_lang_code, t

BROADCAST_WAITING = 1  # conversation state


def is_admin(user_id: int) -> bool:
    """Check if given Telegram user ID is an admin from settings."""
    return user_id in settings.admin_ids_list


async def adminstats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show basic statistics to admins."""
    lang = get_lang_code(update)
    user = update.effective_user
    if user is None or not is_admin(user.id):
        await update.effective_message.reply_text(
            add_disclaimer(lang, t(lang, "admin_unauthorized"))
        )
        return

    async for db in get_session():
        # Count users
        user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()

        # Count queries
        query_count = (await db.execute(select(func.count()).select_from(IMEIQuery))).scalar_one()

        # Count abuse reports
        abuse_count = (
            await db.execute(select(func.count()).select_from(AbuseReport))
        ).scalar_one()

        # Top 10 IMEI prefixes
        stmt_top = (
            select(IMEIQuery.imei_prefix, func.count().label("c"))
            .group_by(IMEIQuery.imei_prefix)
            .order_by(func.count().desc())
            .limit(10)
        )
        result = await db.execute(stmt_top)
        top_rows = result.all()

    header = t(lang, "admin_stats_header")
    body = t(lang, "admin_stats_body", users=user_count, queries=query_count, abuse=abuse_count)

    lines = [header, "", body, ""]
    if top_rows:
        lines.append(t(lang, "admin_top_imeis"))
        for prefix, count in top_rows:
            lines.append(f"- {prefix}: {count}")
    text = "\n".join(lines)

    await update.effective_message.reply_text(add_disclaimer(lang, text), parse_mode="Markdown")


async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Entry point for /broadcast conversation.

    Ask admin to send the message to broadcast.
    """
    lang = get_lang_code(update)
    user = update.effective_user
    if user is None or not is_admin(user.id):
        await update.effective_message.reply_text(
            add_disclaimer(lang, t(lang, "admin_unauthorized"))
        )
        return ConversationHandler.END

    await update.effective_message.reply_text(
        add_disclaimer(lang, t(lang, "admin_broadcast_prompt"))
    )
    return BROADCAST_WAITING


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Receive broadcast message from admin and send to all users.
    """
    lang = get_lang_code(update)
    text_to_send = update.effective_message.text

    async for db in get_session():
        # fetch all user IDs
        stmt = select(User.id)
        result = await db.execute(stmt)
        user_ids: List[int] = [row[0] for row in result.all()]

    # Send message to each user. Errors are ignored so one bad user doesn't stop loop.
    count = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(uid, text_to_send)
            count += 1
        except Exception:
            continue

    await update.effective_message.reply_text(
        add_disclaimer(lang, t(lang, "admin_broadcast_done", count=count))
    )
    return ConversationHandler.END


async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allow admin to cancel the broadcast."""
    lang = get_lang_code(update)
    await update.effective_message.reply_text(add_disclaimer(lang, "Broadcast cancelled."))
    return ConversationHandler.END
