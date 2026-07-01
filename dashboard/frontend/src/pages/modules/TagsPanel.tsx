import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";
import {
  Badge,
  Button,
  Card,
  CenteredSpinner,
  Empty,
  TextArea,
  TextField,
} from "../../components/ui";
import type { TagsConfig } from "../../lib/types";
import { useConfigAction } from "../../lib/useConfigForm";
import type { PanelProps } from "./types";

export default function TagsPanel({ guildId }: PanelProps) {
  const queryKey = ["tags", guildId];
  const path = `/guilds/${guildId}/tags`;
  const query = useQuery<TagsConfig>({
    queryKey,
    queryFn: () => api.get<TagsConfig>(path),
    staleTime: 30_000,
  });
  const action = useConfigAction<TagsConfig>(queryKey);

  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [editContent, setEditContent] = useState("");

  if (query.isLoading || !query.data) return <CenteredSpinner />;
  const tags = query.data.tags;
  const nameTaken = tags.some((t) => t.name === name.trim().toLowerCase());
  const canCreate =
    name.trim().length > 0 && content.trim().length > 0 && !nameTaken && !action.isPending;

  function create() {
    if (!canCreate) return;
    action.mutate(() => api.post<TagsConfig>(path, { name: name.trim(), content }));
    setName("");
    setContent("");
  }

  function saveEdit(tagName: string) {
    action.mutate(() =>
      api.put<TagsConfig>(`${path}/${encodeURIComponent(tagName)}`, { content: editContent }),
    );
    setEditing(null);
  }

  return (
    <div className="stack">
      <Card title="🏷️ Tags" desc="Custom commands — members run ,tag <name> to post the saved text.">
        <div className="stack">
          {tags.length === 0 ? (
            <Empty>No tags yet.</Empty>
          ) : (
            tags.map((t) => (
              <div key={t.name} className="stack" style={{ gap: 6 }}>
                <div className="list-row">
                  <div className="list-row__main">
                    <Badge tone="primary">{t.name}</Badge>
                    <span className="muted">
                      {t.uses} use{t.uses === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="row">
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={action.isPending}
                      onClick={() => {
                        setEditing(t.name);
                        setEditContent(t.content);
                      }}
                    >
                      Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={action.isPending}
                      onClick={() =>
                        action.mutate(() =>
                          api.del<TagsConfig>(`${path}/${encodeURIComponent(t.name)}`),
                        )
                      }
                    >
                      Delete
                    </Button>
                  </div>
                </div>
                {editing === t.name ? (
                  <div className="row row--wrap" style={{ alignItems: "flex-end" }}>
                    <div style={{ flex: 1, minWidth: 220 }}>
                      <TextArea
                        label="Content"
                        maxLength={2000}
                        value={editContent}
                        onChange={setEditContent}
                      />
                    </div>
                    <Button
                      variant="primary"
                      disabled={action.isPending || editContent.trim().length === 0}
                      onClick={() => saveEdit(t.name)}
                    >
                      Save
                    </Button>
                    <Button variant="ghost" onClick={() => setEditing(null)}>
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <div className="muted" style={{ whiteSpace: "pre-wrap" }}>
                    {t.content}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </Card>

      <Card title="➕ New tag" desc="Create a custom command.">
        <div className="stack">
          <TextField
            label="Name"
            hint="Lowercased; used as ,tag <name>. Max 100 characters."
            maxLength={100}
            value={name}
            onChange={setName}
            error={nameTaken ? "A tag with that name already exists." : undefined}
          />
          <TextArea
            label="Content"
            hint="What the bot replies with. Max 2000 characters."
            maxLength={2000}
            value={content}
            onChange={setContent}
          />
          <div className="row">
            <Button variant="primary" disabled={!canCreate} onClick={create}>
              Create tag
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
