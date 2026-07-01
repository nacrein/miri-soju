import { useQuery } from "@tanstack/react-query";
import type { CSSProperties } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import { useSession } from "../auth/session";
import catalog from "../data/commands.json";
import type { BotMeta, CommandCatalog } from "../lib/types";

const CATALOG = catalog as CommandCatalog;

// One glyph per category, keyed by the names in help/categories.py.
const CATEGORY_ICON: Record<string, string> = {
  Economy: "🪙",
  Leveling: "📈",
  Moderation: "🛡️",
  "Server Setup": "⚙️",
  Utility: "🧰",
  Music: "🎵",
  Fun: "🎉",
  Bot: "👑",
};

function useInviteUrl(): string {
  const { data } = useQuery<BotMeta>({
    queryKey: ["meta"],
    queryFn: () => api.get<BotMeta>("/meta"),
    staleTime: Infinity,
    retry: false,
  });
  return data?.invite_url ?? "/dashboard";
}

export default function LandingPage() {
  const invite = useInviteUrl();
  const { data: session } = useSession();
  const categoryCount = CATALOG.categories.length;

  return (
    <div className="landing">
      {/* ── hero ─────────────────────────────────────────────────────────── */}
      <section className="hero">
        <div className="hero__glow" aria-hidden />
        <div className="hero__inner">
          <span className="eyebrow">The warm all-in-one Discord bot</span>
          <h1 className="hero__title">
            Run your server
            <br />
            with <span className="hero__accent">warmth</span>.
          </h1>
          <p className="hero__subtitle">
            Economy, leveling, moderation, automod, music and more — {CATALOG.total} commands
            across {categoryCount} categories, every one configurable from a dashboard built for
            humans, not config files.
          </p>
          <div className="hero__cta">
            <a className="btn btn--primary btn--lg" href={invite}>
              Add to Discord
            </a>
            <Link className="btn btn--ghost btn--lg" to="/dashboard">
              {session ? "Open dashboard" : "Open dashboard →"}
            </Link>
          </div>
          <div className="hero__stats">
            <Stat value={CATALOG.total.toString()} label="Commands" />
            <Stat value={categoryCount.toString()} label="Categories" />
            <Stat value="Browser" label="No config files" />
          </div>
        </div>
      </section>

      {/* ── feature grid (from the real catalog) ─────────────────────────── */}
      <section className="section">
        <div className="section__head">
          <h2 className="section__title">Everything your community needs</h2>
          <p className="section__desc">
            One bot, cleanly split into focused modules. Each is a click away in Discord and on the
            dashboard.
          </p>
        </div>
        <div className="feature-grid">
          {CATALOG.categories.map((cat) => (
            <Link key={cat.name} to="/commands" className="feature-card">
              <div className="feature-card__icon">{CATEGORY_ICON[cat.name] ?? "✨"}</div>
              <div className="feature-card__title">{cat.name}</div>
              <p className="feature-card__desc">{cat.description}</p>
              <div className="feature-card__meta">{cat.commands.length} commands →</div>
            </Link>
          ))}
        </div>
      </section>

      {/* ── dashboard highlight ──────────────────────────────────────────── */}
      <section className="section split">
        <div className="split__text">
          <span className="eyebrow">Server dashboard</span>
          <h2 className="section__title">Configure once, from the browser</h2>
          <p className="section__desc">
            Log in with Discord and every server you manage shows up. Tune leveling, automod rules,
            server logging, moderation and the command prefix with real forms, live validation, and
            a save bar that never lets you lose a change.
          </p>
          <ul className="checklist">
            <li>Leveling — XP rates, rewards, per-channel multipliers</li>
            <li>AutoMod — filters, strike thresholds, exemptions</li>
            <li>Server Log — pick exactly what gets logged, and where</li>
            <li>Moderation &amp; Prefix — jail role, custom prefix</li>
          </ul>
          <Link className="btn btn--primary" to="/dashboard">
            Open your dashboard
          </Link>
        </div>
        <div className="split__visual">
          <div className="mock-window">
            <div className="mock-window__bar">
              <span className="dot" style={{ background: "var(--danger)" }} />
              <span className="dot" style={{ background: "var(--warning)" }} />
              <span className="dot" style={{ background: "var(--success)" }} />
            </div>
            <div className="mock-window__body">
              <div className="mock-row"><span>Enable leveling</span><span className="switch" data-on="true" /></div>
              <div className="mock-row"><span>XP per message</span><span className="mock-pill">15</span></div>
              <div className="mock-row"><span>Announce level-ups</span><span className="mock-pill">#level-ups</span></div>
              <div className="mock-row"><span>Reward @ level 10</span><span className="mock-pill">@Regular</span></div>
              <div className="mock-savebar"><span className="faint">Unsaved changes</span><span className="btn btn--primary btn--sm">Save</span></div>
            </div>
          </div>
        </div>
      </section>

      {/* ── embed builder highlight ──────────────────────────────────────── */}
      <section className="section split split--reverse">
        <div className="split__text">
          <span className="eyebrow">Embed Builder</span>
          <h2 className="section__title">Design embeds, live</h2>
          <p className="section__desc">
            Build a rich embed with a live Discord-accurate preview, then copy the script straight
            into <span className="mono">,ce</span>. Same length limits and color rules as the bot, so
            what you preview is exactly what posts.
          </p>
          <Link className="btn btn--primary" to="/embed">
            Open the builder
          </Link>
        </div>
        <div className="split__visual">
          <div className="embed-preview" style={{ "--embed-color": "#c56b5c" } as CSSProperties}>
            <div className="embed-preview__accent" />
            <div className="embed-preview__content">
              <div className="embed-preview__author">Miri</div>
              <div className="embed-preview__title">Welcome to the server 🌸</div>
              <div className="embed-preview__desc">
                Grab your roles, read the rules, and say hi. Type <span className="mono">,help</span>{" "}
                to see everything I can do.
              </div>
              <div className="embed-preview__footer">Miri · today</div>
            </div>
          </div>
        </div>
      </section>

      {/* ── final CTA ────────────────────────────────────────────────────── */}
      <section className="cta-band">
        <div className="cta-band__inner">
          <h2 className="section__title">Ready to bring Miri home?</h2>
          <p className="section__desc">Add the bot, open the dashboard, and you're running in minutes.</p>
          <div className="hero__cta">
            <a className="btn btn--primary btn--lg" href={invite}>Add to Discord</a>
            <Link className="btn btn--ghost btn--lg" to="/commands">Browse commands</Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="stat">
      <div className="stat__value">{value}</div>
      <div className="stat__label">{label}</div>
    </div>
  );
}
