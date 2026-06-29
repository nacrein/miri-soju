import { Card, CenteredSpinner, SaveBar, Select } from "../../components/ui";
import type { ModerationConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

export default function ModerationPanel({ guildId, meta }: PanelProps) {
  const queryKey = ["moderation", guildId];
  const path = `/guilds/${guildId}/moderation`;

  const form = useConfigForm<ModerationConfig, ModerationConfig>({
    queryKey,
    path,
    project: (c) => ({
      jail_role_id: c.jail_role_id,
    }),
  });

  const roleOptions = meta.roles.map((r) => ({ value: r.id, label: r.name }));

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;

  return (
    <div className="stack">
      <Card
        title="🔨 Moderation"
        desc="The jail role is applied to jailed members, replacing their existing roles until they're released."
      >
        <div className="stack">
          <Select
            label="Jail role"
            placeholder="No jail role set — pick one…"
            value={d.jail_role_id}
            onChange={(v) => form.set("jail_role_id", v)}
            options={roleOptions}
          />
        </div>
      </Card>

      <SaveBar
        dirty={form.dirty}
        saving={form.saving}
        onSave={form.save}
        onReset={form.reset}
        error={form.error}
        justSaved={form.justSaved}
      />
    </div>
  );
}
