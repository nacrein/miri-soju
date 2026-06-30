// AutoMod panel — the richest module. Scalar settings live in a single draft
// edited via useConfigForm + saved through the SaveBar; the four server-managed
// lists (banned words, allowed domains, exempt roles, exempt channels) mutate
// immediately through useConfigAction, mirroring LevelingPanel's rewards list.
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
  TextField,
  ToggleRow,
} from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { AutomodConfig } from "../../lib/types";
import { useConfigAction, useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

// All scalar fields — everything except the four server-managed list arrays.
interface Draft {
  enabled: boolean;
  log_only: boolean;
  dm_on_action: boolean;
  exempt_mods: boolean;
  strike_window_hours: number;
  filter_invites: boolean;
  filter_links: boolean;
  filter_spam: boolean;
  spam_count: number;
  spam_interval: number;
  duplicate_threshold: number;
  filter_mentions: boolean;
  mention_limit: number;
  block_everyone: boolean;
  filter_words: boolean;
  filter_caps: boolean;
  caps_percent: number;
  caps_min_len: number;
  filter_emoji: boolean;
  emoji_limit: number;
  timeout_at: number;
  timeout_minutes: number;
  timeout2_at: number;
  timeout2_minutes: number;
  kick_at: number;
  ban_at: number;
}

export default function AutomodPanel({ guildId, meta }: PanelProps) {
  const queryKey = ["automod", guildId];
  const path = `/guilds/${guildId}/automod`;

  const form = useConfigForm<AutomodConfig, Draft>({
    queryKey,
    path,
    // Strip the four list arrays — they're edited through their own endpoints.
    project: (c) => ({
      enabled: c.enabled,
      log_only: c.log_only,
      dm_on_action: c.dm_on_action,
      exempt_mods: c.exempt_mods,
      strike_window_hours: c.strike_window_hours,
      filter_invites: c.filter_invites,
      filter_links: c.filter_links,
      filter_spam: c.filter_spam,
      spam_count: c.spam_count,
      spam_interval: c.spam_interval,
      duplicate_threshold: c.duplicate_threshold,
      filter_mentions: c.filter_mentions,
      mention_limit: c.mention_limit,
      block_everyone: c.block_everyone,
      filter_words: c.filter_words,
      filter_caps: c.filter_caps,
      caps_percent: c.caps_percent,
      caps_min_len: c.caps_min_len,
      filter_emoji: c.filter_emoji,
      emoji_limit: c.emoji_limit,
      timeout_at: c.timeout_at,
      timeout_minutes: c.timeout_minutes,
      timeout2_at: c.timeout2_at,
      timeout2_minutes: c.timeout2_minutes,
      kick_at: c.kick_at,
      ban_at: c.ban_at,
    }),
  });
  const action = useConfigAction<AutomodConfig>(queryKey);
  useDirtyGuard(form.dirty);

  const roleOptions = meta.roles.map((r) => ({ value: r.id, label: r.name }));
  const channelOptions = meta.channels.map((c) => ({ value: c.id, label: `#${c.name}` }));
  const roleName = (id: string) => meta.roles.find((r) => r.id === id)?.name ?? id;
  const channelName = (id: string) => meta.channels.find((c) => c.id === id)?.name ?? id;

  // add-word / add-domain form state
  const [newWord, setNewWord] = useState("");
  const [newDomain, setNewDomain] = useState("");
  // add-exempt-role / add-exempt-channel form state
  const [exemptRole, setExemptRole] = useState<string | null>(null);
  const [exemptChannel, setExemptChannel] = useState<string | null>(null);

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;
  const { words, domains, exempt_roles, exempt_channels } = form.config;

  return (
    <div className="stack">
      <Card title="🛡️ Master" desc="Turn AutoMod on and set the global behavior.">
        <div className="stack">
          <ToggleRow
            label="Enable AutoMod"
            hint="While on, the enabled filters below scan every message."
            checked={d.enabled}
            onChange={(v) => form.set("enabled", v)}
          />
          <ToggleRow
            label="Dry-run (log only, take no action)"
            checked={d.log_only}
            onChange={(v) => form.set("log_only", v)}
          />
          <ToggleRow
            label="DM the user on action"
            checked={d.dm_on_action}
            onChange={(v) => form.set("dm_on_action", v)}
          />
          <ToggleRow
            label="Never action moderators"
            checked={d.exempt_mods}
            onChange={(v) => form.set("exempt_mods", v)}
          />
          <NumberField
            label="Strike decay window (hours)"
            hint="1–168 — how long a strike counts toward escalation."
            min={1}
            max={168}
            value={d.strike_window_hours}
            onChange={(v) => form.set("strike_window_hours", v)}
          />
        </div>
      </Card>

      <Card title="Filters" desc="Each filter strikes a member when it trips.">
        <div className="stack">
          <ToggleRow
            label="Block invites"
            checked={d.filter_invites}
            onChange={(v) => form.set("filter_invites", v)}
          />

          <ToggleRow
            label="Block links"
            checked={d.filter_links}
            onChange={(v) => form.set("filter_links", v)}
          />

          <ToggleRow label="Block spam" checked={d.filter_spam} onChange={(v) => form.set("filter_spam", v)} />
          {d.filter_spam && (
            <div className="grid-2">
              <NumberField
                label="Messages"
                hint="2–30"
                min={2}
                max={30}
                value={d.spam_count}
                onChange={(v) => form.set("spam_count", v)}
              />
              <NumberField
                label="Within (seconds)"
                hint="1–60"
                min={1}
                max={60}
                value={d.spam_interval}
                onChange={(v) => form.set("spam_interval", v)}
              />
              <NumberField
                label="Duplicate threshold"
                hint="2–20"
                min={2}
                max={20}
                value={d.duplicate_threshold}
                onChange={(v) => form.set("duplicate_threshold", v)}
              />
            </div>
          )}

          <ToggleRow
            label="Limit mass mentions"
            checked={d.filter_mentions}
            onChange={(v) => form.set("filter_mentions", v)}
          />
          {d.filter_mentions && (
            <div className="stack">
              <NumberField
                label="Mention limit"
                hint="1–50"
                min={1}
                max={50}
                value={d.mention_limit}
                onChange={(v) => form.set("mention_limit", v)}
              />
              <ToggleRow
                label="Block @everyone / @here"
                checked={d.block_everyone}
                onChange={(v) => form.set("block_everyone", v)}
              />
            </div>
          )}

          <ToggleRow
            label="Banned-word filter"
            hint="Manage the word list below."
            checked={d.filter_words}
            onChange={(v) => form.set("filter_words", v)}
          />

          <ToggleRow label="Limit caps" checked={d.filter_caps} onChange={(v) => form.set("filter_caps", v)} />
          {d.filter_caps && (
            <div className="grid-2">
              <NumberField
                label="Caps percent"
                hint="50–100"
                min={50}
                max={100}
                value={d.caps_percent}
                onChange={(v) => form.set("caps_percent", v)}
              />
              <NumberField
                label="Minimum length"
                hint="1–200 — ignore shorter messages."
                min={1}
                max={200}
                value={d.caps_min_len}
                onChange={(v) => form.set("caps_min_len", v)}
              />
            </div>
          )}

          <ToggleRow label="Limit emoji" checked={d.filter_emoji} onChange={(v) => form.set("filter_emoji", v)} />
          {d.filter_emoji && (
            <NumberField
              label="Emoji limit"
              hint="1–50"
              min={1}
              max={50}
              value={d.emoji_limit}
              onChange={(v) => form.set("emoji_limit", v)}
            />
          )}
        </div>
      </Card>

      <Card title="Escalation" desc="0 disables a tier.">
        <div className="grid-2">
          <NumberField
            label="Timeout at strike"
            min={0}
            max={100}
            value={d.timeout_at}
            onChange={(v) => form.set("timeout_at", v)}
          />
          <NumberField
            label="Timeout duration (minutes)"
            min={1}
            max={40320}
            value={d.timeout_minutes}
            onChange={(v) => form.set("timeout_minutes", v)}
          />
          <NumberField
            label="Second timeout at strike"
            min={0}
            max={100}
            value={d.timeout2_at}
            onChange={(v) => form.set("timeout2_at", v)}
          />
          <NumberField
            label="Second timeout duration (minutes)"
            min={1}
            max={40320}
            value={d.timeout2_minutes}
            onChange={(v) => form.set("timeout2_minutes", v)}
          />
          <NumberField
            label="Kick at strike"
            min={0}
            max={100}
            value={d.kick_at}
            onChange={(v) => form.set("kick_at", v)}
          />
          <NumberField
            label="Ban at strike"
            min={0}
            max={100}
            value={d.ban_at}
            onChange={(v) => form.set("ban_at", v)}
          />
        </div>
      </Card>

      <Card title="Banned words" desc="Messages containing any of these are filtered.">
        <div className="stack">
          {words.length === 0 ? (
            <Empty>No banned words yet.</Empty>
          ) : (
            <div className="row row--wrap">
              {words.map((w) => (
                <Badge key={w}>
                  <span>{w}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={action.isPending}
                    onClick={() => action.mutate(() => api.del<AutomodConfig>(`${path}/words/${encodeURIComponent(w)}`))}
                  >
                    Remove
                  </Button>
                </Badge>
              ))}
            </div>
          )}
          <div className="row row--wrap" style={{ alignItems: "flex-end" }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <TextField label="Word" placeholder="Add a word…" value={newWord} onChange={setNewWord} />
            </div>
            <Button
              variant="primary"
              disabled={!newWord.trim() || action.isPending}
              onClick={() => {
                const value = newWord.trim();
                if (!value) return;
                action.mutate(() => api.post<AutomodConfig>(`${path}/words`, { value }));
                setNewWord("");
              }}
            >
              Add word
            </Button>
          </div>
        </div>
      </Card>

      <Card title="Allowed link domains" desc="When blocking links, these domains are still permitted.">
        <div className="stack">
          {domains.length === 0 ? (
            <Empty>No allowed domains yet.</Empty>
          ) : (
            <div className="row row--wrap">
              {domains.map((dom) => (
                <Badge key={dom}>
                  <span>{dom}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={action.isPending}
                    onClick={() =>
                      action.mutate(() => api.del<AutomodConfig>(`${path}/domains/${encodeURIComponent(dom)}`))
                    }
                  >
                    Remove
                  </Button>
                </Badge>
              ))}
            </div>
          )}
          <div className="row row--wrap" style={{ alignItems: "flex-end" }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <TextField label="Domain" placeholder="example.com" value={newDomain} onChange={setNewDomain} />
            </div>
            <Button
              variant="primary"
              disabled={!newDomain.trim() || action.isPending}
              onClick={() => {
                const value = newDomain.trim();
                if (!value) return;
                action.mutate(() => api.post<AutomodConfig>(`${path}/domains`, { value }));
                setNewDomain("");
              }}
            >
              Add domain
            </Button>
          </div>
        </div>
      </Card>

      <Card title="Exempt roles" desc="Members with any of these roles are never actioned.">
        <div className="stack">
          {exempt_roles.length === 0 ? (
            <Empty>No exempt roles.</Empty>
          ) : (
            exempt_roles.map((id) => (
              <div key={id} className="list-row">
                <div className="list-row__main">
                  <span>{roleName(id)}</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={action.isPending}
                  onClick={() => action.mutate(() => api.del<AutomodConfig>(`${path}/exempt-roles/${id}`))}
                >
                  Remove
                </Button>
              </div>
            ))
          )}
          <div className="row row--wrap" style={{ alignItems: "flex-end" }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <Select
                label="Role"
                placeholder="Select a role…"
                value={exemptRole}
                onChange={setExemptRole}
                options={roleOptions}
              />
            </div>
            <Button
              variant="primary"
              disabled={!exemptRole || action.isPending}
              onClick={() =>
                exemptRole &&
                action.mutate(() => api.post<AutomodConfig>(`${path}/exempt-roles`, { id: exemptRole }))
              }
            >
              Add role
            </Button>
          </div>
        </div>
      </Card>

      <Card title="Exempt channels" desc="Messages in these channels are never actioned.">
        <div className="stack">
          {exempt_channels.length === 0 ? (
            <Empty>No exempt channels.</Empty>
          ) : (
            exempt_channels.map((id) => (
              <div key={id} className="list-row">
                <div className="list-row__main">
                  <span>#{channelName(id)}</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={action.isPending}
                  onClick={() => action.mutate(() => api.del<AutomodConfig>(`${path}/exempt-channels/${id}`))}
                >
                  Remove
                </Button>
              </div>
            ))
          )}
          <div className="row row--wrap" style={{ alignItems: "flex-end" }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <Select
                label="Channel"
                placeholder="Select a channel…"
                value={exemptChannel}
                onChange={setExemptChannel}
                options={channelOptions}
              />
            </div>
            <Button
              variant="primary"
              disabled={!exemptChannel || action.isPending}
              onClick={() =>
                exemptChannel &&
                action.mutate(() => api.post<AutomodConfig>(`${path}/exempt-channels`, { id: exemptChannel }))
              }
            >
              Add channel
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
      />
    </div>
  );
}
