# Miri Dashboard

A web control panel for the bot: server admins log in with Discord and configure
the bot's per-guild settings (leveling, automod, server logging, moderation,
prefix) from a browser instead of `,setup` commands in chat.

It is a **standalone FastAPI + React app** that reuses the bot's own models,
async engine, and module repositories from `src/`. It runs as its **own process**
against the **same database** the bot uses — so config edited here is what the bot
reads. It never modifies the bot, and the bot never imports it (the dependency
only points `dashboard → src`).

```
Browser (React/Vite)  ──/api──▶  FastAPI (dashboard/)  ──asyncpg──▶  Postgres  ◀──  bot (discord.py)
        │                              │                                              (same tables)
        └─ "Login with Discord" ───────┘  session = your admin guilds ∩ the bot's guilds
```

## Does this affect the bot?

No, except through the shared database — by design. The dashboard:
- adds **only** the `dashboard/` folder; it edits no existing bot file.
- runs as a **separate process** (its own DB connection pool).
- uses the bot token **only for read-only** Discord REST calls (a guild's roles/
  channels for the dropdowns) — it does not connect to the gateway or send messages.
- keeps its web dependencies in `dashboard/requirements.txt`, **not** in the bot's
  `pyproject.toml`.

A config change only reaches the bot when someone clicks **Save** (it writes the
same tables the bot reads). The bot picks it up immediately, or within its config
cache TTL (see Known limitations).

## Known limitations

These are deliberate trade-offs for keeping the dashboard a separate, additive
process that never modifies the bot. Both have clean fixes that require a small
**bot-side** change — left for a later phase.

- **Config changes can lag up to ~5 minutes.** The bot caches each module's config
  in-process (a 300 s TTL) and only invalidates that cache from its own command
  handlers. The dashboard writes the database directly (correct data), but can't
  reach into the running bot's memory to invalidate it — so a change may take up
  to the TTL to take effect live (most visible for the command prefix). *Fix when
  ready:* have the dashboard `NOTIFY` a Postgres channel after each save and the
  bot `LISTEN` and invalidate the matching cache (instant, ~30 lines bot-side).
- **Dashboard access is re-checked at login, not continuously.** Who-can-manage-what
  is computed once at login (the user's admin guilds ∩ the bot's guilds) and trusted
  for the session (**8 hours**). Revoking someone's Manage Server in Discord removes
  their dashboard access at their next login / within 8 h, not instantly. Shorten
  `max_age` in `app.py` to tighten the window.

## One-time setup

### 1. Create a Discord OAuth2 app
In the [Discord Developer Portal](https://discord.com/developers/applications) →
your application → **OAuth2**:
- Copy the **Client ID** (same as the bot's application id) and **Client Secret**.
- Under **Redirects**, add: `http://localhost:5173/api/auth/callback` (dev).

### 2. Configure env
Add these to the bot's existing `.env` at the repo root (it already has
`BOT_TOKEN`, `DATABASE_URL`, `OWNER_ID`, `STAFF_IDS`, …). See
[.env.example](.env.example):

```
DISCORD_CLIENT_ID=your_application_id
DISCORD_CLIENT_SECRET=your_oauth2_client_secret
OAUTH_REDIRECT_URI=http://localhost:5173/api/auth/callback
DASHBOARD_FRONTEND_URL=http://localhost:5173
DASHBOARD_SESSION_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
```

### 3. Install dependencies
```bash
# Backend — into the SAME virtualenv the bot uses (it imports src/):
pip install -r dashboard/requirements.txt

# Frontend:
cd dashboard/frontend && npm install
```

## Running (development)

Two terminals, from the repo root:

```bash
# 1) API on :8000
python -m dashboard            # set DASHBOARD_RELOAD=1 for autoreload

# 2) Frontend on :5173 (proxies /api → :8000)
cd dashboard/frontend && npm run dev
```

Open http://localhost:5173 and log in with Discord.

## Building for production

```bash
cd dashboard/frontend && npm run build      # outputs dashboard/frontend/dist/
```

When `dist/` exists, the FastAPI app serves it directly, so the whole thing is one
same-origin service. In production set `OAUTH_REDIRECT_URI` and
`DASHBOARD_FRONTEND_URL` to your real domain and `DASHBOARD_COOKIE_SECURE=1`, and
run behind HTTPS (e.g. `uvicorn dashboard.app:app --host 0.0.0.0 --port 8000`).

## How access control works

- **Login** is Discord OAuth2 (`identify guilds`). The session stores the user and
  the set of guilds they may manage, computed once at login as
  **their admin guilds ∩ the guilds the bot is in**.
- Every config endpoint goes through `require_guild` (see `deps.py`): the guild id
  in the URL is only honored if it's in that session set. The browser is never
  trusted to assert what it can manage.

## Architecture / where things are

| Path | Role |
|---|---|
| `config.py` | Dashboard settings (OAuth creds, session secret) — reuses the bot's `Settings` for the bot token + DB. |
| `discord_api.py` | Async Discord REST client (OAuth exchange; bot-auth roles/channels/guilds, cached). |
| `deps.py` | `get_current_user`, `require_guild` (the auth gate). |
| `schemas.py` | The wire contract. Snowflakes are strings; validation ranges are imported from the bot's own config modules so web + commands can't drift. |
| `routers/` | One router per module; each reuses that module's existing repository/service. `leveling.py` is the reference shape. |
| `app.py` | App factory: session middleware, mounts `/api/*`, serves the built SPA. |
| `frontend/src/components/ui/` | The design-system component library (tokens in `styles/tokens.css`). |
| `frontend/src/lib/useConfigForm.ts` | The shared load→edit→save hook every panel uses. |
| `frontend/src/pages/modules/` | One panel per module + `registry.ts` (the nav). `LevelingPanel.tsx` is the reference. |

## Adding a module

The dashboard is intentionally **not** auto-generated, so a new module is two
small files + one line (existing settings stay in sync automatically; new ones
need this):

1. **Backend** — `dashboard/schemas.py`: add `<Module>ConfigOut/In`. Then
   `dashboard/routers/<module>.py`: copy `leveling.py`, point it at the module's
   repository. Register it in `app.py`'s `api_routers` tuple.
2. **Frontend** — `frontend/src/lib/types.ts`: add the wire interface. Then
   `frontend/src/pages/modules/<Module>Panel.tsx`: copy `LevelingPanel.tsx`. Add
   one line to `frontend/src/pages/modules/registry.ts`.
