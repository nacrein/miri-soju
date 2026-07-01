import { Card, CenteredSpinner, NumberField, SaveBar, Select } from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { MusicConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

interface Draft {
  dj_role_id: string | null;
  command_channel_id: string | null;
  default_volume: number;
}

export default function MusicPanel({ guildId, meta }: PanelProps) {
  const form = useConfigForm<MusicConfig, Draft>({
    queryKey: ["music", guildId],
    path: `/guilds/${guildId}/music`,
    project: (c) => ({
      dj_role_id: c.dj_role_id,
      command_channel_id: c.command_channel_id,
      default_volume: c.default_volume,
    }),
  });
  useDirtyGuard(form.dirty);

  const roleOptions = meta.roles.map((r) => ({ value: r.id, label: r.name }));
  const channelOptions = meta.channels.map((c) => ({ value: c.id, label: `#${c.name}` }));

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;

  return (
    <div className="stack">
      <Card title="🎵 Music" desc="DJ role, command channel, and the default volume.">
        <div className="stack">
          <Select
            label="DJ role"
            hint="Members with this role can run privileged music commands. Leave empty to allow everyone."
            placeholder="Anyone can DJ…"
            value={d.dj_role_id}
            onChange={(v) => form.set("dj_role_id", v)}
            options={roleOptions}
          />
          <Select
            label="Command channel"
            hint="Restrict music commands to one channel. Leave empty to allow anywhere."
            placeholder="Any channel…"
            value={d.command_channel_id}
            onChange={(v) => form.set("command_channel_id", v)}
            options={channelOptions}
          />
          <NumberField
            label="Default volume"
            hint="0-150. The volume new players start at"
            min={0}
            max={150}
            value={d.default_volume}
            onChange={(v) => form.set("default_volume", v)}
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
