"""Entrypoint: python -m src"""

from __future__ import annotations

import asyncio

from config.settings import get_settings
from src.core.bot import Bot
from src.core.log_config import configure_logging


async def main() -> None:
    settings = get_settings()
    bot = Bot()
    async with bot:
        await bot.start(settings.bot_token)


if __name__ == "__main__":
    configure_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # clean exit on Ctrl+C, no traceback
