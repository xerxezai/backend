"""Partner Portal authentication.

Approved partners aren't Django Users — there's no separate account/password
system here, just the existing PartnerApplication row. Login is
email + portal_token (a random string generated the first time an
application is approved, see PartnerApplication.ensure_portal_token), and
every Partner Portal API call after that carries both as headers
(X-Partner-Email / X-Partner-Token) rather than a JWT — mirroring how this
app already carries the platform-admin's "active company" as a header
instead of a server session (see apps.companies.utils) rather than inventing
a second parallel auth system for what is, for now, a small feature.
"""
from .models import PartnerApplication


def get_partner_from_request(request):
    """Returns the authenticated PartnerApplication for this request, or None."""
    email = request.headers.get('X-Partner-Email')
    token = request.headers.get('X-Partner-Token')
    if not email or not token:
        return None
    try:
        return PartnerApplication.objects.get(email=email, portal_token=token, status='approved')
    except PartnerApplication.DoesNotExist:
        return None
