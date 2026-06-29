import type { ComponentType } from "react";

import AutomodPanel from "./AutomodPanel";
import LevelingPanel from "./LevelingPanel";
import ModerationPanel from "./ModerationPanel";
import PrefixPanel from "./PrefixPanel";
import ServerlogPanel from "./ServerlogPanel";
import type { PanelProps } from "./types";

export interface ModuleDef {
  key: string; // matches the URL segment and the API path prefix
  label: string;
  icon: string;
  component: ComponentType<PanelProps>;
}

// Order here = order in the left nav. Add a module by writing its panel + router
// and adding one line here (the dashboard is intentionally not auto-generated).
export const MODULES: ModuleDef[] = [
  { key: "leveling", label: "Leveling", icon: "📈", component: LevelingPanel },
  { key: "automod", label: "AutoMod", icon: "🛡️", component: AutomodPanel },
  { key: "serverlog", label: "Server Log", icon: "📜", component: ServerlogPanel },
  { key: "moderation", label: "Moderation", icon: "🔨", component: ModerationPanel },
  { key: "prefix", label: "Prefix", icon: "⌨️", component: PrefixPanel },
];

export const defaultModuleKey = MODULES[0].key;
