import type { ComponentType } from "react";

import AutomodPanel from "./AutomodPanel";
import AutorolesPanel from "./AutorolesPanel";
import BoosterRolePanel from "./BoosterRolePanel";
import LevelingPanel from "./LevelingPanel";
import ModerationPanel from "./ModerationPanel";
import MusicPanel from "./MusicPanel";
import PrefixPanel from "./PrefixPanel";
import ServerlogPanel from "./ServerlogPanel";
import StarboardPanel from "./StarboardPanel";
import TagsPanel from "./TagsPanel";
import VanityPanel from "./VanityPanel";
import VoiceMasterPanel from "./VoiceMasterPanel";
import WelcomePanel from "./WelcomePanel";
import type { PanelProps } from "./types";

export interface ModuleDef {
  key: string; // matches the URL segment and the API path prefix
  label: string;
  icon: string; // unicode fallback
  emojiName?: string; // bot emoji registry key (src/core/emojis.py) for custom art
  component: ComponentType<PanelProps>;
}

// Order here = order in the left nav. Add a module by writing its panel + router
// and adding one line here (the dashboard is intentionally not auto-generated).
export const MODULES: ModuleDef[] = [
  { key: "leveling", label: "Leveling", icon: "📈", emojiName: "xp", component: LevelingPanel },
  { key: "automod", label: "AutoMod", icon: "🛡️", emojiName: "shield", component: AutomodPanel },
  { key: "serverlog", label: "Server Log", icon: "📜", emojiName: "message_edit", component: ServerlogPanel },
  { key: "moderation", label: "Moderation", icon: "🔨", emojiName: "ban", component: ModerationPanel },
  { key: "prefix", label: "Prefix", icon: "⌨️", component: PrefixPanel },
  { key: "welcome", label: "Welcome", icon: "👋", component: WelcomePanel },
  { key: "starboard", label: "Starboard", icon: "⭐", component: StarboardPanel },
  { key: "autoroles", label: "Autoroles", icon: "🎭", component: AutorolesPanel },
  { key: "tags", label: "Tags", icon: "🏷️", component: TagsPanel },
  { key: "boosterrole", label: "Booster Roles", icon: "🎨", component: BoosterRolePanel },
  { key: "vanity", label: "Vanity", icon: "✨", component: VanityPanel },
  { key: "voicemaster", label: "VoiceMaster", icon: "🔊", component: VoiceMasterPanel },
  { key: "music", label: "Music", icon: "🎵", component: MusicPanel },
];

export const defaultModuleKey = MODULES[0].key;
