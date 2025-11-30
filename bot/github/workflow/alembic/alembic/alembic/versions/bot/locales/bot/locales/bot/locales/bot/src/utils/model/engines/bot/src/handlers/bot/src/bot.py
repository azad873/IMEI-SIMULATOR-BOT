"""
Main entrypoint for the Telegram bot.

Creates the Application, sets up handlers, connects to Redis / DB,
and starts in webhook or long polling mode depending on configuration.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

import redis.asyncio as redis
from telegram.ext import (
    AIORateLimiter,
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.handlers.abuse import report_abuse_callback
from src.handlers.admin import (
    BROADCAST_WAITING,
    adminstats,
    broadcast_cancel,
    broadcast_send,
    broadcast_start,
)
from src.handlers.imei import handle_imei_message
from src.handlers.lang import lang_callback, lang_command
from src.handlers.start import start, start_track_callback
from src.utils.config import settings
from src.utils.logging import setup_logging


async def on_startup(app: Application) -> None:
    """Run on application startup: connect Redis and store in bot_data."""
    # Connect Redis and store client so handlers can use it.
    app.bot_data["redis"] = redis.from_url(settings.REDIS_URL, decode_responses=False)
    logging.getLogger(__name__).info("Connected Redis client")


async def on_shutdown(app: Application) -> None:
    """Run on application shutdown: close Redis connection."""
    redis_client: redis.Redis | None = app.bot_data.get("redis")
    if redis_client:
        await redis_client.aclose()
        logging.getLogger(__name__).info("Closed Redis client")


def build_application() -> Application:
    """Create and configure the Telegram Application."""
    setup_logging()
    logging.getLogger(__name__).info("Starting IMEI simulator bot")

    application = (
        ApplicationBuilder()
        .token(settings.BOT_TOKEN)
        .rate_limiter(AIORateLimiter())  # basic rate limiter for Telegram API itself
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )

    # === Command handlers ===
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("lang", lang_command))
    application.add_handler(CommandHandler("adminstats", adminstats))

    # Broadcast conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("broadcast", broadcast_start)],
        states={
            BROADCAST_WAITING: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", broadcast_cancel)],
    )
    application.add_handler(conv)

    # === Callback query handlers ===
    application.add_handler(CallbackQueryHandler(start_track_callback, pattern="^track_imei$"))
    application.add_handler(CallbackQueryHandler(lang_callback, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(report_abuse_callback, pattern="^report_"))
    application.add_handler(CallbackQueryHandler(report_abuse_callback, pattern="^donate$"), group=1)

    # === Message handlers ===
    # IMEI numbers are plain text; we keep it simple and send all TEXT to IMEI handler.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_imei_message))

    return application


def main() -> None:
    """Entrypoint called by 'python -m src.bot'."""
    app = build_application()

    if settings.WEBHOOK_URL:
        # Webhook mode (for production)
        logging.getLogger(__name__).info("Running in webhook mode.")
        app.run_webhook(
            listen="0.0.0.0",
            port=settings.PORT,
            url_path="webhook",
            webhook_url=f"{settings.WEBHOOK_URL}/webhook",
        )
    else:
        # Long polling mode (for development / simple hosting)
        logging.getLogger(__name__).info("Running in polling mode.")
        app.run_polling()


if __name__ == "__main__":
    main()
