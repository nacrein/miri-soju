import { useQuery } from "@tanstack/react-query";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import { GuildIcon } from "../components/GuildIcon";
import { Alert, CenteredSpinner } from "../components/ui";
import { useDirtyGuardContext } from "../lib/dirtyGuard";
import type { GuildMeta } from "../lib/types";
import { MODULES, defaultModuleKey } from "./modules/registry";

export default function GuildDashboardPage() {
  const { guildId, moduleKey } = useParams();
  const navigate = useNavigate();
  const { confirmDiscard } = useDirtyGuardContext();

  const { data: meta, isLoading, isError, error } = useQuery<GuildMeta>({
    queryKey: ["meta", guildId],
    queryFn: () => api.get<GuildMeta>(`/guilds/${guildId}/meta`),
    enabled: !!guildId,
  });

  if (!guildId) return <Navigate to="/dashboard" replace />;
  if (!moduleKey) return <Navigate to={`/dashboard/guilds/${guildId}/${defaultModuleKey}`} replace />;
  if (isLoading) return <CenteredSpinner />;
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
          {MODULES.map((m) => (
            <div
              key={m.key}
              className={"modnav__item" + (m.key === active.key ? " modnav__item--active" : "")}
              onClick={() => {
                if (m.key === active.key) return;
                if (confirmDiscard()) navigate(`/dashboard/guilds/${guildId}/${m.key}`);
              }}
            >
              <span className="modnav__icon">{m.icon}</span> {m.label}
            </div>
          ))}
        </nav>
        <main>
          <Panel guildId={guildId} meta={meta} />
        </main>
      </div>
    </div>
  );
}
