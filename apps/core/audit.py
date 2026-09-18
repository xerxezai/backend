"""Security audit logging — login/logout events, with IP + user agent.

Best-effort by design: a logging failure (DB hiccup, etc.) must never break
the login/logout flow it's observing, so every write is wrapped and swallowed.
"""
import logging

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Prefers X-Forwarded-For (Railway/any proxy sits in front of Django) —
    falls back to REMOTE_ADDR for direct/local connections."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_audit_event(request, action, username='', source=''):
    """action: one of AuditLog.ACTION_CHOICES. source: 'erp' / 'lma' / 'partner'."""
    from apps.core.models import AuditLog
    try:
        AuditLog.objects.create(
            action=action,
            username=(username or '')[:150],
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
            source=source,
        )
    except Exception:
        logger.warning('Audit log write failed for action=%s username=%s', action, username, exc_info=True)
