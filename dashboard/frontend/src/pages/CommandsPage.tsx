import { useMemo, useState } from "react";

import catalog from "../data/commands.json";
import type { CommandCatalog, CommandEntry } from "../lib/types";

const CATALOG = catalog as CommandCatalog;

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

function matches(cmd: CommandEntry, q: string): boolean {
  if (!q) return true;
  const hay = (cmd.name + " " + cmd.aliases.join(" ") + " " + cmd.description).toLowerCase();
  return hay.includes(q);
}

export default function CommandsPage() {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState<string>("All");

  const q = query.trim().toLowerCase();
  const filtered = useMemo(() => {
    return CATALOG.categories
      .filter((cat) => active === "All" || cat.name === active)
      .map((cat) => ({ ...cat, commands: cat.commands.filter((c) => matches(c, q)) }))
      .filter((cat) => cat.commands.length > 0);
  }, [q, active]);

  const shown = filtered.reduce((n, c) => n + c.commands.length, 0);

  return (
    <div className="container container--wide">
      <div className="page-header">
        <div className="page-header__title">Commands</div>
        <div className="page-header__desc">
          Every command Miri knows — {CATALOG.total} across {CATALOG.categories.length} categories.
          The default prefix is <span className="mono">,</span>.
        </div>
      </div>

      <div className="cmd-toolbar">
        <input
          className="input cmd-search"
          placeholder="Search commands, aliases, descriptions…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="cmd-toolbar__count muted">{shown} shown</span>
      </div>

      <div className="cmd-chips">
        <Chip label="All" active={active === "All"} onClick={() => setActive("All")} />
        {CATALOG.categories.map((cat) => (
          <Chip
            key={cat.name}
            label={`${CATEGORY_ICON[cat.name] ?? ""} ${cat.name}`.trim()}
            active={active === cat.name}
            onClick={() => setActive(cat.name)}
          />
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="empty" style={{ marginTop: 24 }}>
          No commands match “{query}”.
        </div>
      ) : (
        filtered.map((cat) => (
          <section key={cat.name} className="cmd-section">
            <div className="cmd-section__head">
              <span className="cmd-section__icon">{CATEGORY_ICON[cat.name] ?? "✨"}</span>
              <h2 className="cmd-section__title">{cat.name}</h2>
              <span className="badge">{cat.commands.length}</span>
              <span className="muted cmd-section__desc">{cat.description}</span>
            </div>
            <div className="cmd-list">
              {cat.commands.map((cmd) => (
                <CommandRow key={cmd.name} cmd={cmd} />
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}

function CommandRow({ cmd }: { cmd: CommandEntry }) {
  return (
    <div className="cmd-row">
      <div className="cmd-row__head">
        <code className="cmd-row__name">
          ,{cmd.name}
          {cmd.signature && <span className="cmd-row__sig"> {cmd.signature}</span>}
        </code>
        {cmd.is_group && <span className="badge badge--primary">group</span>}
        {cmd.aliases.map((a) => (
          <span key={a} className="chip cmd-row__alias">{a}</span>
        ))}
      </div>
      {cmd.description && <div className="cmd-row__desc">{cmd.description}</div>}
      {cmd.example && (
        <div className="cmd-row__example mono">
          e.g. <span>,{cmd.example}</span>
        </div>
      )}
    </div>
  );
}

function Chip({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button className={"cmd-chip" + (active ? " cmd-chip--active" : "")} onClick={onClick}>
      {label}
    </button>
  );
}
