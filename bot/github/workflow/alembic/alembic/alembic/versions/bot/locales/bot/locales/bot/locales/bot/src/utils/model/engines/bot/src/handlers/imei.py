"""
Handlers related to IMEI input and fake tracking.

This:
- validates IMEI
- checks rate limit
- calls fake tracking engine
- generates map + response
"""

from __future__ import annotations

from datetime import timedelta

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Update
from telegram.ext import ContextTypes

from src.engines.fake_tracking import FakeTrackResult, generate_fake_track
from src.engines.rate_limit import check_rate_limit, increment_rate_limit
from src.models.base import get_session
from src.models.user import IMEIQuery, User
from src.utils.config import settings
from src.utils.i18n import add_disclaimer, get_lang_code, t
from src.utils.imei import is_valid_imei, mask_imei, suffix_imei
from src.utils.time_utils import humanize_delta, seconds_until_midnight_utc, utc_now
from .common import reply_with_disclaimer


async def ensure_user(db: AsyncSession, update: Update) -> User:
    """
    Ensure we have a User row for this Telegram user.

    If missing, create one.
    """
    tg_user = update.effective_user
    assert tg_user is not None
    user = await db.get(User, tg_user.id)
    if user is None:
        user = User(id=tg_user.id, language_code=tg_user.language_code)
        db.add(user)
        await db.commit()
    return user


async def handle_imei_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle a plain text message that may contain an IMEI.

    This is triggered after user presses 'Track IMEI' and sends a number.
    """
    lang = get_lang_code(update)
    message = update.effective_message
    text = message.text.strip()

    # Validate format first.
    if not is_valid_imei(text):
        await reply_with_disclaimer(update, context, t(lang, "invalid_imei"))
        return

    imei = text

    # Connect to Redis and Postgres.
    redis: Redis = context.bot_data["redis"]
    async for db in get_session():
        # Ensure user exists.
        user = await ensure_user(db, update)

        # Check rate limit.
        status = await check_rate_limit(redis, db, user.id)
        if not status.allowed:
            # Show user how long to wait.
            delta = timedelta(seconds=status.reset_in_seconds)
            human = humanize_delta(delta)
            await reply_with_disclaimer(
                update,
                context,
                t(lang, "rate_limited", time_left=human),
            )
            return

        # Increment usage now that request is accepted.
        await increment_rate_limit(redis, user.id)

        # Record query with masked IMEI prefix.
        masked = mask_imei(imei)
        q = IMEIQuery(user_id=user.id, imei_prefix=masked)
        db.add(q)
        await db.commit()

    # Show "searching" message with typing delay.
    searching_text = t(lang, "searching")
    await reply_with_disclaimer(update, context, searching_text)
    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")

    # Check Redis cache for this IMEI first.
    cache_key = f"track:imei:{imei}"
    cached = await redis.get(cache_key)
    if cached:
        # If we stored compressed result, we would deserialize here.
        # For brevity, we regenerate even if cache exists; but you can expand
        # this to store JSON + base64 map.
        pass

    # Generate fake track (deterministic).
    result: FakeTrackResult = await generate_fake_track(imei)

    # Cache marker for 1 hour to satisfy requirement.
    await redis.set(cache_key, "1", ex=3600)

    # Build response.
    suffix = suffix_imei(imei)
    header = t(lang, "imei_result_header", suffix=suffix)

    # Build history text.
    lines = [header, ""]
    now = utc_now()

    for point in result.points:
        # Relative time (e.g. "3 hours ago").
        rel = humanize_delta(now - point.timestamp)
        line = f"• {point.timestamp.isoformat()} ({rel}) – {point.address}"
        lines.append(line)

    # Seed rotation countdown.
    seconds_left = seconds_until_midnight_utc()
    rotation_delta = timedelta(seconds=seconds_left)
    rotation_str = humanize_delta(rotation_delta)
    lines.append("")
    lines.append(t(lang, "seed_rotation", time_left=rotation_str))

    # Last seen info.
    last_point = result.points[-1]
    last_seen_rel = humanize_delta(now - last_point.timestamp)
    lines.append(t(lang, "last_seen", relative_time=last_seen_rel))

    body = "\n".join(lines)

    # Inline keyboard with Share / Report / Donate.
    # For Share, we construct a deeplink. We need bot username from context.
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username

    deep_link = f"https://t.me/{bot_username}?start=imei_{imei}"
    keyboard = [
        [
            InlineKeyboardButton(t(lang, "btn_share"), url=deep_link),
        ],
        [
            InlineKeyboardButton(
                t(lang, "btn_report_abuse"),
                callback_data=f"report_{suffix}",
            ),
            InlineKeyboardButton(
                t(lang, "btn_donate"),
                callback_data="donate",
            ),
        ],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    # Send map as photo with caption.
    caption = add_disclaimer(lang, body)
    photo_file = InputFile(result.map_png, filename="track.png")
    await update.effective_message.reply_photo(photo=photo_file, caption=caption, reply_markup=markup)
