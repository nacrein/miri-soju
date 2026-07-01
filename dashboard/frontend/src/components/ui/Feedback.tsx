import type { CSSProperties, ReactNode } from "react";
import { motion } from "framer-motion";

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
    <motion.div
      className="center-screen"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <Spinner />
    </motion.div>
  );
}

// ── skeleton (shimmering placeholder while data loads) ───────────────────────
interface SkeletonProps {
  width?: number | string;
  height?: number | string;
  radius?: number | string;
  style?: CSSProperties;
}

export function Skeleton({ width = "100%", height = 16, radius, style }: SkeletonProps) {
  return <div className="skeleton" style={{ width, height, borderRadius: radius, ...style }} />;
}

// ── alert ───────────────────────────────────────────────────────────────────
export function Alert({ tone = "info", children }: { tone?: "info" | "danger"; children: ReactNode }) {
  return (
    <motion.div
      className={`alert alert--${tone}`}
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28 }}
    >
      {children}
    </motion.div>
  );
}

// ── empty state ─────────────────────────────────────────────────────────────
export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}
