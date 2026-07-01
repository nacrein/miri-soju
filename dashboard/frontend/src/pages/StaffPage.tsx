import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";

import { api } from "../api/client";
import { Alert, CenteredSpinner } from "../components/ui";
import { BotIcon } from "../lib/icons";
import { useCountUp, useGrow } from "../lib/reveal";
import type {
  CommandAnalytics,
  EconomyAnalytics,
  ErrorAnalytics,
  ModerationAnalytics,
  StaffSummary,
} from "../lib/types";

type Tab = "commands" | "economy" | "moderation" | "errors";

const fmt = (n: number) => n.toLocaleString();
const when = (iso: string) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
};

export default function StaffPage() {
  const [tab, setTab] = useState<Tab>("commands");
  const summary = useQuery<StaffSummary>({
    queryKey: ["staff", "summary"],
    queryFn: () => api.get<StaffSummary>("/staff/summary"),
  });

  return (
    <div className="container container--wide">
      <div className="page-header">
        <div className="row" style={{ gap: 10 }}>
          <div className="page-header__title">Staff analytics</div>
          <span className="badge badge--primary">bot-wide</span>
        </div>
        <div className="page-header__desc">
          Global, cross-server insight for Miri's staff — economy health, command usage, moderation,
          and errors.
        </div>
      </div>

      {summary.isLoading ? (
        <CenteredSpinner />
      ) : summary.isError ? (
        <Alert tone="danger">{(summary.error as Error)?.message || "Couldn't load analytics."}</Alert>
      ) : summary.data ? (
        <div className="stat-cards">
          <CountCard label="Bits in circulation" value={summary.data.economy.circulation} accent />
          <CountCard label="Economy players" value={summary.data.economy.players} />
          <CountCard label="Commands run" value={summary.data.commands.invocations} sub={`${fmt(summary.data.commands.unique_users)} users`} />
          <CountCard label="Mod cases" value={summary.data.mod_cases} />
          <CountCard label="Ledger rows" value={summary.data.ledger_rows} />
          <CountCard label="Errors (24h)" value={summary.data.errors_24h} sub={`${fmt(summary.data.errors_total)} all-time`} danger={summary.data.errors_24h > 0} />
        </div>
      ) : null}

      <div className="cmd-chips" style={{ marginTop: 24 }}>
        <TabButton icon="rank" fallback="📊" label="Command usage" active={tab === "commands"} onClick={() => setTab("commands")} />
        <TabButton icon="bits" fallback="🪙" label="Economy" active={tab === "economy"} onClick={() => setTab("economy")} />
        <TabButton icon="shield" fallback="🛡️" label="Moderation" active={tab === "moderation"} onClick={() => setTab("moderation")} />
        <TabButton icon="warning" fallback="⚠️" label="Errors" active={tab === "errors"} onClick={() => setTab("errors")} />
      </div>

      <div style={{ marginTop: 20 }}>
        {tab === "commands" && <CommandsTab />}
        {tab === "economy" && <EconomyTab />}
        {tab === "moderation" && <ModerationTab />}
        {tab === "errors" && <ErrorsTab />}
      </div>
    </div>
  );
}

// ── command usage ────────────────────────────────────────────────────────────
function CommandsTab() {
  const q = useQuery<CommandAnalytics>({
    queryKey: ["staff", "commands"],
    queryFn: () => api.get<CommandAnalytics>("/staff/commands"),
  });
  if (q.isLoading) return <CenteredSpinner />;
  if (q.isError || !q.data) return <Alert tone="danger">Couldn't load command analytics.</Alert>;
  const d = q.data;
  const noData = d.totals.invocations === 0;

  return (
    <div className="analytics-grid">
      {noData && (
        <Alert tone="info">
          No command usage recorded yet. Rows land here as people run commands (tracked from the
          bot's <span className="mono">on_command_completion</span> listener).
        </Alert>
      )}
      <div className="grid-2">
        <Panel title="Usage — last 14 days">
          <DayBars data={d.by_day} />
        </Panel>
        <Panel title="Busiest hours (UTC)">
          <HourBars data={d.by_hour} />
        </Panel>
      </div>
      <div className="grid-2">
        <Panel title="Top commands (all time)">
          <BarList items={d.top.map((t) => ({ label: t.command, value: t.count }))} unit="runs" />
        </Panel>
        <Panel title="Top commands (30 days)">
          <BarList items={d.top_30d.map((t) => ({ label: t.command, value: t.count }))} unit="runs" />
        </Panel>
      </div>
    </div>
  );
}

// ── economy ──────────────────────────────────────────────────────────────────
function EconomyTab() {
  const q = useQuery<EconomyAnalytics>({
    queryKey: ["staff", "economy"],
    queryFn: () => api.get<EconomyAnalytics>("/staff/economy"),
  });
  if (q.isLoading) return <CenteredSpinner />;
  if (q.isError || !q.data) return <Alert tone="danger">Couldn't load economy analytics.</Alert>;
  const d = q.data;
  const houseNet = -d.gambling_net;

  return (
    <div className="analytics-grid">
      <div className="grid-2">
        <Panel title="Bit flow — minted vs burned (14 days)">
          <FlowBars data={d.flow} />
          <div className="flow-legend faint">
            <span><i className="dot dot--pos" /> minted (faucets, wins)</span>
            <span><i className="dot dot--neg" /> burned (sinks, losses)</span>
          </div>
        </Panel>
        <Panel title="Casino ledger">
          <div className="casino">
            <div className="casino__row">
              <span className="muted">Players' net P/L</span>
              <span className={d.gambling_net >= 0 ? "pos" : "neg"}>
                {d.gambling_net >= 0 ? "+" : ""}{fmt(d.gambling_net)} bits
              </span>
            </div>
            <div className="casino__row">
              <span className="muted">House net (edge realized)</span>
              <span className={houseNet >= 0 ? "pos" : "neg"}>
                {houseNet >= 0 ? "+" : ""}{fmt(houseNet)} bits
              </span>
            </div>
            <p className="faint" style={{ marginTop: 8 }}>
              {houseNet >= 0
                ? "The house is ahead — games are net-draining bits from players."
                : "Players are ahead — the games are paying out more than they take."}
            </p>
          </div>
        </Panel>
      </div>
      <div className="grid-2">
        <Panel title="Where bits flow (by transaction kind)">
          {d.breakdown.length === 0 ? (
            <div className="muted">No transactions yet.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr><th>Kind</th><th className="num">Count</th><th className="num">Net bits</th></tr>
              </thead>
              <tbody>
                {d.breakdown.map((b) => (
                  <tr key={b.kind}>
                    <td className="mono">{b.kind}</td>
                    <td className="num">{fmt(b.count)}</td>
                    <td className={"num " + (b.net >= 0 ? "pos" : "neg")}>
                      {b.net >= 0 ? "+" : ""}{fmt(b.net)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
        <Panel title="Richest players (net worth)">
          <BarList items={d.top_net_worth.map((p) => ({ label: p.user_id, value: p.net_worth, mono: true }))} unit="bits" />
        </Panel>
      </div>
      <Panel title="Recent activity">
        {d.recent.length === 0 ? (
          <div className="muted">No activity yet.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>When</th><th>User</th><th>Kind</th><th className="num">Amount</th><th className="num">Balance</th></tr>
            </thead>
            <tbody>
              {d.recent.map((r, i) => (
                <tr key={i}>
                  <td className="muted nowrap">{when(r.created_at)}</td>
                  <td className="mono">{r.user_id}</td>
                  <td className="mono">{r.kind}</td>
                  <td className={"num " + (r.amount >= 0 ? "pos" : "neg")}>
                    {r.amount >= 0 ? "+" : ""}{fmt(r.amount)}
                  </td>
                  <td className="num">{fmt(r.balance_after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

// ── moderation ───────────────────────────────────────────────────────────────
function ModerationTab() {
  const q = useQuery<ModerationAnalytics>({
    queryKey: ["staff", "moderation"],
    queryFn: () => api.get<ModerationAnalytics>("/staff/moderation"),
  });
  if (q.isLoading) return <CenteredSpinner />;
  if (q.isError || !q.data) return <Alert tone="danger">Couldn't load moderation analytics.</Alert>;
  const d = q.data;

  return (
    <div className="analytics-grid">
      {d.total_cases === 0 && <Alert tone="info">No moderation cases logged yet.</Alert>}
      <Panel title={`Actions — last 14 days (${fmt(d.total_cases)} cases all-time)`}>
        <DayBars data={d.by_day} />
      </Panel>
      <Panel title="By action type">
        <BarList items={d.breakdown.map((b) => ({ label: b.kind, value: b.count, mono: true }))} unit="cases" />
      </Panel>
    </div>
  );
}

// ── errors ───────────────────────────────────────────────────────────────────
function ErrorsTab() {
  const q = useQuery<ErrorAnalytics>({
    queryKey: ["staff", "errors"],
    queryFn: () => api.get<ErrorAnalytics>("/staff/errors"),
  });
  if (q.isLoading) return <CenteredSpinner />;
  if (q.isError || !q.data) return <Alert tone="danger">Couldn't load error logs.</Alert>;
  const d = q.data;

  return (
    <div className="analytics-grid">
      <Panel title={`Recent errors — ${fmt(d.errors_24h)} in the last 24h, ${fmt(d.errors_total)} all-time`}>
        {d.recent.length === 0 ? (
          <div className="muted">No errors logged. 🎉</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>Code</th><th>Type</th><th>Context</th><th>Message</th><th>When</th></tr>
            </thead>
            <tbody>
              {d.recent.map((e) => (
                <tr key={e.code + e.created_at}>
                  <td><span className="chip">{e.code}</span></td>
                  <td className="mono">{e.exc_type}</td>
                  <td className="muted">{e.context}</td>
                  <td className="err-msg">{e.message}</td>
                  <td className="muted nowrap">{when(e.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}

// ── shared bits ──────────────────────────────────────────────────────────────
function CountCard({
  label, value, sub, accent, danger,
}: { label: string; value: number; sub?: string; accent?: boolean; danger?: boolean }) {
  const n = useCountUp(value, 1100);
  return (
    <div className={"stat-card" + (accent ? " stat-card--accent" : "")}>
      <div className="stat-card__label">{label}</div>
      <div className={"stat-card__value" + (danger ? " stat-card__value--danger" : "")}>{fmt(n)}</div>
      {sub && <div className="stat-card__sub faint">{sub}</div>}
    </div>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="card">
      <div className="card__header"><div className="card__title">{title}</div></div>
      <div className="card__body">{children}</div>
    </div>
  );
}

function TabButton({ icon, fallback, label, active, onClick }: { icon: string; fallback: string; label: string; active: boolean; onClick: () => void }) {
  return (
    <button className={"cmd-chip" + (active ? " cmd-chip--active" : "")} onClick={onClick}>
      <BotIcon name={icon} fallback={fallback} /> {label}
    </button>
  );
}

function BarList({ items, unit }: { items: { label: string; value: number; mono?: boolean }[]; unit: string }) {
  const grown = useGrow();
  if (items.length === 0) return <div className="muted">Nothing yet.</div>;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="bar-list">
      {items.map((it, i) => (
        <div key={i} className="bar-row">
          <div className={"bar-row__label" + (it.mono ? " mono" : "")} title={it.label}>{it.label}</div>
          <div className="bar-row__track">
            <div className="bar-row__fill" style={{ width: grown ? `${(it.value / max) * 100}%` : 0 }} />
          </div>
          <div className="bar-row__value">{fmt(it.value)} <span className="faint">{unit}</span></div>
        </div>
      ))}
    </div>
  );
}

function DayBars({ data }: { data: { day: string; count: number }[] }) {
  const grown = useGrow();
  if (data.length === 0) return <div className="muted">No data in this window.</div>;
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="day-bars">
      {data.map((d) => (
        <div key={d.day} className="day-bar" title={`${d.day}: ${d.count}`}>
          <div className="day-bar__fill" style={{ height: grown ? `${(d.count / max) * 100}%` : 0 }} />
          <div className="day-bar__label">{d.day.slice(5)}</div>
        </div>
      ))}
    </div>
  );
}

function HourBars({ data }: { data: { hour: number; count: number }[] }) {
  const grown = useGrow();
  const counts = new Array(24).fill(0);
  for (const d of data) counts[d.hour] = d.count;
  const max = Math.max(...counts, 1);
  if (data.length === 0) return <div className="muted">No usage recorded.</div>;
  return (
    <div className="day-bars day-bars--hours">
      {counts.map((c, h) => (
        <div key={h} className="day-bar" title={`${h}:00 — ${c}`}>
          <div className="day-bar__fill" style={{ height: grown ? `${(c / max) * 100}%` : 0 }} />
          {h % 3 === 0 && <div className="day-bar__label">{h}</div>}
        </div>
      ))}
    </div>
  );
}

function FlowBars({ data }: { data: { day: string; minted: number; burned: number }[] }) {
  const grown = useGrow();
  if (data.length === 0) return <div className="muted">No flow in this window.</div>;
  const max = Math.max(...data.map((d) => Math.max(d.minted, Math.abs(d.burned))), 1);
  return (
    <div className="flow-bars">
      {data.map((d) => (
        <div key={d.day} className="flow-col" title={`${d.day}: +${fmt(d.minted)} / ${fmt(d.burned)}`}>
          <div className="flow-col__up">
            <div className="flow-col__pos" style={{ height: grown ? `${(d.minted / max) * 100}%` : 0 }} />
          </div>
          <div className="flow-col__down">
            <div className="flow-col__neg" style={{ height: grown ? `${(Math.abs(d.burned) / max) * 100}%` : 0 }} />
          </div>
          <div className="day-bar__label">{d.day.slice(5)}</div>
        </div>
      ))}
    </div>
  );
}
