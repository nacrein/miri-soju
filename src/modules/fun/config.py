"""Fun module tuning: every list, threshold, label, and colour lives here.

No logic, just data. Adding a trait, retuning a tier, or changing a cooldown is a
one-file edit. Each flavour list is kept at 20 entries so a reroll feels varied.
Tier tables are ascending ``(min_value, label)`` pairs: the resolver picks the
highest tier whose minimum the value clears (see ``cog._tier``).
"""

from __future__ import annotations

import discord

# ── gif interaction commands ──────────────────────────────────────────────────
# Total request budget for a nekos.best call (connect + read). Short on purpose so
# a slow upstream never makes a reaction command hang: on timeout we retry once,
# then fall back to a gif-less embed.
GIF_TIMEOUT_SECONDS = 8.0
# Per-user cooldown on every reaction command. Doubles as a shield on the upstream
# API: at most one in-flight call per user every few seconds.
GIF_COOLDOWN_SECONDS = 3.0

# ── per-command colours (override embeds.info where it adds flavour) ───────────
COLOR_RIZZ = discord.Color.from_str("#E84F8C")     # flirty pink
COLOR_AURA = discord.Color.from_str("#8A5CD1")     # violet
COLOR_DELULU = discord.Color.from_str("#D96BB0")   # bubblegum
COLOR_SIGMA = discord.Color.from_str("#3A3A44")    # graphite
COLOR_GLAZING = discord.Color.from_str("#D9A441")  # gold
COLOR_SKILL = discord.Color.from_str("#B5503F")    # rust
COLOR_NPC = discord.Color.from_str("#7A7F8A")      # grey
COLOR_BASED = discord.Color.from_str("#5F8D7E")    # sage (approval)
COLOR_RATIO = discord.Color.from_str("#5865F2")    # blurple
COLOR_CAUGHT = discord.Color.from_str("#C0392B")   # alarm red
COLOR_ICK = discord.Color.from_str("#9B8AA0")      # muted mauve

# ── scored-command tiers (ascending min, label) ───────────────────────────────
RIZZ_TIERS = [
    (0, "no rizz"),
    (20, "mid"),
    (45, "certified rizzler"),
    (70, "W rizz"),
    (90, "Ohio rizz god"),
]

# Aura is the one score that can go negative; the roll is bounded by these.
AURA_MIN = -1000
AURA_MAX = 1000
AURA_TIERS = [
    (-1000, "aura vacuum"),
    (-500, "negative aura"),
    (0, "no aura"),
    (250, "decent aura"),
    (500, "high aura"),
    (800, "aura farming"),
]

DELULU_TIERS = [
    (0, "grounded in reality"),
    (25, "a little delulu"),
    (50, "certified delulu"),
    (75, "very delulu"),
    (90, "delulu is the solulu"),
]

SIGMA_TIERS = [
    (0, "beta energy"),
    (30, "developing"),
    (55, "sigma"),
    (75, "alpha sigma"),
    (90, "sigma grindset god"),
]

GLAZING_TIERS = [
    (0, "no glaze"),
    (25, "light glaze"),
    (50, "glazing"),
    (75, "heavy glaze"),
    (95, "professional glazer"),
]

SKILL_TIERS = [
    (0, "minor skill issue"),
    (30, "moderate skill issue"),
    (55, "severe skill issue"),
    (80, "critical skill issue"),
    (95, "terminal skill issue"),
]

BASED_TIERS = [
    (0, "cringe"),
    (25, "slightly based"),
    (50, "based"),
    (75, "very based"),
    (92, "based and redpilled"),
]

# ── flavour lists (20 each) ────────────────────────────────────────────────────
NPC_TRAITS = [
    "repeats the same three lines of dialogue",
    "stares at a wall until spoken to",
    "stands perfectly still in the town square",
    "only ever walks in straight lines",
    "says 'I used to be an adventurer like you'",
    "turns to face you the moment you approach",
    "has no thoughts behind the eyes",
    "reboots when asked an original question",
    "follows a fixed daily pathing loop",
    "laughs exactly half a second too late",
    "owns one outfit and wears it every day",
    "agrees with whoever spoke last",
    "buffers for a moment before replying",
    "cannot leave a ten foot radius",
    "reacts to every event with the same emoji",
    "clips through the furniture sometimes",
    "reads tutorial tips out loud",
    "asks 'is it the weekend yet' every day",
    "has dialogue options but no real choice",
    "despawns the second you stop looking",
]

SIGMA_QUOTES = [
    "While they slept, I grinded.",
    "I don't lose, I learn.",
    "Discipline is just remembering what you want.",
    "Lions don't lose sleep over the opinions of sheep.",
    "Rise. Grind. Repeat.",
    "Comfort is the enemy of progress.",
    "I work in silence and let the results talk.",
    "No days off, only down payments.",
    "The grind does not care how you feel.",
    "Be so consistent they think you're cheating.",
    "Sleep is for people without goals.",
    "I negotiate with no one, least of all myself.",
    "Everyone wants the view, nobody wants the climb.",
    "Average was a choice and I declined it.",
    "Motivation is for amateurs, I run on routine.",
    "Talk less, lift more.",
    "I don't chase, I attract, then I keep building.",
    "They build excuses, I build empires.",
    "Your only competition is who you were yesterday.",
    "Silence is the loudest flex.",
]

ICKS = [
    "says 'no offense' right before being offensive",
    "claps when the plane lands",
    "chews with the headset mic still on",
    "calls their food 'noms'",
    "trips on flat pavement then glares at it",
    "texts back a single 'k'",
    "laughs at their own joke before finishing it",
    "refers to themselves in the third person",
    "narrates what they are about to do",
    "sends a voice note just to say 'ok'",
    "reply-alls to the entire server",
    "loses a thumb war and demands a rematch",
    "orders for the whole table uninvited",
    "uses way too many ellipses...",
    "high fives and misses every single time",
    "reads the menu out loud word for word",
    "says 'per my last message' unironically",
    "double texts within five seconds",
    "corrects your grammar in a casual chat",
    "waves back at someone waving past them",
]

CAUGHT_EVIDENCE = [
    "a 4K screen recording with timestamps",
    "three eyewitnesses and a group chat log",
    "security footage from the lobby camera",
    "a screenshot that was never deleted",
    "the read receipt at 3:47 AM",
    "a reflection in someone's glasses",
    "the location tag left on the photo",
    "a voice note they forgot to delete",
    "browser history that tells the whole story",
    "a receipt with the date printed on it",
    "the metadata on the original file",
    "a witness who wasn't even supposed to be there",
    "the quote-tweet that aged poorly",
    "a mirror selfie with too much background",
    "the typing indicator that never stopped",
    "a calendar invite nobody declined",
    "the same shirt in two different stories",
    "GPS pings from a phone left on",
    "a doorbell camera clip in crisp 1080p",
    "the group photo they cropped themselves out of",
]

GLAZING_SUBJECTS = [
    "their favourite streamer",
    "a thoroughly mid restaurant",
    "their own gym routine",
    "a Discord mod with no real powers",
    "their high school football stats",
    "a celebrity who will never know them",
    "their barber's questionable work",
    "a coin that is down ninety percent",
    "their friend's terrible business idea",
    "a movie nobody else liked",
    "their own mixtape",
    "a politician on the timeline",
    "their car with 200k on the clock",
    "a sports team mid losing streak",
    "an influencer's morning routine",
    "their pet's exceptional intelligence",
    "a phone that came out four years ago",
    "their own takes in the group chat",
    "a vending machine that ate their money",
    "the same restaurant they always pick",
]

# ── among-us (,sus): the embed colour is the rolled suspect colour ─────────────
AMONG_US_COLORS = {
    "Red": "#C51111",
    "Blue": "#132ED1",
    "Green": "#117F2D",
    "Pink": "#ED54BA",
    "Orange": "#EF7D0D",
    "Yellow": "#F5F557",
    "Black": "#3F474E",
    "White": "#D6E0F0",
    "Purple": "#6B2FBB",
    "Brown": "#71491E",
    "Cyan": "#38FEDC",
    "Lime": "#50EF39",
}

AMONG_US_TASKS = [
    "faking tasks in Electrical",
    "venting from Medbay to Security",
    "lingering near the body in Cafeteria",
    "following the crew one room behind",
    "standing on the Admin table",
    "never finishing the wires task",
    "self-reporting the body they found",
    "cutting the lights right before a kill",
    "hovering by the vent in Navigation",
    "sabotaging the reactor for no reason",
    "watching cams the entire round",
    "running from the group on sight",
    "swiping the card seventeen times",
    "closing doors behind the crew",
    "first to every body, every time",
    "faking the scan in Medbay",
    "looping the same hallway in Storage",
    "calling meetings with zero evidence",
    "staying silent through every discussion",
    "skipping every emergency vote",
]

# ── easter eggs: targeting the bot earns a canned reply ────────────────────────
# Keyed by command name; anything not listed uses GENERIC_BOT_REPLY.
BOT_REPLIES = {
    "rizz": "You tried to rizz me up. Access denied, but I respect the confidence.",
    "npc": "I run the simulation, I'm not an NPC inside it.",
    "sigma": "I grind 24/7 with no breaks. Out-discipline that.",
    "ratio": "You can't ratio a bot. No feelings to hurt here.",
    "sus": "I physically cannot vent. I am, regrettably, just a bot.",
    "skill": "My only skill issue is carrying this entire server.",
    "glazing": "Glaze me all you like, it still won't bump your rank.",
    "aura": "My aura is measured in uptime.",
    "caught": "Caught doing what? Running flawlessly?",
    "ick": "My only ick is downtime.",
    "delulu": "I'm not delulu, I'm deterministic.",
}
GENERIC_BOT_REPLY = "Flattering, but leave me out of this one."
