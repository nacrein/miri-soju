import { guildIconUrl, initials } from "../lib/discord";
import type { Guild } from "../lib/types";

export function GuildIcon({ guild, size = 44 }: { guild: Guild; size?: number }) {
  const url = guildIconUrl(guild, 128);
  return (
    <div className="guild-icon" style={{ width: size, height: size }}>
      {url ? <img src={url} alt="" /> : initials(guild.name)}
    </div>
  );
}
