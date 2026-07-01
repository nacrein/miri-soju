// Brand icons. Icons resolve against the bot's own emoji registry
// (src/core/emojis.py, served at /api/emojis): the moment you upload custom art
// and set its id there, the whole site swaps from the unicode fallback to your
// real emoji, no frontend change. Until then, the curated fallbacks below show.
import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { BotEmojiMap } from "./types";

// Matches a Discord custom-emoji mention: <:name:id> or animated <a:name:id>.
const CUSTOM = /^<(a?):(\w+):(\d+)>$/;

export function useBotEmojis() {
  return useQuery<BotEmojiMap>({
    queryKey: ["emojis"],
    queryFn: () => api.get<BotEmojiMap>("/emojis"),
    staleTime: Infinity,
    retry: false,
  });
}

function EmojiImg({ token, className }: { token: string; className?: string }) {
  const m = token.match(CUSTOM);
  if (!m) return <span className={className}>{token}</span>;
  const animated = m[1] === "a";
  const url = `https://cdn.discordapp.com/emojis/${m[3]}.${animated ? "gif" : "webp"}?size=48`;
  return <img className={"emoji-img " + (className ?? "")} src={url} alt="" loading="lazy" />;
}

/** Render a brand icon by its registry name, falling back to a unicode glyph.
 *  Shows the bot's custom emoji image only once a real id exists for `name`. */
export function BotIcon({
  name,
  fallback,
  className,
}: {
  name?: string;
  fallback: string;
  className?: string;
}) {
  const { data } = useBotEmojis();
  const token = name ? data?.[name] : undefined;
  if (token && CUSTOM.test(token)) return <EmojiImg token={token} className={className} />;
  return <span className={className}>{fallback}</span>;
}

// category name → (bot emoji registry key, curated unicode fallback).
export const CATEGORY_ICON: Record<string, { name: string; fallback: string }> = {
  Leveling: { name: "xp", fallback: "📈" },
  Moderation: { name: "shield", fallback: "🛡️" },
  "Server Setup": { name: "settings", fallback: "⚙️" },
  Utility: { name: "info", fallback: "🧰" },
  Music: { name: "voice", fallback: "🎵" },
  Fun: { name: "win", fallback: "🎉" },
  Bot: { name: "crown", fallback: "👑" },
};

export function CategoryIcon({ category, className }: { category: string; className?: string }) {
  const e = CATEGORY_ICON[category];
  return <BotIcon name={e?.name} fallback={e?.fallback ?? "✨"} className={className} />;
}
