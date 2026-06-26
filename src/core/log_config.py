"""Central logging setup. Call configure_logging() once at startup.

Console + rotating file output, a separate errors-only file, and discord.py's
own loggers turned down so the logs stay about THIS bot. Plain readable format.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path("logs")
_FMT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Rotation: 5 MB per file, keep 5 old files (so ~30 MB ceiling per log).
_MAX_BYTES = 5 * 1024 * 1024
_BACKUPS = 5


def configure_logging(level: int = logging.INFO) -> None:
    _LOG_DIR.mkdir(exist_ok=True)  # create logs/ before any handler writes

    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)
    root = logging.getLogger()
    root.setLevel(level)

    # Guard against double-configuration (e.g. if called twice).
    if root.handlers:
        root.handlers.clear()

    # Console.
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # Everything at `level` and up -> rotating bot.log.
    file_all = RotatingFileHandler(
        _LOG_DIR / "bot.log", maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    file_all.setFormatter(formatter)
    root.addHandler(file_all)

    # Errors only -> rotating errors.log, so problems are easy to find.
    file_err = RotatingFileHandler(
        _LOG_DIR / "errors.log", maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    file_err.setLevel(logging.ERROR)
    file_err.setFormatter(formatter)
    root.addHandler(file_err)

    # Quiet the noisy library loggers; keep our own at `level`.
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
