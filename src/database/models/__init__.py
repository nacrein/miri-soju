"""Import every model so SQLAlchemy's metadata (and Alembic) sees all tables."""

from src.database.models.automod import (
    AutomodConfig,
    AutomodDomain,
    AutomodExemptChannel,
    AutomodExemptRole,
    AutomodWord,
)
from src.database.models.autorole import AutoRole
from src.database.models.blacklist import Blacklist
from src.database.models.boosterrole import BoosterRole, BoosterRoleConfig
from src.database.models.buttonrole import ButtonRole
from src.database.models.case import ModCase
from src.database.models.command_usage import CommandUsage
from src.database.models.errorlog import ErrorLog
from src.database.models.giveaway import Giveaway, GiveawayEntry
from src.database.models.guild import GuildConfig
from src.database.models.immune import ImmuneEntry
from src.database.models.jail import JailedMember, ModerationConfig
from src.database.models.level import ChannelMultiplier, LevelConfig, LevelReward, MemberLevel
from src.database.models.music import MusicConfig
from src.database.models.poll import Poll, PollVote
from src.database.models.reactionrole import ReactionRole
from src.database.models.reminder import Reminder
from src.database.models.staff import StaffMember
from src.database.models.starboard import StarboardConfig, StarboardEntry
from src.database.models.sticky import StickyMessage
from src.database.models.tag import Tag
from src.database.models.temprole import TempRole
from src.database.models.timer import Timer
from src.database.models.vanity import VanityConfig, VanityTracker
from src.database.models.voicemaster import VoiceMasterChannel, VoiceMasterConfig
from src.database.models.webhook import ManagedWebhook
from src.database.models.welcome import WelcomeConfig

__all__ = [
    "GuildConfig",
    "ModCase", "ModerationConfig", "JailedMember", "ImmuneEntry", "TempRole",
    "ManagedWebhook", "ReactionRole", "ButtonRole", "StickyMessage", "Timer", "Reminder",
    "AutoRole", "Tag", "WelcomeConfig", "StarboardConfig", "StarboardEntry",
    "Giveaway", "GiveawayEntry", "Poll", "PollVote",
    "LevelConfig", "MemberLevel", "LevelReward", "ChannelMultiplier",
    "MusicConfig",
    "AutomodConfig", "AutomodWord", "AutomodDomain", "AutomodExemptRole", "AutomodExemptChannel",
    "BoosterRoleConfig", "BoosterRole",
    "VoiceMasterConfig", "VoiceMasterChannel",
    "VanityConfig", "VanityTracker",
    "ErrorLog",
    "CommandUsage",
    "StaffMember",
    "Blacklist",
]
