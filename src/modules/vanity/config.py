"""Vanity-rep tuning."""

from __future__ import annotations

# Debounce window before a revoke fires, so a client reconnect (a brief offline /
# status flicker) doesn't thrash the role off and back on.
REVOKE_GRACE_SECONDS = 60

# Cap concurrent role grants/revokes per guild to stay friendly to the role endpoint.
ROLE_CONCURRENCY = 2

# How often the backstop loop reconciles roles against the live repping set.
RECONCILE_INTERVAL_MINUTES = 15
