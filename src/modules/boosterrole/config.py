"""Booster-role tuning.

The 250-role guild ceiling is an external Discord limit, asserted inline at the
``,br create`` guard in the cog (not here)."""

from __future__ import annotations

# How often the cohort is repositioned relative to the anchor and dangling rows
# (whose Discord role no longer resolves) are pruned.
RECONCILE_INTERVAL_SECONDS = 600
