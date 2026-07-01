import { Card, CenteredSpinner, SaveBar, Select } from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { ModerationConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

// Editable subset of ModerationConfig sent in the PUT body. Declared explicitly
// (rather than reusing the Out type) so a future read-only/server-managed field
// on ModerationConfig isn't silently included in the body or dirty-tracking.
interface Draft {
  jail_role_id: string | null;
}

export default function ModerationPanel({ guildId, meta }: PanelProps) {
  const queryKey = ["moderation", guildId];
  const path = `/guilds/${guildId}/moderation`;

  const form = useConfigForm<ModerationConfig, Draft>({
    queryKey,
    path,
    project: (c) => ({
      jail_role_id: c.jail_role_id,
    }),
  });
  useDirtyGuard(form.dirty);

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
            placeholder="No jail role set, pick one…"
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
