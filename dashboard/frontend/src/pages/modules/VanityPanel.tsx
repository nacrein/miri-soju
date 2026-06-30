import { Card, CenteredSpinner, SaveBar, Select, TextArea, ToggleRow } from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { VanityConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

interface Draft {
  enabled: boolean;
  role_id: string | null;
  channel_id: string | null;
  message_template: string;
}

export default function VanityPanel({ guildId, meta }: PanelProps) {
  const form = useConfigForm<VanityConfig, Draft>({
    queryKey: ["vanity", guildId],
    path: `/guilds/${guildId}/vanity`,
    project: (c) => ({
      enabled: c.enabled,
      role_id: c.role_id,
      channel_id: c.channel_id,
      message_template: c.message_template ?? "",
    }),
  });
  useDirtyGuard(form.dirty);

  const roleOptions = meta.roles.map((r) => ({ value: r.id, label: r.name }));
  const channelOptions = meta.channels.map((c) => ({ value: c.id, label: `#${c.name}` }));

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;
  const off = !d.enabled;

  return (
    <div className="stack">
      <Card title="✨ Vanity" desc="Reward members who put the server's vanity link in their status.">
        <div className="stack">
          <ToggleRow
            label="Enable vanity rewards"
            checked={d.enabled}
            onChange={(v) => form.set("enabled", v)}
          />
          <Select
            label="Reward role"
            placeholder="Pick a role…"
            value={d.role_id}
            onChange={(v) => form.set("role_id", v)}
            options={roleOptions}
            disabled={off}
          />
          <Select
            label="Announcement channel"
            placeholder="Pick a channel…"
            value={d.channel_id}
            onChange={(v) => form.set("channel_id", v)}
            options={channelOptions}
            disabled={off}
          />
          <TextArea
            label="Thank-you message"
            hint="Placeholders: {user} and {vanity}. Max 500 characters."
            maxLength={500}
            value={d.message_template}
            onChange={(v) => form.set("message_template", v)}
            disabled={off}
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
