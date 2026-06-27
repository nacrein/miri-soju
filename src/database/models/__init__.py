"""Import every model so SQLAlchemy's metadata (and Alembic) sees all tables."""

from src.database.models.buttonrole import ButtonRole
from src.database.models.case import ModCase
from src.database.models.guild import GuildConfig
from src.database.models.immune import ImmuneEntry
from src.database.models.jail import JailedMember, ModerationConfig
from src.database.models.player import Player
from src.database.models.reactionrole import ReactionRole
from src.database.models.reminder import Reminder
from src.database.models.sticky import StickyMessage
from src.database.models.temprole import TempRole
from src.database.models.timer import Timer
from src.database.models.transaction import Transaction
from src.database.models.webhook import ManagedWebhook

__all__ = [
    "Player", "GuildConfig", "Transaction",
    "ModCase", "ModerationConfig", "JailedMember", "ImmuneEntry", "TempRole",
    "ManagedWebhook", "ReactionRole", "ButtonRole", "StickyMessage", "Timer", "Reminder",
]
