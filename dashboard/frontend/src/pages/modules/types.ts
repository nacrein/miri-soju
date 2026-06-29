import type { GuildMeta } from "../../lib/types";

/** Every module panel receives the guild id and its roles/channels (for selects). */
export interface PanelProps {
  guildId: string;
  meta: GuildMeta;
}
