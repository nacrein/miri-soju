// REFERENCE PANEL, every other module panel follows this shape.
//
// Anatomy:
//  1. useConfigForm(): load config + a local draft of the *scalar* fields, with
//     dirty tracking; Save does the PUT, the SaveBar shows state.
//  2. project(): the editable scalar subset (lists are handled separately).
//  3. useConfigAction(): immediate add/remove for server-managed lists (rewards,
//     multipliers), each call returns the full config and refreshes the panel.
//  4. meta.roles / meta.channels populate the dropdowns with the server's real
//     roles and channels.
import { useState } from "react";

import { api } from "../../api/client";
import {
  Badge,
  Button,
  Card,
  CenteredSpinner,
  Empty,
  NumberField,
  SaveBar,
  Select,
  TextArea,
  ToggleRow,
} from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { LevelingConfig } from "../../lib/types";
import { useConfigAction, useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

interface Draft {
  enabled: boolean;
  xp_per_message: number;
  message_cooldown: number;
  announce_mode: "here" | "dm" | "channel";
  announce_channel_id: string | null;
  level_up_message: string;
}

export default function LevelingPanel({ guildId, meta }: PanelProps) {
  const queryKey = ["leveling", guildId];
  const path = `/guilds/${guildId}/leveling`;

  const form = useConfigForm<LevelingConfig, Draft>({
    queryKey,
    path,
    project: (c) => ({
      enabled: c.enabled,
      xp_per_message: c.xp_per_message,
      message_cooldown: c.message_cooldown,
      announce_mode: c.announce_mode,
      announce_channel_id: c.announce_channel_id,
      level_up_message: c.level_up_message,
    }),
  });
  const action = useConfigAction<LevelingConfig>(queryKey);
  useDirtyGuard(form.dirty);

  const roleOptions = meta.roles.map((r) => ({ value: r.id, label: r.name }));
  const channelOptions = meta.channels.map((c) => ({ value: c.id, label: `#${c.name}` }));
  const roleName = (id: string) => meta.roles.find((r) => r.id === id)?.name ?? `@${id}`;
  const channelName = (id: string) => meta.channels.find((c) => c.id === id)?.name ?? id;

  // add-reward form state
  const [newLevel, setNewLevel] = useState(5);
  const [newRole, setNewRole] = useState<string | null>(null);
  // add-multiplier form state
  const [multChannel, setMultChannel] = useState<string | null>(null);
  const [multValue, setMultValue] = useState(2);

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;
  const { rewards, multipliers } = form.config;

  // schemas.py rejects announce_mode='channel' without a channel; pre-validate so
  // the user sees a field error instead of an opaque 422 after saving.
  const channelRequired = d.announce_mode === "channel" && !d.announce_channel_id;

  return (
    <div className="stack">
      <Card title="📈 Leveling" desc="Award XP for chatting and rank members up over time.">
        <div className="stack">
          <ToggleRow
            label="Enable leveling"
            hint="While on, members earn XP from messages."
            checked={d.enabled}
            onChange={(v) => form.set("enabled", v)}
          />
          <div className="grid-2">
            <NumberField
              label="XP per message"
              hint="1-1000"
              min={1}
              max={1000}
              value={d.xp_per_message}
              onChange={(v) => form.set("xp_per_message", v)}
            />
            <NumberField
              label="Message cooldown (seconds)"
              hint="0-3600. Minimum gap between XP-earning messages"
              min={0}
              max={3600}
              value={d.message_cooldown}
              onChange={(v) => form.set("message_cooldown", v)}
            />
          </div>
          <div className="grid-2">
            <Select
              label="Announce level-ups"
              value={d.announce_mode}
              onChange={(v) => form.set("announce_mode", (v ?? "here") as Draft["announce_mode"])}
              options={[
                { value: "here", label: "In the channel they leveled up" },
                { value: "dm", label: "Direct message" },
                { value: "channel", label: "A specific channel" },
              ]}
            />
            {d.announce_mode === "channel" && (
              <Select
                label="Announcement channel"
                placeholder="Select a channel…"
                error={channelRequired ? "Pick a channel to announce in." : undefined}
                value={d.announce_channel_id}
                onChange={(v) => form.set("announce_channel_id", v)}
                options={channelOptions}
              />
            )}
          </div>
          <TextArea
            label="Level-up message"
            hint="Placeholders: {user} and {level}. Max 500 characters."
            maxLength={500}
            value={d.level_up_message}
            onChange={(v) => form.set("level_up_message", v)}
          />
        </div>
      </Card>

      <Card title="🎁 Role rewards" desc="Grant a role automatically when a member reaches a level.">
        <div className="stack">
          {rewards.length === 0 ? (
            <Empty>No role rewards yet.</Empty>
          ) : (
            rewards.map((r) => (
              <div key={r.level} className="list-row">
                <div className="list-row__main">
                  <Badge tone="primary">Level {r.level}</Badge>
                  <span className="muted">→</span>
                  <span>{roleName(r.role_id)}</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={action.isPending}
                  onClick={() => action.mutate(() => api.del<LevelingConfig>(`${path}/rewards/${r.level}`))}
                >
                  Remove
                </Button>
              </div>
            ))
          )}
          <div className="row row--wrap" style={{ alignItems: "flex-end" }}>
            <div style={{ width: 120 }}>
              <NumberField label="Level" min={1} max={1000} value={newLevel} onChange={setNewLevel} />
            </div>
            <div style={{ flex: 1, minWidth: 180 }}>
              <Select label="Role" placeholder="Select a role…" value={newRole} onChange={setNewRole} options={roleOptions} />
            </div>
            <Button
              variant="primary"
              disabled={!newRole || action.isPending}
              onClick={() =>
                newRole &&
                action.mutate(() => api.post<LevelingConfig>(`${path}/rewards`, { level: newLevel, role_id: newRole }))
              }
            >
              Add reward
            </Button>
          </div>
        </div>
      </Card>

      <Card title="✖️ Channel multipliers" desc="Boost or disable XP in specific channels (0 = no XP).">
        <div className="stack">
          {multipliers.length === 0 ? (
            <Empty>No channel multipliers set. Every channel earns XP at 1×.</Empty>
          ) : (
            multipliers.map((m) => (
              <div key={m.channel_id} className="list-row">
                <div className="list-row__main">
                  <span>#{channelName(m.channel_id)}</span>
                  <Badge>{m.multiplier}×</Badge>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={action.isPending}
                  onClick={() => action.mutate(() => api.del<LevelingConfig>(`${path}/multipliers/${m.channel_id}`))}
                >
                  Remove
                </Button>
              </div>
            ))
          )}
          <div className="row row--wrap" style={{ alignItems: "flex-end" }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <Select label="Channel" placeholder="Select a channel…" value={multChannel} onChange={setMultChannel} options={channelOptions} />
            </div>
            <div style={{ width: 140 }}>
              <NumberField label="Multiplier" min={0} max={10} step={0.5} value={multValue} onChange={setMultValue} />
            </div>
            <Button
              variant="primary"
              disabled={!multChannel || action.isPending}
              onClick={() =>
                multChannel &&
                action.mutate(() =>
                  api.post<LevelingConfig>(`${path}/multipliers`, { channel_id: multChannel, multiplier: multValue }),
                )
              }
            >
              Set
            </Button>
          </div>
        </div>
      </Card>

      <SaveBar
        dirty={form.dirty}
        saving={form.saving}
        onSave={form.save}
        onReset={form.reset}
        error={form.error}
        justSaved={form.justSaved}
        invalid={channelRequired ? "Pick an announcement channel before saving." : undefined}
      />
    </div>
  );
}
