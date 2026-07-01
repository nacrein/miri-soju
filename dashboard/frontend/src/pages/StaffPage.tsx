import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useState } from "react";

import { api } from "../api/client";
import { Alert, CenteredSpinner } from "../components/ui";
import type {
  CommandAnalytics,
  EconomyAnalytics,
  ErrorAnalytics,
  StaffSummary,
} from "../lib/types";

type Tab = "commands" | "economy" | "errors";

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
          Global, cross-server insight for Miri's staff — economy health, command usage, and errors.
        </div>
      </div>

      {summary.isLoading ? (
        <CenteredSpinner />
      ) : summary.isError ? (
        <Alert tone="danger">{(summary.error as Error)?.message || "Couldn't load analytics."}</Alert>
      ) : summary.data ? (
        <div className="stat-cards">
          <StatCard label="Bits in circulation" value={fmt(summary.data.economy.circulation)} accent />
          <StatCard label="Economy players" value={fmt(summary.data.economy.players)} />
          <StatCard label="Commands run" value={fmt(summary.data.commands.invocations)} sub={`${fmt(summary.data.commands.unique_users)} users`} />
          <StatCard label="Ledger rows" value={fmt(summary.data.ledger_rows)} />
          <StatCard label="Errors (24h)" value={fmt(summary.data.errors_24h)} sub={`${fmt(summary.data.errors_total)} all-time`} tone={summary.data.errors_24h > 0 ? "danger" : undefined} />
        </div>
      ) : null}

      <div className="cmd-chips" style={{ marginTop: 24 }}>
        <TabButton label="📊 Command usage" active={tab === "commands"} onClick={() => setTab("commands")} />
        <TabButton label="🪙 Economy" active={tab === "economy"} onClick={() => setTab("economy")} />
        <TabButton label="⚠️ Errors" active={tab === "errors"} onClick={() => setTab("errors")} />
      </div>

      <div style={{ marginTop: 20 }}>
        {tab === "commands" && <CommandsTab />}
        {tab === "economy" && <EconomyTab />}
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
      <Panel title="Usage — last 14 days">
        <DayBars data={d.by_day} />
      </Panel>
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

  return (
    <div className="analytics-grid">
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
          <BarList
            items={d.top_net_worth.map((p) => ({ label: p.user_id, value: p.net_worth, mono: true }))}
            unit="bits"
          />
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
function StatCard({
  label, value, sub, accent, tone,
}: { label: string; value: string; sub?: string; accent?: boolean; tone?: "danger" }) {
  return (
    <div className={"stat-card" + (accent ? " stat-card--accent" : "")}>
      <div className="stat-card__label">{label}</div>
      <div className={"stat-card__value" + (tone === "danger" ? " stat-card__value--danger" : "")}>{value}</div>
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

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button className={"cmd-chip" + (active ? " cmd-chip--active" : "")} onClick={onClick}>
      {label}
    </button>
  );
}

function BarList({ items, unit }: { items: { label: string; value: number; mono?: boolean }[]; unit: string }) {
  if (items.length === 0) return <div className="muted">Nothing yet.</div>;
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="bar-list">
      {items.map((it, i) => (
        <div key={i} className="bar-row">
          <div className={"bar-row__label" + (it.mono ? " mono" : "")} title={it.label}>{it.label}</div>
          <div className="bar-row__track">
            <div className="bar-row__fill" style={{ width: `${(it.value / max) * 100}%` }} />
          </div>
          <div className="bar-row__value">{fmt(it.value)} <span className="faint">{unit}</span></div>
        </div>
      ))}
    </div>
  );
}

function DayBars({ data }: { data: { day: string; count: number }[] }) {
  if (data.length === 0) return <div className="muted">No usage in this window.</div>;
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="day-bars">
      {data.map((d) => (
        <div key={d.day} className="day-bar" title={`${d.day}: ${d.count}`}>
          <div className="day-bar__fill" style={{ height: `${(d.count / max) * 100}%` }} />
          <div className="day-bar__label">{d.day.slice(5)}</div>
        </div>
      ))}
    </div>
  );
}
