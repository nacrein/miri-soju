"""Web dashboard for the bot.

A standalone FastAPI app that reuses the bot's models, async engine, and module
repositories (``src/``) to read and write per-guild configuration over HTTP. It
runs as its own process against the *same* database the bot uses, so config
edited here is picked up by the running bot (immediately, or within its config
cache TTL — see the README).

Core never imports this package; the dependency only points dashboard → src.
"""
