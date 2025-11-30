"""
Logging configuration for the bot.
"""

import logging
import sys


def setup_logging() -> None:
    """
    Configure basic logging for the whole application.

    - Logs to stdout so Docker can capture output.
    - INFO level by default is a good balance for bots.
    """
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
