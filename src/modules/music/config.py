"""Music module configuration: Lavalink connection + playback tuning.

``LAVALINK_URI`` / ``LAVALINK_PASSWORD`` MUST match the lavalink service in
docker-compose.yml and the values in application.yml. Everything else tunes search,
the idle disconnect, queue limits, the skip-vote threshold, and the filter presets.
"""

from __future__ import annotations

import os

# ── Lavalink node (match application.yml: server.port + lavalink.server.password) ──
LAVALINK_URI = os.environ.get("LAVALINK_URI", "http://localhost:2333")
LAVALINK_PASSWORD = os.environ.get("LAVALINK_PASSWORD", "youshallnotpass")

# ── search ──────────────────────────────────────────────────────────────────────
# SoundCloud is the primary search source (it's stabler than YouTube, which gets
# rate-limited); search falls back to YouTube when SoundCloud returns nothing. Spotify
# links resolve as metadata only (track names searched on the playable source) via the
# LavaSrc plugin — Spotify can't stream directly. A bare URL (YouTube / SoundCloud /
# Spotify) is loaded directly and ignores the search source.
DEFAULT_SOURCE = "scsearch"
FALLBACK_SOURCE = "ytsearch"

# ── playback ─────────────────────────────────────────────────────────────────────
IDLE_DISCONNECT_SECONDS = 300   # leave an empty/finished channel after this grace window
DEFAULT_VOLUME = 50             # 0-100; mirrors MusicConfig.default_volume's default
MAX_QUEUE_LENGTH = 500          # reject queueing past this many tracks
SKIP_VOTE_RATIO = 0.5           # fraction of (non-bot) listeners whose votes force a skip
VOLUME_STEP = 10                # panel +/- volume button step

# ── filter presets (wavelink 3.x) ─────────────────────────────────────────────────
# Bass boosts the low equalizer bands; ``,bass <level>`` scales the gain (0 resets).
BASS_BANDS = (0, 1, 2, 3)       # the low-end equalizer bands ,bass touches
BASS_MAX_GAIN = 0.5             # equalizer gain applied at level 100
# Nightcore speeds up and pitches up the audio via a timescale filter.
NIGHTCORE = {"speed": 1.20, "pitch": 1.20, "rate": 1.0}
