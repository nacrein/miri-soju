import { Card, CenteredSpinner, SaveBar, Select, ToggleRow } from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { BoosterRoleConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

interface Draft {
  enabled: boolean;
  hoist_above: boolean;
  anchor_role_id: string | null;
}

export default function BoosterRolePanel({ guildId, meta }: PanelProps) {
  const form = useConfigForm<BoosterRoleConfig, Draft>({
    queryKey: ["boosterrole", guildId],
    path: `/guilds/${guildId}/boosterrole`,
    project: (c) => ({
      enabled: c.enabled,
      hoist_above: c.hoist_above,
      anchor_role_id: c.anchor_role_id,
    }),
  });
  useDirtyGuard(form.dirty);

  const roleOptions = meta.roles.map((r) => ({ value: r.id, label: r.name }));

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;
  const off = !d.enabled;

  return (
    <div className="stack">
      <Card title="🎨 Booster Roles" desc="Let server boosters create their own custom role.">
        <div className="stack">
          <ToggleRow
            label="Enable booster roles"
            checked={d.enabled}
            onChange={(v) => form.set("enabled", v)}
          />
          <Select
            label="Anchor role"
            hint="Booster roles are positioned relative to this role. Leave empty for no anchor."
            placeholder="No anchor…"
            value={d.anchor_role_id}
            onChange={(v) => form.set("anchor_role_id", v)}
            options={roleOptions}
            disabled={off}
          />
          <ToggleRow
            label="Place booster roles above the anchor"
            hint="On: just above the anchor role. Off: just below it."
            checked={d.hoist_above}
            disabled={off}
            onChange={(v) => form.set("hoist_above", v)}
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
