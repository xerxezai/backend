"""Shared Resend email sending helper.

Used by any app that needs to send transactional email via Resend
(contact form, LMA notifications, etc.) instead of Django's SMTP backend.
"""
import logging

import resend
from django.conf import settings

logger = logging.getLogger(__name__)


def send_via_resend(*, to, subject, html, text, from_email, reply_to=None):
    """Send one email through Resend. Never raises — a failed email must not break the caller's request."""
    resend.api_key = settings.RESEND_API_KEY
    if not resend.api_key:
        logger.error("RESEND_API_KEY is not set — skipping email send (subject=%r, to=%r)", subject, to)
        return
    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to] if isinstance(to, str) else to,
        "subject": subject,
        "html": html,
        "text": text,
    }
    if reply_to:
        params["reply_to"] = reply_to
    try:
        resend.Emails.send(params)
    except Exception as exc:
        logger.error("Resend email failed (subject=%r, to=%r): %s", subject, to, exc)
