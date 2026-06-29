// Builders for Discord CDN URLs + small display helpers.
import type { Guild, User } from "./types";

const CDN = "https://cdn.discordapp.com";

export function avatarUrl(user: User, size = 64): string | null {
  if (!user.avatar) return null;
  return `${CDN}/avatars/${user.id}/${user.avatar}.png?size=${size}`;
}

export function guildIconUrl(guild: Guild, size = 64): string | null {
  if (!guild.icon) return null;
  return `${CDN}/icons/${guild.id}/${guild.icon}.png?size=${size}`;
}

export function displayName(user: User): string {
  return user.global_name || user.username;
}

/** First letters of a server name, for the icon fallback. */
export function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase();
}
