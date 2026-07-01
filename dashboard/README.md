# Miri Dashboard

The bot's website + web control panel. Three layers, one same-origin app:

1. **Public marketing site** — a landing page, a searchable **Commands** catalog
   (all ~300 commands, generated from the bot's own source), and a live **Embed
   Builder**. No login required.
2. **Server dashboard** — server admins log in with Discord and configure the
   bot's per-guild settings (leveling, automod, server logging, moderation,
   prefix) from a browser instead of `,setup` commands in chat. Lives under
   `/dashboard`.
3. **Staff analytics** — a bot-staff-only area (`/staff`) with global, cross-server
   insight: command-usage charts, moderation activity, and the error log. Gated by the
   same `OWNER_ID`/`STAFF_IDS` the in-Discord `,staff` commands use.

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

Config-wise, no — only through the shared database, by design. The dashboard:
- runs as a **separate process** (its own DB connection pool).
- uses the bot token **only for read-only** Discord REST calls (a guild's roles/
  channels for the dropdowns) — it does not connect to the gateway or send messages.
- keeps its web dependencies in `dashboard/requirements.txt`, **not** in the bot's
  `pyproject.toml`.

**One deliberate exception — command-usage tracking (for staff analytics).** The
staff area's command-usage charts need data nothing recorded before, so this feature
adds a small, self-contained, opt-in-by-existing bot-side piece:
- a new `command_usage` table (model `src/database/models/command_usage.py` +
  Alembic migration `e2f3a4b5c6d7`),
- a listener cog `src/modules/analytics/` that writes one row per completed
  command (best-effort; it can never break a command),
- read-only aggregate helpers on the moderation repository and `core/error_log`.

None of this changes existing command behaviour. If you don't want it, don't run
the migration and skip the analytics cog — the rest of the dashboard is unaffected.

A config change only reaches the bot when someone clicks **Save** (it writes the
same tables the bot reads). The bot picks it up near-instantly on Postgres (see
[How a save reaches the running bot](#how-a-save-reaches-the-running-bot-cache-invalidation)).

## How a save reaches the running bot (cache invalidation)

**Config changes take effect near-instantly on Postgres.** The bot serves each
module's config from an in-process `TTLCache` (300 s TTL). To keep a dashboard write
from staying invisible until that TTL lapses, the two processes are wired over
Postgres `LISTEN`/`NOTIFY` (`src/core/cache_sync.py`):

1. After a successful config write the dashboard `pg_notify`s the guild id
   (`app.py`'s post-write middleware → `publish_guild_changed`).
2. The bot `LISTEN`s on that channel (started in `Bot.setup_hook`) and calls
   `cache.invalidate_guild`, dropping that guild from **every** registered cache.

So a **Save** propagates to the live bot in milliseconds. The 300 s TTL now only
acts as a backstop — if the listener is momentarily reconnecting, or you're running
on **SQLite** (dev), where `LISTEN`/`NOTIFY` is a no-op and staleness is bounded by
the TTL instead. Production (Postgres) does not have the old ~5-minute lag.

## Known limitations

- **Dashboard access is re-checked at login, not continuously.** Who-can-manage-what
  is computed once at login (the user's admin guilds ∩ the bot's guilds) and trusted
  for the session. Revoking someone's Manage Server in Discord removes their dashboard
  access at their next login / within the session window, not instantly. The window is
  **8 hours by default**; set `DASHBOARD_SESSION_MAX_AGE` (seconds) to shorten it —
  `7200` (2h) is a good tighter default. Because admins can only edit bot config (not
  perform destructive server actions), a short stale window is usually an acceptable
  trade-off; shorten it if that blast radius matters to you.

## Deploying & schema migrations

The dashboard and the bot are **two processes that share one database and import the
same models from `src/`**, so they must run the **same code revision** — a mismatch
(e.g. the dashboard on new models while a migration hasn't run) throws against the
old schema. When a change includes an Alembic migration, deploy in this order:

1. **Additive migrations** (new table/column — the common case, e.g. this release's
   `command_usage`) are backward-compatible: existing code ignores the new shape. Safe
   order: apply the migration, then roll both processes onto the new code. Old code
   keeps working against the pre-migration shape in between.
2. **Destructive migrations** (drop/rename/retype a column both processes read) are
   **not** backward-compatible. Take a short maintenance window: stop the dashboard,
   `alembic upgrade head`, deploy the new code to **both** the bot and the dashboard,
   then start them. Don't leave one process on old code against the migrated schema.

Run migrations **once** (they're global, not per-process). Keep the bot and dashboard
pinned to the same commit so their model definitions never disagree with the DB.

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
| `routers/` | One router per module; each reuses that module's existing repository/service. `leveling.py` is the reference shape. `staff.py` is the bot-wide analytics router (gated by `require_staff`). |
| `deps.py` | `get_current_user`, `require_guild` (guild gate), `require_staff` (staff gate — reads the bot's DB `staff_members` roster via `staff_roster`, with `OWNER_ID`/`STAFF_IDS` as an env floor). |
| `app.py` | App factory: session middleware, mounts `/api/*`, `/api/meta` (public invite link), serves the built SPA. |
| `frontend/src/components/ui/` | The design-system component library (tokens in `styles/tokens.css`). |
| `frontend/src/lib/useConfigForm.ts` | The shared load→edit→save hook every panel uses. |
| `frontend/src/pages/` | `LandingPage`, `CommandsPage`, `EmbedBuilderPage` (public); `GuildPickerPage`/`GuildDashboardPage` (dashboard); `StaffPage` (staff). |
| `frontend/src/pages/modules/` | One panel per module + `registry.ts` (the nav). `LevelingPanel.tsx` is the reference. |
| `frontend/src/data/commands.json` | The command catalog powering the Commands page. **Generated** by `scripts/dump_commands.py` — re-run it when commands change (it parses the cogs; no bot/DB needed). |

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
