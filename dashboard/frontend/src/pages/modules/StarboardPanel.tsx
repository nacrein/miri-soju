import {
  Card,
  CenteredSpinner,
  NumberField,
  SaveBar,
  Select,
  TextField,
  ToggleRow,
} from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { StarboardConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

interface Draft {
  channel_id: string | null;
  threshold: number;
  star_emoji: string;
  enabled: boolean;
  self_star: boolean;
}

export default function StarboardPanel({ guildId, meta }: PanelProps) {
  const form = useConfigForm<StarboardConfig, Draft>({
    queryKey: ["starboard", guildId],
    path: `/guilds/${guildId}/starboard`,
    project: (c) => ({
      channel_id: c.channel_id,
      threshold: c.threshold,
      star_emoji: c.star_emoji,
      enabled: c.enabled,
      self_star: c.self_star,
    }),
  });
  useDirtyGuard(form.dirty);

  const channelOptions = meta.channels.map((c) => ({ value: c.id, label: `#${c.name}` }));

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;
  const off = !d.enabled;

  return (
    <div className="stack">
      <Card title="⭐ Starboard" desc="Mirror well-starred messages to a board channel.">
        <div className="stack">
          <ToggleRow
            label="Enable starboard"
            checked={d.enabled}
            onChange={(v) => form.set("enabled", v)}
          />
          <Select
            label="Board channel"
            placeholder="Pick a channel…"
            value={d.channel_id}
            onChange={(v) => form.set("channel_id", v)}
            options={channelOptions}
            disabled={off}
          />
          <div className="grid-2">
            <NumberField
              label="Star threshold"
              hint="1–50 — stars needed to reach the board"
              min={1}
              max={50}
              value={d.threshold}
              onChange={(v) => form.set("threshold", v)}
              disabled={off}
            />
            <TextField
              label="Star emoji"
              hint="The reaction to count (default ⭐)"
              maxLength={64}
              value={d.star_emoji}
              onChange={(v) => form.set("star_emoji", v)}
              disabled={off}
            />
          </div>
          <ToggleRow
            label="Count authors' own stars"
            hint="If off, a member starring their own message doesn't count toward the threshold."
            checked={d.self_star}
            disabled={off}
            onChange={(v) => form.set("self_star", v)}
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
