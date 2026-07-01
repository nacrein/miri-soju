import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";
import { Button, Card, CenteredSpinner, Empty, Select } from "../../components/ui";
import type { AutorolesConfig } from "../../lib/types";
import { useConfigAction } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

export default function AutorolesPanel({ guildId, meta }: PanelProps) {
  const queryKey = ["autoroles", guildId];
  const path = `/guilds/${guildId}/autoroles`;
  const query = useQuery<AutorolesConfig>({
    queryKey,
    queryFn: () => api.get<AutorolesConfig>(path),
    staleTime: 30_000,
  });
  const action = useConfigAction<AutorolesConfig>(queryKey);
  const [newRole, setNewRole] = useState<string | null>(null);

  if (query.isLoading || !query.data) return <CenteredSpinner />;
  const roles = query.data.roles;
  const roleName = (id: string) => meta.roles.find((r) => r.id === id)?.name ?? `@${id}`;
  const available = meta.roles
    .filter((r) => !roles.includes(r.id))
    .map((r) => ({ value: r.id, label: r.name }));

  return (
    <div className="stack">
      <Card title="🎭 Autoroles" desc="Roles automatically granted to every member when they join.">
        <div className="stack">
          {roles.length === 0 ? (
            <Empty>No autoroles yet — new members get no role automatically.</Empty>
          ) : (
            roles.map((id) => (
              <div key={id} className="list-row">
                <div className="list-row__main">
                  <span>{roleName(id)}</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={action.isPending}
                  onClick={() => action.mutate(() => api.del<AutorolesConfig>(`${path}/${id}`))}
                >
                  Remove
                </Button>
              </div>
            ))
          )}
          <div className="row row--wrap" style={{ alignItems: "flex-end" }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <Select
                label="Role"
                placeholder="Select a role…"
                value={newRole}
                onChange={setNewRole}
                options={available}
              />
            </div>
            <Button
              variant="primary"
              disabled={!newRole || action.isPending}
              onClick={() => {
                if (!newRole) return;
                action.mutate(() => api.post<AutorolesConfig>(path, { role_id: newRole }));
                setNewRole(null);
              }}
            >
              Add role
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
