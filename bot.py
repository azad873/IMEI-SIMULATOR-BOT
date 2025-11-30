"""
BOT_TOKEN = "8498132889:AAGX4wTJrkyX1ISKP1LTeHYSaL_EQ2Jhdps"
SECRET_KEY = "Azad873_SUPER_SECURE_FAKE_TRACKING_KEY_97f2b1e6c4a39d"
Simple IMEI simulation Telegram bot (single-file version).

This is a simplified version of the big multi-file project we discussed.
It:

- Uses python-telegram-bot v20 (async).
- Validates IMEI using Luhn algorithm.
- Generates fake but deterministic locations from IMEI + date.
- Optionally creates a static map via Geoapify.
- Adds a legal disclaimer on EVERY message.

HOW TO USE (Windows):

1. Install Python 3.11 from https://www.python.org
2. Open Command Prompt (or PowerShell) in the folder where bot.py is saved.
3. Install required packages:

   pip install python-telegram-bot[webhooks]==20.8 aiohttp humanize

4. Edit BOT_TOKEN and GEOAPIFY_API_KEY below.
5. Run the bot:

   python bot.py

6. Open Telegram, find your bot, send /start, then send a 15-digit IMEI.
"""

import asyncio
import hmac
import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import List, Tuple, Optional

import aiohttp
import humanize
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
)
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ========= CONFIG: EDIT THESE =============

BOT_TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"  # <- replace with your token from BotFather
SECRET_KEY = "CHANGE_THIS_TO_A_RANDOM_LONG_STRING"  # used for fake location generation
GEOAPIFY_API_KEY = "OPTIONAL_GEOAPIFY_KEY"  # put real key for map image, or leave as-is


# ========= HELPER FUNCTIONS ===============

DISCLAIMER = "⚠️ Simulation only. Real IMEI tracking is illegal without a court order."


def add_disclaimer(text: str) -> str:
    """Append the disclaimer to any message."""
    return f"{text}\n\n{DISCLAIMER}"


def utc_now() -> datetime:
    """Return current UTC time (timezone aware)."""
    return datetime.now(timezone.utc)


def is_valid_imei(imei: str) -> bool:
    """
    Check if a string is a valid 15-digit IMEI using Luhn algorithm.
    """
    if len(imei) != 15 or not imei.isdigit():
        return False

    total = 0
    for i, ch in enumerate(reversed(imei)):
        digit = int(ch)
        if i % 2 == 1:  # every second digit from the right
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def suffix_imei(imei: str) -> str:
    """Return the last 4 digits (for display)."""
    return imei[-4:]


def daily_seed(dt: Optional[datetime] = None) -> str:
    """Return date string used as daily seed."""
    if dt is None:
        dt = utc_now()
    return dt.strftime("%Y-%m-%d")


def hash_to_base_coord(imei: str, seed: str) -> Tuple[float, float]:
    """
    Use HMAC-SHA256(IMEI + seed, SECRET_KEY) to get a base latitude/longitude.

    We map the bytes into:
    - latitude in [-85, 85]
    - longitude in [-180, 180]
    """
    key = SECRET_KEY.encode("utf-8")
    msg = (imei + seed).encode("utf-8")
    digest = hmac.new(key, msg, hashlib.sha256).digest()

    lat_int = int.from_bytes(digest[:8], "big")
    lon_int = int.from_bytes(digest[8:16], "big")

    lat = (lat_int / 2**64) * 170.0 - 85.0
    lon = (lon_int / 2**64) * 360.0 - 180.0
    return lat, lon


async def generate_static_map(
    session: aiohttp.ClientSession,
    coords: List[Tuple[float, float]],
) -> Optional[bytes]:
    """
    Generate a static map PNG with a polyline using Geoapify.

    Returns bytes, or None if GEOAPIFY_API_KEY is missing or any error occurs.
    """
    if not GEOAPIFY_API_KEY or GEOAPIFY_API_KEY == "OPTIONAL_GEOAPIFY_KEY":
        return None  # map feature disabled

    if not coords:
        return None

    first_lat, first_lon = coords[0]
    path_points = "|".join(f"{lon},{lat}" for lat, lon in coords)

    params = {
        "style": "osm-bright",
        "width": 600,
        "height": 400,
        "center": f"lonlat:{first_lon},{first_lat}",
        "zoom": 12,
        "path": f"color:0x0080FF|weight:4|{path_points}",
        "apiKey": GEOAPIFY_API_KEY,
    }

    url = "https://maps.geoapify.com/v1/staticmap"
    try:
        async with session.get(url, params=params, timeout=10) as resp:
            if resp.status != 200:
                return None
            return await resp.read()
    except Exception:
        return None


async def fake_track(imei: str):
    """
    Generate a fake track for this IMEI.

    Returns (points, map_bytes, seed_date)

    - points: list of dicts with timestamp, lat, lon, address
    """
    now = utc_now()
    seed = daily_seed(now)
    base_lat, base_lon = hash_to_base_coord(imei, seed)

    # deterministic random
    digest = hmac.new(
        SECRET_KEY.encode("utf-8"),
        (imei + seed).encode("utf-8"),
        hashlib.sha256,
    ).digest()
    rnd = random.Random(int.from_bytes(digest, "big"))

    coords: List[Tuple[float, float]] = []
    for _ in range(5):
        dlat = (rnd.random() - 0.5) * 0.6  # ±0.3°
        dlon = (rnd.random() - 0.5) * 0.6
        coords.append((base_lat + dlat, base_lon + dlon))

    points = []
    start_time = now - timedelta(hours=24)
    current_time = start_time + timedelta(hours=rnd.uniform(0, 4))

    async with aiohttp.ClientSession() as session:
        for lat, lon in coords:
            if current_time > now:
                current_time = now - timedelta(minutes=rnd.randint(0, 60))

            address = f"Near {lat:.3f}, {lon:.3f}"  # fake address
            points.append(
                {
                    "time": current_time,
                    "lat": lat,
                    "lon": lon,
                    "address": address,
                }
            )
            current_time = current_time + timedelta(hours=rnd.uniform(2, 6))

        # map image
        map_bytes = await generate_static_map(
            session, [(p["lat"], p["lon"]) for p in points]
        )

    points.sort(key=lambda p: p["time"])
    seed_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return points, map_bytes, seed_date


def seconds_until_midnight_utc() -> int:
    """How many seconds until 00:00 UTC."""
    now = utc_now()
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    delta = tomorrow - now
    return int(delta.total_seconds())


# Simple in-memory rate limit: user_id -> (count, date)
# NOTE: If you restart the bot, this resets. For serious use, DB/Redis is better.
rate_limit_state = {}


def check_rate_limit(user_id: int) -> Tuple[bool, int]:
    """
    Allow max 3 checks per user per day.

    Returns (allowed, remaining_seconds_until_reset)
    """
    today = daily_seed()
    entry = rate_limit_state.get(user_id)

    if entry is None or entry["date"] != today:
        rate_limit_state[user_id] = {"date": today, "count": 0}
        entry = rate_limit_state[user_id]

    if entry["count"] >= 3:
        return False, seconds_until_midnight_utc()

    entry["count"] += 1
    return True, seconds_until_midnight_utc()


# ========= HANDLERS =======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    text = (
        "Hi! I can simulate IMEI-based phone tracking for educational purposes.\n\n"
        "Tap *Track IMEI* and send me a 15-digit IMEI. "
        "I will generate a fake, deterministic location history for it."
    )
    keyboard = [
        [InlineKeyboardButton("Track IMEI", callback_data="track")],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    await update.effective_message.reply_text(
        add_disclaimer(text),
        reply_markup=markup,
        parse_mode="Markdown",
    )


async def on_track_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """When user presses “Track IMEI” button."""
    query = update.callback_query
    await query.answer()
    text = "Please send me a *15-digit IMEI* number."
    await query.edit_message_text(add_disclaimer(text), parse_mode="Markdown")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages: treat them as IMEI."""
    message = update.effective_message
    user = update.effective_user
    assert user is not None

    imei = message.text.strip()

    # Validate first
    if not is_valid_imei(imei):
        await message.reply_text(
            add_disclaimer(
                "That doesn't look like a valid 15-digit IMEI. "
                "Double-check you typed it correctly and try again."
            )
        )
        return

    # Rate limit
    allowed, reset_seconds = check_rate_limit(user.id)
    if not allowed:
        delta = timedelta(seconds=reset_seconds)
        pretty = humanize.naturaldelta(delta)
        await message.reply_text(
            add_disclaimer(
                f"⏳ You reached the daily limit of 3 checks.\n"
                f"Please come back in {pretty}."
            )
        )
        return

    # Typing / searching effect
    await message.reply_text(add_disclaimer("🔍 Searching fake network data…"))
    await context.bot.send_chat_action(
        chat_id=message.chat_id, action=ChatAction.TYPING
    )
    await asyncio.sleep(3)

    # Generate fake track
    points, map_bytes, seed_date = await fake_track(imei)

    now = utc_now()
    lines = [
        f"Here is the *simulated* history for IMEI ending with `{suffix_imei(imei)}`:",
        "",
    ]

    for p in points:
        rel = humanize.naturaldelta(now - p["time"])
        lines.append(
            f"• {p['time'].strftime('%Y-%m-%d %H:%M UTC')} "
            f"({rel} ago) – {p['address']}"
        )

    # Last seen
    last_point = points[-1]
    last_seen_rel = humanize.naturaldelta(now - last_point["time"])
    lines.append("")
    lines.append(f"Last seen {last_seen_rel} ago.")

    # Seed rotation info
    reset_secs = seconds_until_midnight_utc()
    rotation_rel = humanize.naturaldelta(timedelta(seconds=reset_secs))
    lines.append(f"Fake signal will refresh in {rotation_rel}.")

    # Buttons
    deep_link = f"https://t.me/{(await context.bot.get_me()).username}?start=imei_{imei}"
    keyboard = [
        [InlineKeyboardButton("Share", url=deep_link)],
        [
            InlineKeyboardButton("Report abuse", callback_data="report"),
            InlineKeyboardButton("Donate", callback_data="donate"),
        ],
    ]
    markup = InlineKeyboardMarkup(keyboard)

    caption = add_disclaimer("\n".join(lines))

    if map_bytes:
        photo = InputFile(map_bytes, filename="track.png")
        await message.reply_photo(
            photo=photo,
            caption=caption,
            reply_markup=markup,
            parse_mode="Markdown",
        )
    else:
        # No map available, send text only
        await message.reply_text(
            caption,
            reply_markup=markup,
            parse_mode="Markdown",
        )


async def on_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'Report abuse' button (just acknowledge in this simple version)."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        add_disclaimer(
            "Thank you. Your report has been noted (this is a demo bot, "
            "no real tracking happens here)."
        )
    )


async def on_donate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'Donate' button."""
    query = update.callback_query
    await query.answer()
    text = (
        "If you like this educational demo and want to support development:\n"
        "- BuyMeACoffee: https://buymeacoffee.com/example\n"
        "- BTC: bc1-example\n"
        "- ETH: 0xExample\n\n"
        "Thank you! ❤️"
    )
    await query.edit_message_text(add_disclaimer(text))


# ========= MAIN ===========================

def main() -> None:
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("Please edit BOT_TOKEN at the top of bot.py")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_track_button, pattern="^track$"))
    app.add_handler(CallbackQueryHandler(on_report, pattern="^report$"))
    app.add_handler(CallbackQueryHandler(on_donate, pattern="^donate$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot is running. Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
