// Client mirror of src/modules/embed/script.py — the same caps, the same color
// rules, the same "needs a title, description, or a field" check — so what the
// builder previews and copies is exactly what `,ce <json>` will accept in Discord.
import type { EmbedScript } from "./types";

export const CAPS = {
  title: 256,
  description: 4000,
  author: 256,
  footer: 2048,
  fieldName: 256,
  fieldValue: 1024,
  fields: 25,
} as const;

const HEX6 = /^#?[0-9a-fA-F]{6}$/;
const HEX3 = /^#?[0-9a-fA-F]{3}$/;

/** Parse a color like "#5865f2", "0x5865f2", "rgb(88,101,242)", or a decimal int
 *  into a normalized "#rrggbb". Returns null if it isn't a valid color. */
export function parseColor(input: string): string | null {
  const s = (input ?? "").trim();
  if (!s) return null;
  if (/^\d+$/.test(s)) {
    const v = parseInt(s, 10);
    if (v < 0 || v > 0xffffff) return null;
    return "#" + v.toString(16).padStart(6, "0");
  }
  const rgb = s.match(/^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$/i);
  if (rgb) {
    const [r, g, b] = [rgb[1], rgb[2], rgb[3]].map(Number);
    if ([r, g, b].some((n) => n > 255)) return null;
    return "#" + [r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("");
  }
  if (s.startsWith("0x") && HEX6.test(s.slice(2))) return "#" + s.slice(2).toLowerCase();
  if (HEX6.test(s)) return "#" + s.replace("#", "").toLowerCase();
  if (HEX3.test(s)) {
    const h = s.replace("#", "");
    return "#" + h.split("").map((c) => c + c).join("").toLowerCase();
  }
  return null;
}

/** First validation error (matching build()'s rules), or null if postable. */
export function validate(s: EmbedScript): string | null {
  const fields = s.fields ?? [];
  if (s.color && parseColor(s.color) === null) return "Color must be a hex like #5865f2.";
  if (fields.length > CAPS.fields) return `A maximum of ${CAPS.fields} fields is allowed.`;
  const hasField = fields.some((f) => f.name.trim() || f.value.trim());
  if (!s.title?.trim() && !s.description?.trim() && !hasField) {
    return "Add a title, a description, or at least one field.";
  }
  return null;
}

/** The compact `to_script`-shaped object: only fields the user actually set. */
export function toScript(s: EmbedScript): EmbedScript {
  const out: EmbedScript = {};
  if (s.title?.trim()) out.title = s.title;
  if (s.description?.trim()) out.description = s.description;
  if (s.url?.trim()) out.url = s.url;
  if (s.color?.trim()) out.color = parseColor(s.color) ?? s.color;
  if (s.author?.trim()) out.author = s.author;
  if (s.footer?.trim()) out.footer = s.footer;
  if (s.image?.trim()) out.image = s.image;
  if (s.thumbnail?.trim()) out.thumbnail = s.thumbnail;
  const fields = (s.fields ?? []).filter((f) => f.name.trim() || f.value.trim());
  if (fields.length) out.fields = fields;
  return out;
}

export function toJson(s: EmbedScript): string {
  return JSON.stringify(toScript(s), null, 2);
}
