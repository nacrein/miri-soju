import type { ReactNode } from "react";

// ── badge ───────────────────────────────────────────────────────────────────
type Tone = "default" | "success" | "danger" | "warning" | "primary";

export function Badge({ tone = "default", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={"badge" + (tone !== "default" ? ` badge--${tone}` : "")}>{children}</span>;
}

// ── spinner ─────────────────────────────────────────────────────────────────
export function Spinner() {
  return <div className="spinner" role="status" aria-label="Loading" />;
}

export function CenteredSpinner() {
  return (
    <div className="center-screen">
      <Spinner />
    </div>
  );
}

// ── alert ───────────────────────────────────────────────────────────────────
export function Alert({ tone = "info", children }: { tone?: "info" | "danger"; children: ReactNode }) {
  return <div className={`alert alert--${tone}`}>{children}</div>;
}

// ── empty state ─────────────────────────────────────────────────────────────
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
