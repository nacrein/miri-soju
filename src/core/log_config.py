"""Central logging setup. Call configure_logging() once at startup.

Colored console (rich) + rotating file output, a separate errors-only file, and
discord.py's own loggers turned down so the logs stay about THIS bot.

The console uses a RichHandler: time-only timestamps, colour-coded levels
(yellow WARNING, red ERROR, blue INFO) and syntax-highlighted tracebacks, with
our own ``src.core.`` / ``src.modules.`` prefixes stripped from logger names so
the eye lands on warnings and errors instead of reading a uniform wall.

The rotating files deliberately keep the full plain format (full date, full
dotted logger name, plain-text tracebacks) so they stay grep-friendly for
forensics long after the colours have scrolled off screen.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

_LOG_DIR = Path("logs")

# Files: full timestamp + full dotted logger name, easy to grep after the fact.
_FILE_FMT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Console: RichHandler renders the time and the (coloured) level itself, so the
# formatter only owns "name: message"; the time column is set via log_time_format.
_CONSOLE_FMT = "%(name)s: %(message)s"
_CONSOLE_TIMEFMT = "%H:%M:%S"

# Prefixes stripped from logger names on the console only (so
# "src.modules.music.cog" shows as "music.cog", "src.core.bot" as "bot").
_STRIP_PREFIXES = ("src.modules.", "src.core.")

# Rotation: 5 MB per file, keep 5 old files (so ~30 MB ceiling per log).
_MAX_BYTES = 5 * 1024 * 1024
_BACKUPS = 5


class _ShortNameFormatter(logging.Formatter):
    """Drop our own package prefixes from the logger name for console display.

    Overrides ``formatMessage`` rather than ``format`` on purpose: that is the
    single point both the normal render path *and* RichHandler's rich-traceback
    path route the message through, so exception logs get the short name too.
    The record's real ``name`` is restored immediately, so the file handlers
    (which share the same record) still log the full dotted name.
    """

    def formatMessage(self, record: logging.LogRecord) -> str:
        original = record.name
        for prefix in _STRIP_PREFIXES:
            if original.startswith(prefix):
                record.name = original[len(prefix):]
                break
        try:
            return super().formatMessage(record)
        finally:
            record.name = original


def configure_logging(level: int = logging.INFO) -> None:
    _LOG_DIR.mkdir(exist_ok=True)  # create logs/ before any handler writes

    file_formatter = logging.Formatter(_FILE_FMT, datefmt=_FILE_DATEFMT)
    root = logging.getLogger()
    root.setLevel(level)

    # Guard against double-configuration (e.g. if called twice).
    if root.handlers:
        root.handlers.clear()

    # Console: colour-coded, time-only, syntax-highlighted tracebacks. Rich
    # auto-disables colour when stdout isn't a TTY (piped/redirected), so logs
    # stay clean in files and under process managers.
    console = RichHandler(
        rich_tracebacks=True,       # next crash prints a highlighted traceback
        show_path=False,            # drop the file:line column
        markup=False,               # log text like "[B57BDF]" is literal, not markup
        omit_repeated_times=False,  # timestamp every line, even within the same second
        log_time_format=_CONSOLE_TIMEFMT,
    )
    console.setFormatter(_ShortNameFormatter(_CONSOLE_FMT))
    root.addHandler(console)

    # Everything at `level` and up -> rotating bot.log.
    file_all = RotatingFileHandler(
        _LOG_DIR / "bot.log", maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    file_all.setFormatter(file_formatter)
    root.addHandler(file_all)

    # Errors only -> rotating errors.log, so problems are easy to find.
    file_err = RotatingFileHandler(
        _LOG_DIR / "errors.log", maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
    )
    file_err.setLevel(logging.ERROR)
    file_err.setFormatter(file_formatter)
    root.addHandler(file_err)

    # Quiet the noisy library loggers; keep our own at `level`.
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
