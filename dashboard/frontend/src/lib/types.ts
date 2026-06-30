// Wire types — the TypeScript mirror of dashboard/schemas.py.
// Every Discord id is a string here too (64-bit; unsafe as a JS number).

export interface User {
  id: string;
  username: string;
  global_name: string | null;
  avatar: string | null;
}

export interface Guild {
  id: string;
  name: string;
  icon: string | null;
}

export interface Role {
  id: string;
  name: string;
  color: number;
  managed: boolean;
}

export interface Channel {
  id: string;
  name: string;
}

export interface GuildMeta {
  guild: Guild;
  roles: Role[];
  channels: Channel[]; // text channels (logs/announcements)
  voice_channels: Channel[]; // voice channels (e.g. VoiceMaster's join-to-create)
}

export interface Session {
  user: User;
  guilds: Guild[];
}

// ── leveling ──────────────────────────────────────────────────────────────
export interface LevelReward {
  level: number;
  role_id: string;
}
export interface ChannelMultiplier {
  channel_id: string;
  multiplier: number;
}
export interface LevelingConfig {
  enabled: boolean;
  xp_per_message: number;
  message_cooldown: number;
  announce_mode: "here" | "dm" | "channel";
  announce_channel_id: string | null;
  level_up_message: string;
  rewards: LevelReward[];
  multipliers: ChannelMultiplier[];
}

// ── serverlog ───────────────────────────────────────────────────────────────
export interface ServerlogConfig {
  log_channel_id: string | null;
  log_joins: boolean;
  log_leaves: boolean;
  log_message_delete: boolean;
  log_message_edit: boolean;
  log_mod_actions: boolean;
}

// ── prefix ──────────────────────────────────────────────────────────────────
export interface PrefixConfig {
  prefix: string | null;
  default: string;
}

// ── moderation ──────────────────────────────────────────────────────────────
export interface ModerationConfig {
  jail_role_id: string | null;
}

// ── automod ─────────────────────────────────────────────────────────────────
export interface AutomodConfig {
  enabled: boolean;
  log_only: boolean;
  dm_on_action: boolean;
  exempt_mods: boolean;
  strike_window_hours: number;
  filter_invites: boolean;
  filter_links: boolean;
  filter_spam: boolean;
  spam_count: number;
  spam_interval: number;
  duplicate_threshold: number;
  filter_mentions: boolean;
  mention_limit: number;
  block_everyone: boolean;
  filter_words: boolean;
  filter_caps: boolean;
  caps_percent: number;
  caps_min_len: number;
  filter_emoji: boolean;
  emoji_limit: number;
  timeout_at: number;
  timeout_minutes: number;
  timeout2_at: number;
  timeout2_minutes: number;
  kick_at: number;
  ban_at: number;
  words: string[];
  domains: string[];
  exempt_roles: string[];
  exempt_channels: string[];
}

// ── welcome / goodbye ─────────────────────────────────────────────────────────
export interface WelcomeConfig {
  welcome_channel_id: string | null;
  welcome_message: string | null;
  welcome_enabled: boolean;
  goodbye_channel_id: string | null;
  goodbye_message: string | null;
  goodbye_enabled: boolean;
}

// ── starboard ─────────────────────────────────────────────────────────────────
export interface StarboardConfig {
  channel_id: string | null;
  threshold: number;
  star_emoji: string;
  enabled: boolean;
  self_star: boolean;
}

// ── vanity ────────────────────────────────────────────────────────────────────
export interface VanityConfig {
  enabled: boolean;
  role_id: string | null;
  channel_id: string | null;
  message_template: string | null;
}

// ── music ─────────────────────────────────────────────────────────────────────
export interface MusicConfig {
  dj_role_id: string | null;
  command_channel_id: string | null;
  default_volume: number;
}

// ── boosterrole ───────────────────────────────────────────────────────────────
export interface BoosterRoleConfig {
  enabled: boolean;
  hoist_above: boolean;
  anchor_role_id: string | null;
}

// ── voicemaster ───────────────────────────────────────────────────────────────
export interface VoiceMasterConfig {
  enabled: boolean;
  create_channel_id: string | null;
}

// ── autoroles ─────────────────────────────────────────────────────────────────
export interface AutorolesConfig {
  roles: string[];
}

// ── tags ──────────────────────────────────────────────────────────────────────
export interface Tag {
  name: string;
  content: string;
  author_id: string;
  uses: number;
}
export interface TagsConfig {
  tags: Tag[];
}
