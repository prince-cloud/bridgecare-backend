"""
Shared DRF throttle classes.

`ScopedRateThrottle` (the project default) keys on IP for anonymous requests,
which stops one machine hammering an endpoint but does nothing about a
distributed attempt to flood a single victim's inbox. The throttles here key on
a value taken from the request body instead, so limits apply per *target*
regardless of where the requests originate.
"""

import hashlib

from rest_framework.throttling import SimpleRateThrottle


class BaseFieldThrottle(SimpleRateThrottle):
    """Throttle keyed on a hashed request-body field rather than the client IP."""

    field = None

    def get_field_value(self, request):
        value = request.data.get(self.field) if hasattr(request, "data") else None
        if not isinstance(value, str):
            return None
        return value.strip().lower() or None

    def get_cache_key(self, request, view):
        value = self.get_field_value(request)
        if not value:
            # Nothing to key on: let the IP-based throttle handle this request.
            return None
        # Hashed so raw emails/phone numbers never land in the cache keyspace.
        ident = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": ident}


class PasswordResetEmailThrottle(BaseFieldThrottle):
    """
    Limit reset requests per email address.

    Blocks the mailbox-flooding attack in the audit: without this, an attacker
    rotating IPs can send unlimited reset mails to one victim.
    """

    scope = "password_reset_email"
    field = "email"
