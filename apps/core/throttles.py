"""Brute-force protection for login endpoints.

DRF's built-in rate-string parser only understands whole units (5/min,
5/hour, 5/day) — it has no way to express "5 per 15 minutes", since the
number before the slash is the request count, not a multiplier on the period.
So this overrides `parse_rate` directly rather than relying on a
DEFAULT_THROTTLE_RATES string (which would raise KeyError on first use if
someone tried '5/15min' there — not a valid DRF rate).
"""
from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Max 5 login attempts per 15 minutes, keyed by client IP (inherited from
    AnonRateThrottle — logins are unauthenticated requests). Shared by every
    login surface: ERP (`auth/login/`), LMA (`lma/auth/login/`), Partner
    Portal (`partners/login/`).

    Commenting out DEFAULT_THROTTLE_RATES['login'] in settings.py (e.g. for
    local dev testing) disables this throttle entirely — get_rate() then
    returns None, and parse_rate keeps DRF's normal "no rate configured for
    this scope -> unlimited" contract instead of crashing. DRF's own
    SimpleRateThrottle.get_rate() does NOT degrade gracefully on a missing
    scope (it raises ImproperlyConfigured), so this override is required
    for that unset-key case to work at all, not just for the 15-minute
    duration override below."""
    scope = 'login'

    def get_rate(self):
        return self.THROTTLE_RATES.get(self.scope)

    def parse_rate(self, rate):
        if rate is None:
            return (None, None)
        # DRF's rate-string parser only understands whole units (5/min,
        # 5/hour, 5/day) — it has no way to express "5 per 15 minutes", since
        # the number before the slash is the request count, not a multiplier
        # on the period. So whenever a rate IS configured, hardcode the real
        # 5-per-15-minutes policy here rather than trying to encode it in the
        # settings string (which would be invalid DRF syntax, e.g. '5/15min').
        return (5, 15 * 60)
