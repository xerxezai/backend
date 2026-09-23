"""
Shared affiliate logic called from outside this app (apps.lma.views, on
successful enrollment) — kept separate from views.py so apps.lma doesn't
need to import request-handling code, just this one function.
"""
import logging
from decimal import Decimal

from django.utils import timezone

from apps.core.email import send_via_resend, render_v2_email

from .models import Affiliate, AffiliateClick, AffiliateCommission

logger = logging.getLogger(__name__)

COOKIE_NAME = 'affiliate_ref'
FROM_EMAIL = 'onboarding@resend.dev'


def record_conversion_from_cookie(request, course, enrollment, created, ref_code=None):
    """Called right after an Enrollment is created (paid or free). Attributes
    the conversion to an affiliate and — if it resolves to an approved
    affiliate and this is a genuinely new enrollment for a paid course —
    creates the commission record. Silently no-ops for every other case
    (free course, no code, unknown/unapproved code, already-recorded
    enrollment); a broken or missing code must never block enrollment itself.

    `ref_code` (preferred) is the affiliate code the frontend read from its
    own `affiliate_ref` cookie and sent explicitly in the request body. The
    frontend and backend usually live on different origins (e.g. xerxez.com
    vs. a Railway API domain), so a cookie set via `document.cookie` on the
    frontend page is never actually present in `request.COOKIES` here — it's
    a same-origin-only cookie, not something a cross-origin fetch() forwards
    automatically. Falling back to `request.COOKIES` keeps same-origin
    callers (the /affiliates/track/<code>/ redirect, which sets and reads the
    cookie on the API's own origin) working unchanged.
    """
    if not created or not course.price or course.price <= 0:
        logger.info('affiliate conversion skip: created=%s price=%s', created, getattr(course, 'price', None))
        return

    code = ref_code or request.COOKIES.get(COOKIE_NAME)
    if not code:
        logger.info('affiliate conversion skip: no ref_code and no %s cookie', COOKIE_NAME)
        return

    try:
        affiliate = Affiliate.objects.get(affiliate_code=code.upper(), status='approved')
    except Affiliate.DoesNotExist:
        logger.info('affiliate conversion skip: no approved affiliate for code=%s', code)
        return

    if AffiliateCommission.objects.filter(enrollment=enrollment).exists():
        logger.info('affiliate conversion skip: commission already recorded for enrollment=%s', enrollment.id)
        return

    logger.info('affiliate conversion: recording commission for affiliate=%s enrollment=%s', affiliate.affiliate_code, enrollment.id)

    rate = affiliate.commission_rate
    amount = (course.price * rate / Decimal('100')).quantize(Decimal('0.01'))

    AffiliateCommission.objects.create(
        affiliate=affiliate, enrollment=enrollment, course=course,
        course_price=course.price, commission_rate=rate, commission_amount=amount,
    )
    affiliate.total_conversions += 1
    affiliate.total_earnings += amount
    affiliate.save(update_fields=['total_conversions', 'total_earnings'])

    AffiliateClick.objects.filter(affiliate=affiliate, course=course, converted=False).update(converted=True)

    _send_commission_email(affiliate, course, amount)


def _send_commission_email(affiliate: Affiliate, course, amount) -> None:
    if not affiliate.email:
        return
    plain = f"""Hi {affiliate.full_name.split()[0] if affiliate.full_name else ''},

You just earned a new commission!

Course: {course.title}
Commission: ₹{amount}
Status: Pending review

It'll show up in your affiliate dashboard, and you'll be notified again once it's approved and paid.

xerxez.com/lma/affiliate/dashboard

— The XERXEZ Team
""".strip()
    body_html = (
        f'<p>Hi {affiliate.full_name.split()[0] if affiliate.full_name else ""},</p>'
        f'<p>You just earned a new commission!</p>'
        f'<div style="background:#F4F7FA;border-left:3px solid #D93522;border-radius:0 8px 8px 0;padding:16px 20px;margin:18px 0">'
        f'<div style="font-size:28px;font-weight:800;color:#D93522">₹{amount}</div>'
        f'<div style="font-size:13px;color:#6b7280;margin-top:4px">{course.title} · Pending review</div>'
        f'</div>'
        f'<p>Track it any time from your affiliate dashboard.</p>'
    )
    html = render_v2_email(
        title='New commission earned!', body_html=body_html,
        cta_label='Open Affiliate Dashboard', cta_url='https://www.xerxez.com/lma/affiliate/dashboard',
    )
    send_via_resend(to=affiliate.email, subject='You earned a new commission — XERXEZ Academy', html=html, text=plain, from_email=FROM_EMAIL)
