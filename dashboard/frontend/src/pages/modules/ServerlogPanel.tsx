import { Card, CenteredSpinner, SaveBar, Select, ToggleRow } from "../../components/ui";
import type { ServerlogConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

export default function ServerlogPanel({ guildId, meta }: PanelProps) {
  const form = useConfigForm<ServerlogConfig, ServerlogConfig>({
    queryKey: ["serverlog", guildId],
    path: `/guilds/${guildId}/serverlog`,
    project: (c) => ({ ...c }),
  });

  const channelOptions = meta.channels.map((c) => ({ value: c.id, label: `#${c.name}` }));

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;
  const off = !d.log_channel_id;

  return (
    <div className="stack">
      <Card title="📜 Server Log" desc="Send a record of server activity to a channel.">
        <div className="stack">
          <Select
            label="Log channel"
            placeholder="Logging is off — pick a channel…"
            value={d.log_channel_id}
            onChange={(v) => form.set("log_channel_id", v)}
            options={channelOptions}
          />
          <ToggleRow
            label="Member joins"
            checked={d.log_joins}
            disabled={off}
            onChange={(v) => form.set("log_joins", v)}
          />
          <ToggleRow
            label="Member leaves"
            checked={d.log_leaves}
            disabled={off}
            onChange={(v) => form.set("log_leaves", v)}
          />
          <ToggleRow
            label="Deleted messages"
            checked={d.log_message_delete}
            disabled={off}
            onChange={(v) => form.set("log_message_delete", v)}
          />
          <ToggleRow
            label="Edited messages"
            checked={d.log_message_edit}
            disabled={off}
            onChange={(v) => form.set("log_message_edit", v)}
          />
          <ToggleRow
            label="Moderation actions"
            checked={d.log_mod_actions}
            disabled={off}
            onChange={(v) => form.set("log_mod_actions", v)}
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
