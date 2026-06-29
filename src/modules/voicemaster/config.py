"""VoiceMaster tuning."""

from __future__ import annotations

# Discord caps channel-name edits at 2 per 10 minutes; we pre-reject the third so
# the interaction never hangs waiting for the bucket to free.
RENAME_WINDOW_SECONDS = 600
RENAME_MAX = 2

# Per-user cooldown on the create channel so rapid join/leave can't spam new channels.
# Kept short so a normal "left, want a fresh room" rejoin feels instant; it only
# blocks truly rapid re-creation. Set to 0 to disable entirely.
CREATE_COOLDOWN_SECONDS = 3
