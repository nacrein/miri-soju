"""Test bootstrap — runs before any ``src``/``config`` import.

The app reads ``BOT_TOKEN`` and ``DATABASE_URL`` from the environment *at import
time* (``config.settings`` defines them with no defaults, and
``src.database.session`` builds the engine on import). So they MUST be set here,
in a conftest, which pytest imports before collecting the sibling test modules.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("BOT_TOKEN", "test-token-not-real")
os.environ.setdefault("OWNER_ID", "1")

# A file-based SQLite DB (not :memory:) so every async connection — including
# any background task loop a cog starts on load — sees the same schema.
_fd, _path = tempfile.mkstemp(prefix="miri_test_", suffix=".sqlite")
os.close(_fd)
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_path.replace(chr(92), '/')}")
