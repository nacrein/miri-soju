import { Card, CenteredSpinner, SaveBar, Select, ToggleRow } from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { ServerlogConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

// Editable subset of ServerlogConfig sent in the PUT body. Declared explicitly
// (rather than reusing the Out type) so a future read-only/server-managed field
// on ServerlogConfig isn't silently included in the body or dirty-tracking.
interface Draft {
  log_channel_id: string | null;
  log_joins: boolean;
  log_leaves: boolean;
  log_message_delete: boolean;
  log_message_edit: boolean;
  log_mod_actions: boolean;
}

export default function ServerlogPanel({ guildId, meta }: PanelProps) {
  const form = useConfigForm<ServerlogConfig, Draft>({
    queryKey: ["serverlog", guildId],
    path: `/guilds/${guildId}/serverlog`,
    project: (c) => ({
      log_channel_id: c.log_channel_id,
      log_joins: c.log_joins,
      log_leaves: c.log_leaves,
      log_message_delete: c.log_message_delete,
      log_message_edit: c.log_message_edit,
      log_mod_actions: c.log_mod_actions,
    }),
  });
  useDirtyGuard(form.dirty);

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
            placeholder="Logging is off, pick a channel…"
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
