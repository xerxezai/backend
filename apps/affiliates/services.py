"""
Shared affiliate logic called from outside this app (apps.lma.views, on
successful enrollment) — kept separate from views.py so apps.lma doesn't
need to import request-handling code, just this one function.
"""
import logging
from decimal import Decimal

from django.utils import timezone

from apps.core.email import send_via_resend

from .models import Affiliate, AffiliateClick, AffiliateCommission

logger = logging.getLogger(__name__)

COOKIE_NAME = 'affiliate_ref'
FROM_EMAIL = 'onboarding@resend.dev'


def record_conversion_from_cookie(request, course, enrollment, created):
    """Called right after an Enrollment is created (paid or free). Reads the
    affiliate_ref cookie set when the student first clicked an affiliate
    link, and — if it resolves to an approved affiliate and this is a
    genuinely new enrollment for a paid course — creates the commission
    record. Silently no-ops for every other case (free course, no cookie,
    unknown/unapproved code, already-recorded enrollment); a broken or
    missing cookie must never block enrollment itself.
    """
    if not created or not course.price or course.price <= 0:
        return

    code = request.COOKIES.get(COOKIE_NAME)
    if not code:
        return

    try:
        affiliate = Affiliate.objects.get(affiliate_code=code, status='approved')
    except Affiliate.DoesNotExist:
        return

    if AffiliateCommission.objects.filter(enrollment=enrollment).exists():
        return

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
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
.wrap{{max-width:520px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
.hdr{{background:linear-gradient(135deg,#071a33 0%,#04101f 100%);padding:32px 36px;text-align:center}}
.hdr h1{{color:#D93522;font-family:Georgia,serif;font-size:22px;margin:0 0 4px}}
.body{{padding:32px 36px;font-size:14px;color:#333;line-height:1.7}}
.amt{{background:#fafaf8;border-left:3px solid #D93522;border-radius:0 8px 8px 0;padding:16px 20px;margin:18px 0}}
.amt .n{{font-size:28px;font-weight:800;color:#D93522}}
.ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:16px 36px;text-align:center;font-size:12px;color:#9b9690}}
</style></head><body><div class="wrap">
<div class="hdr"><h1>XERXEZ Academy</h1></div>
<div class="body">
<p>Hi {affiliate.full_name.split()[0] if affiliate.full_name else ''},</p>
<p>You just earned a new commission!</p>
<div class="amt"><div class="n">₹{amount}</div><div>{course.title} · Pending review</div></div>
<p>Track it any time from your affiliate dashboard.</p>
</div>
<div class="ftr">XERXEZ Academy &nbsp;·&nbsp; xerxez.com</div>
</div></body></html>"""
    send_via_resend(to=affiliate.email, subject='You earned a new commission — XERXEZ Academy', html=html, text=plain, from_email=FROM_EMAIL)
