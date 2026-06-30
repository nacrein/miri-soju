import { Card, CenteredSpinner, SaveBar, Select, TextArea, ToggleRow } from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { WelcomeConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

interface Draft {
  welcome_channel_id: string | null;
  welcome_message: string;
  welcome_enabled: boolean;
  goodbye_channel_id: string | null;
  goodbye_message: string;
  goodbye_enabled: boolean;
}

const HINT = "Placeholders: {user} {name} {server} {count}. Max 2000 characters.";

export default function WelcomePanel({ guildId, meta }: PanelProps) {
  const form = useConfigForm<WelcomeConfig, Draft>({
    queryKey: ["welcome", guildId],
    path: `/guilds/${guildId}/welcome`,
    project: (c) => ({
      welcome_channel_id: c.welcome_channel_id,
      welcome_message: c.welcome_message ?? "",
      welcome_enabled: c.welcome_enabled,
      goodbye_channel_id: c.goodbye_channel_id,
      goodbye_message: c.goodbye_message ?? "",
      goodbye_enabled: c.goodbye_enabled,
    }),
  });
  useDirtyGuard(form.dirty);

  const channelOptions = meta.channels.map((c) => ({ value: c.id, label: `#${c.name}` }));

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;

  return (
    <div className="stack">
      <Card title="👋 Welcome" desc="Greet members in a channel when they join.">
        <div className="stack">
          <ToggleRow
            label="Enable welcome messages"
            checked={d.welcome_enabled}
            onChange={(v) => form.set("welcome_enabled", v)}
          />
          <Select
            label="Welcome channel"
            placeholder="Pick a channel…"
            value={d.welcome_channel_id}
            onChange={(v) => form.set("welcome_channel_id", v)}
            options={channelOptions}
            disabled={!d.welcome_enabled}
          />
          <TextArea
            label="Welcome message"
            hint={HINT}
            maxLength={2000}
            value={d.welcome_message}
            onChange={(v) => form.set("welcome_message", v)}
            disabled={!d.welcome_enabled}
          />
        </div>
      </Card>

      <Card title="🚪 Goodbye" desc="Say farewell when a member leaves.">
        <div className="stack">
          <ToggleRow
            label="Enable goodbye messages"
            checked={d.goodbye_enabled}
            onChange={(v) => form.set("goodbye_enabled", v)}
          />
          <Select
            label="Goodbye channel"
            placeholder="Pick a channel…"
            value={d.goodbye_channel_id}
            onChange={(v) => form.set("goodbye_channel_id", v)}
            options={channelOptions}
            disabled={!d.goodbye_enabled}
          />
          <TextArea
            label="Goodbye message"
            hint={HINT}
            maxLength={2000}
            value={d.goodbye_message}
            onChange={(v) => form.set("goodbye_message", v)}
            disabled={!d.goodbye_enabled}
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
