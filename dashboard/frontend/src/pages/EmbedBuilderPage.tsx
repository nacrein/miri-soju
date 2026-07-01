import type { CSSProperties } from "react";
import { useState } from "react";

import { Alert, Button, Field, TextField } from "../components/ui";
import { CAPS, parseColor, toJson, validate } from "../lib/embed";
import type { EmbedField, EmbedScript } from "../lib/types";

const STARTER: EmbedScript = {
  title: "Welcome to the server 🌸",
  description: "Grab your roles, read the rules, and say hi.\nType `,help` to see everything I can do.",
  color: "#c56b5c",
  author: "Miri",
  footer: "Miri · today",
  fields: [],
};

export default function EmbedBuilderPage() {
  const [s, setS] = useState<EmbedScript>(STARTER);
  const [copied, setCopied] = useState(false);

  const set = <K extends keyof EmbedScript>(key: K, value: EmbedScript[K]) =>
    setS((prev) => ({ ...prev, [key]: value }));

  const fields = s.fields ?? [];
  const setFields = (next: EmbedField[]) => set("fields", next);
  const setField = (i: number, patch: Partial<EmbedField>) =>
    setFields(fields.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));

  const error = validate(s);
  const json = toJson(s);
  const color = parseColor(s.color ?? "") ?? "#4f545c";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(json);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked; the JSON is still visible to select manually */
    }
  };

  return (
    <div className="container container--wide">
      <div className="page-header">
        <div className="page-header__title">Embed Builder</div>
        <div className="page-header__desc">
          Design an embed with a live preview, then copy the script into{" "}
          <span className="mono">,ce &lt;json&gt;</span> in your server. Same limits and color rules
          as the bot.
        </div>
      </div>

      <div className="embed-builder">
        {/* ── form ──────────────────────────────────────────────────────── */}
        <div className="embed-form card">
          <div className="card__body stack">
            <TextField
              label="Title"
              value={s.title ?? ""}
              onChange={(v) => set("title", v)}
              maxLength={CAPS.title}
              placeholder="Embed title"
            />
            <Field label="Description" hint={`${(s.description ?? "").length} / ${CAPS.description}`}>
              <textarea
                className="textarea"
                value={s.description ?? ""}
                maxLength={CAPS.description}
                placeholder="Body text. Newlines and **markdown** work."
                onChange={(e) => set("description", e.target.value)}
                style={{ minHeight: 120 }}
              />
            </Field>

            <div className="grid-2">
              <Field
                label="Color"
                error={s.color && !parseColor(s.color) ? "Not a valid color." : undefined}
              >
                <div className="color-field">
                  <span className="color-swatch" style={{ background: color }} />
                  <input
                    className="input mono"
                    value={s.color ?? ""}
                    placeholder="#5865f2"
                    onChange={(e) => set("color", e.target.value)}
                  />
                  <input
                    type="color"
                    className="color-picker"
                    value={parseColor(s.color ?? "") ?? "#c56b5c"}
                    onChange={(e) => set("color", e.target.value)}
                    aria-label="Pick color"
                  />
                </div>
              </Field>
              <TextField
                label="Author"
                value={s.author ?? ""}
                onChange={(v) => set("author", v)}
                maxLength={CAPS.author}
                placeholder="Small text above the title"
              />
            </div>

            <TextField
              label="URL"
              value={s.url ?? ""}
              onChange={(v) => set("url", v)}
              mono
              placeholder="https://… (makes the title a link)"
            />
            <div className="grid-2">
              <TextField
                label="Image URL"
                value={s.image ?? ""}
                onChange={(v) => set("image", v)}
                mono
                placeholder="https://…/image.png"
              />
              <TextField
                label="Thumbnail URL"
                value={s.thumbnail ?? ""}
                onChange={(v) => set("thumbnail", v)}
                mono
                placeholder="https://…/thumb.png"
              />
            </div>
            <TextField
              label="Footer"
              value={s.footer ?? ""}
              onChange={(v) => set("footer", v)}
              maxLength={CAPS.footer}
              placeholder="Small text at the bottom"
            />

            {/* fields */}
            <div className="field">
              <div className="row row--between">
                <label className="field__label">Fields</label>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={fields.length >= CAPS.fields}
                  onClick={() => setFields([...fields, { name: "", value: "", inline: false }])}
                >
                  + Add field ({fields.length}/{CAPS.fields})
                </Button>
              </div>
              <div className="stack stack--sm">
                {fields.map((f, i) => (
                  <div key={i} className="embed-field-row">
                    <div className="embed-field-row__inputs">
                      <input
                        className="input"
                        placeholder="Field name"
                        value={f.name}
                        maxLength={CAPS.fieldName}
                        onChange={(e) => setField(i, { name: e.target.value })}
                      />
                      <input
                        className="input"
                        placeholder="Field value"
                        value={f.value}
                        maxLength={CAPS.fieldValue}
                        onChange={(e) => setField(i, { value: e.target.value })}
                      />
                    </div>
                    <button
                      type="button"
                      className={"chip embed-field-row__inline" + (f.inline ? " embed-field-row__inline--on" : "")}
                      onClick={() => setField(i, { inline: !f.inline })}
                      title="Toggle inline"
                    >
                      inline
                    </button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => setFields(fields.filter((_, idx) => idx !== i))}
                    >
                      ✕
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ── preview + output ──────────────────────────────────────────── */}
        <div className="embed-side">
          <div className="embed-side__label muted">Live preview</div>
          <EmbedPreview script={s} color={color} />

          {error ? (
            <Alert tone="danger">{error}</Alert>
          ) : (
            <Alert tone="info">Ready to post. Copy the script below.</Alert>
          )}

          <div className="embed-output">
            <div className="row row--between embed-output__head">
              <span className="muted mono">embed.json</span>
              <Button size="sm" variant={copied ? "primary" : "default"} onClick={copy}>
                {copied ? "Copied!" : "Copy script"}
              </Button>
            </div>
            <pre className="embed-output__code mono">{json}</pre>
            <div className="faint" style={{ marginTop: 8 }}>
              Paste into <span className="mono">,ce</span>, e.g.{" "}
              <span className="mono">,ce {json.replace(/\s+/g, " ").slice(0, 40)}…</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function EmbedPreview({ script: s, color }: { script: EmbedScript; color: string }) {
  const fields = (s.fields ?? []).filter((f) => f.name.trim() || f.value.trim());
  const empty = !s.title?.trim() && !s.description?.trim() && fields.length === 0;

  return (
    <div className="embed-preview" style={{ "--embed-color": color } as CSSProperties}>
      <div className="embed-preview__accent" />
      <div className="embed-preview__content">
        {empty && <div className="faint">Your embed preview will appear here.</div>}
        {s.author?.trim() && <div className="embed-preview__author">{s.author}</div>}
        {s.title?.trim() &&
          (s.url?.trim() ? (
            <a className="embed-preview__title embed-preview__title--link" href={s.url} onClick={(e) => e.preventDefault()}>
              {s.title}
            </a>
          ) : (
            <div className="embed-preview__title">{s.title}</div>
          ))}
        {s.description?.trim() && <div className="embed-preview__desc">{s.description}</div>}
        {s.thumbnail?.trim() && (
          <img className="embed-preview__thumb" src={s.thumbnail} alt="" onError={(e) => (e.currentTarget.style.display = "none")} />
        )}
        {fields.length > 0 && (
          <div className="embed-preview__fields">
            {fields.map((f, i) => (
              <div key={i} className={"embed-preview__field" + (f.inline ? " embed-preview__field--inline" : "")}>
                <div className="embed-preview__field-name">{f.name || "​"}</div>
                <div className="embed-preview__field-value">{f.value || "​"}</div>
              </div>
            ))}
          </div>
        )}
        {s.image?.trim() && (
          <img className="embed-preview__image" src={s.image} alt="" onError={(e) => (e.currentTarget.style.display = "none")} />
        )}
        {s.footer?.trim() && <div className="embed-preview__footer">{s.footer}</div>}
      </div>
    </div>
  );
}
