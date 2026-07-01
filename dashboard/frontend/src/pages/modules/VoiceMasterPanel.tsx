import { Card, CenteredSpinner, SaveBar, Select, ToggleRow } from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { VoiceMasterConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

interface Draft {
  enabled: boolean;
  create_channel_id: string | null;
}

export default function VoiceMasterPanel({ guildId, meta }: PanelProps) {
  const form = useConfigForm<VoiceMasterConfig, Draft>({
    queryKey: ["voicemaster", guildId],
    path: `/guilds/${guildId}/voicemaster`,
    project: (c) => ({
      enabled: c.enabled,
      create_channel_id: c.create_channel_id,
    }),
  });
  useDirtyGuard(form.dirty);

  const voiceOptions = meta.voice_channels.map((c) => ({ value: c.id, label: `🔊 ${c.name}` }));

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;

  return (
    <div className="stack">
      <Card
        title="🔊 VoiceMaster"
        desc="A join-to-create voice channel: joining it spins up a temporary channel the member controls."
      >
        <div className="stack">
          <ToggleRow
            label="Enable VoiceMaster"
            checked={d.enabled}
            onChange={(v) => form.set("enabled", v)}
          />
          <Select
            label="Join-to-create channel"
            hint="Members who join this voice channel get their own temporary channel."
            placeholder="Pick a voice channel…"
            value={d.create_channel_id}
            onChange={(v) => form.set("create_channel_id", v)}
            options={voiceOptions}
            disabled={!d.enabled}
          />
          <p className="muted">
            The control panel message is posted with <code>,setup voicemaster</code> in Discord.
          </p>
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
