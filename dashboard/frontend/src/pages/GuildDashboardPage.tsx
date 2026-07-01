import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { GuildIcon } from "../components/GuildIcon";
import { Alert, Skeleton } from "../components/ui";
import { useDirtyGuardContext } from "../lib/dirtyGuard";
import { springSoft } from "../lib/motion";
import type { GuildMeta } from "../lib/types";
import { MODULES, defaultModuleKey } from "./modules/registry";

function DashboardSkeleton() {
  return (
    <div className="container">
      <div className="page-header row" style={{ gap: 16 }}>
        <Skeleton width={44} height={44} radius="50%" />
        <div className="stack stack--sm">
          <Skeleton width={200} height={22} />
          <Skeleton width={140} height={13} />
        </div>
      </div>
      <div className="dash-layout">
        <div className="modnav">
          {MODULES.map((m) => (
            <Skeleton key={m.key} height={38} radius="var(--radius-md)" />
          ))}
        </div>
        <div className="stack">
          <Skeleton height={190} radius="var(--radius-lg)" />
          <Skeleton height={230} radius="var(--radius-lg)" />
        </div>
      </div>
    </div>
  );
}

export default function GuildDashboardPage() {
  const { guildId, moduleKey } = useParams();
  const navigate = useNavigate();
  const { confirmDiscard } = useDirtyGuardContext();

  const { data: meta, isLoading, isError, error } = useQuery<GuildMeta>({
    queryKey: ["meta", guildId],
    queryFn: () => api.get<GuildMeta>(`/guilds/${guildId}/meta`),
    enabled: !!guildId,
  });

  if (!guildId) return <Navigate to="/" replace />;
  if (!moduleKey) return <Navigate to={`/guilds/${guildId}/${defaultModuleKey}`} replace />;
  if (isLoading) return <DashboardSkeleton />;
  if (isError || !meta) {
    return (
      <div className="container">
        <Alert tone="danger">{(error as Error)?.message || "Couldn’t load this server."}</Alert>
      </div>
    );
  }

  const active = MODULES.find((m) => m.key === moduleKey) ?? MODULES[0];
  const Panel = active.component;

  return (
    <div className="container">
      <div className="page-header row" style={{ gap: 16 }}>
        <GuildIcon guild={meta.guild} />
        <div>
          <div className="page-header__title">{meta.guild.name}</div>
          <div className="page-header__desc">Server configuration</div>
        </div>
      </div>

      <div className="dash-layout">
        <nav className="modnav">
          {MODULES.map((m) => {
            const isActive = m.key === active.key;
            return (
              <div
                key={m.key}
                className={"modnav__item" + (isActive ? " modnav__item--active" : "")}
                onClick={() => {
                  if (isActive) return;
                  if (confirmDiscard()) navigate(`/guilds/${guildId}/${m.key}`);
                }}
              >
                {isActive && (
                  <motion.span className="modnav__indicator" layoutId="modnav-active" transition={springSoft} />
                )}
                <span className="modnav__label">
                  <span className="modnav__icon">{m.icon}</span> {m.label}
                </span>
              </div>
            );
          })}
        </nav>
        <main className="panel-stage">
          {/* No mode="wait": the incoming panel mounts immediately so its
              useDirtyGuard clears the guard flag at once (no lingering prompt),
              while the outgoing panel crossfades away on the shared stage. */}
          <AnimatePresence>
            <motion.div
              key={active.key}
              className="panel-layer"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.18 }}
            >
              <Panel guildId={guildId} meta={meta} />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
