import {
  Badge,
  Card,
  CenteredSpinner,
  SaveBar,
  TextField,
} from "../../components/ui";
import { useDirtyGuard } from "../../lib/dirtyGuard";
import type { PrefixConfig } from "../../lib/types";
import { useConfigForm } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

interface Draft {
  prefix: string | null;
}

export default function PrefixPanel({ guildId }: PanelProps) {
  const queryKey = ["prefix", guildId];
  const path = `/guilds/${guildId}/prefix`;

  const form = useConfigForm<PrefixConfig, Draft>({
    queryKey,
    path,
    project: (c) => ({ prefix: c.prefix }),
  });
  useDirtyGuard(form.dirty);

  if (form.isLoading || !form.draft || !form.config) return <CenteredSpinner />;
  const d = form.draft;
  const effective = d.prefix ?? form.config.default;

  return (
    <div className="stack">
      <Card title="⌨️ Command Prefix" desc="Set the character(s) that trigger the bot's text commands.">
        <div className="stack">
          <TextField
            label="Prefix"
            mono
            maxLength={8}
            hint={`Leave blank to use the default (${form.config.default}). Max 8 characters.`}
            value={d.prefix ?? ""}
            onChange={(v) => form.set("prefix", v === "" ? null : v)}
          />
          <div className="row" style={{ alignItems: "center", gap: 8 }}>
            <span className="muted">Effective prefix</span>
            <Badge tone="primary">{effective}</Badge>
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
