"""Run the dashboard API: ``python -m dashboard`` (from the repo root).

A thin uvicorn launcher. Host/port/reload come from the environment so dev and
prod differ only by env, not code.
"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "dashboard.app:app",
        host=os.environ.get("DASHBOARD_HOST", "127.0.0.1"),
        port=int(os.environ.get("DASHBOARD_PORT", "8000")),
        reload=os.environ.get("DASHBOARD_RELOAD", "0") == "1",
    )


if __name__ == "__main__":
    main()
