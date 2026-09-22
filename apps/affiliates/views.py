import logging
import secrets
import string

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response

from apps.core.email import send_via_resend
from apps.lma.models import Course

from .models import Affiliate, AffiliateClick, AffiliateCommission
from .serializers import (
    AffiliateApplySerializer, AffiliateSerializer, AffiliateAdminListSerializer,
    AffiliateCommissionSerializer, AffiliateCommissionAdminSerializer,
)
from .services import COOKIE_NAME

logger = logging.getLogger(__name__)
User = get_user_model()

ADMIN_EMAIL = 'info@xerxez.com'
# TEMPORARY: xerxez.com is not yet verified in Resend — see apps.partners.views for the
# same note; switch to a verified xerxez.com sender once domain verification completes.
FROM_EMAIL = 'onboarding@resend.dev'
COOKIE_MAX_AGE = 30 * 24 * 60 * 60  # 30 days


class IsStaffUser(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)


class IsApprovedAffiliate(IsAuthenticated):
    """Gates the affiliate-facing portal endpoints."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        affiliate = getattr(request.user, 'affiliate', None)
        return affiliate is not None and affiliate.status == 'approved'


# ── emails ────────────────────────────────────────────────────────────────

def _application_notification_email(a: Affiliate) -> tuple:
    plain = f"""New affiliate application received.

Name: {a.full_name}
Email: {a.email}
Requested Code: {a.affiliate_code}
Company: {a.company_name or '—'}
Website: {a.website or '—'}
Promotion Method: {a.promotion_method}
Audience Size: {a.audience_size}

Review this application in the LMA admin panel.
""".strip()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
.wrap{{max-width:560px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
.hdr{{background:linear-gradient(135deg,#071a33 0%,#04101f 100%);padding:32px 36px;text-align:center}}
.hdr h1{{color:#D93522;font-family:Georgia,serif;font-size:22px;margin:0}}
.body{{padding:32px 36px}}
table{{width:100%;border-collapse:collapse}}
td{{padding:10px 12px;font-size:14px;color:#333;border-bottom:1px solid #f0ede8}}
td:first-child{{width:36%;font-weight:700;color:#5a5650;font-size:11px;text-transform:uppercase;letter-spacing:.08em}}
.ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:16px 36px;text-align:center;font-size:12px;color:#9b9690}}
</style></head><body><div class="wrap">
<div class="hdr"><h1>XERXEZ Academy</h1><p style="color:rgba(255,255,255,.5);margin:6px 0 0;font-size:12px">New Affiliate Application</p></div>
<div class="body"><table>
<tr><td>Name</td><td>{a.full_name}</td></tr>
<tr><td>Email</td><td>{a.email}</td></tr>
<tr><td>Code</td><td>{a.affiliate_code}</td></tr>
<tr><td>Company</td><td>{a.company_name or '—'}</td></tr>
<tr><td>Website</td><td>{a.website or '—'}</td></tr>
<tr><td>Promotion Method</td><td>{a.promotion_method}</td></tr>
<tr><td>Audience Size</td><td>{a.audience_size}</td></tr>
</table></div>
<div class="ftr">XERXEZ Academy &nbsp;·&nbsp; xerxez.com</div>
</div></body></html>"""
    return plain, html


def _applicant_confirmation_email(a: Affiliate) -> tuple:
    first = a.full_name.split()[0] if a.full_name else 'there'
    plain = f"""Hi {first},

Thanks for applying to the XERXEZ Academy affiliate program. We've received
your application (code: {a.affiliate_code}) and will review it shortly.

— The XERXEZ Team
""".strip()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
.wrap{{max-width:520px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
.hdr{{background:#071a33;padding:32px 36px;text-align:center}}
.hdr h1{{color:#D93522;font-family:Georgia,serif;font-size:20px;margin:0}}
.body{{padding:32px 36px;font-size:14px;color:#333;line-height:1.7}}
.ftr{{background:#071a33;padding:16px 36px;text-align:center;font-size:12px;color:rgba(255,255,255,.5)}}
</style></head><body><div class="wrap">
<div class="hdr"><h1>XERXEZ Academy</h1></div>
<div class="body"><p>Hi {first},</p>
<p>Thanks for applying to the XERXEZ Academy affiliate program. We've received your application
(code: <strong>{a.affiliate_code}</strong>) and will review it shortly.</p>
<p>— The XERXEZ Team</p></div>
<div class="ftr">XERXEZ Academy &nbsp;·&nbsp; xerxez.com</div>
</div></body></html>"""
    return plain, html


def _approval_email(a: Affiliate, password: str) -> tuple:
    plain = f"""Congratulations {a.full_name.split()[0] if a.full_name else ''}!

Your XERXEZ Academy affiliate application has been approved.

Affiliate Code: {a.affiliate_code}
Commission Rate: {a.commission_rate}%
Login: xerxez.com/lma/login
Email: {a.email}
Password: {password}

Your affiliate link format:
xerxez.com/lma/courses/:id?ref={a.affiliate_code}

Please change your password after first login.

— The XERXEZ Team
""".strip()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
.wrap{{max-width:560px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
.hdr{{background:linear-gradient(135deg,#071a33 0%,#04101f 100%);padding:32px 36px;text-align:center}}
.hdr h1{{color:#D93522;font-family:Georgia,serif;font-size:22px;margin:0}}
.body{{padding:32px 36px;font-size:14px;color:#333;line-height:1.7}}
.creds{{background:#fafaf8;border-radius:10px;border-left:3px solid #D93522;padding:16px 20px;margin:18px 0;font-size:13px}}
.creds p{{margin:4px 0;color:#5a5650}}
.creds strong{{color:#141413}}
.cta{{display:inline-block;margin-top:8px;padding:12px 30px;background:linear-gradient(135deg,#D93522,#b32a1a);color:#fff!important;font-size:13px;font-weight:700;border-radius:100px;text-decoration:none}}
.ftr{{background:#071a33;padding:16px 36px;text-align:center;font-size:12px;color:rgba(255,255,255,.5)}}
</style></head><body><div class="wrap">
<div class="hdr"><h1>XERXEZ Academy</h1><p style="color:rgba(255,255,255,.5);margin:6px 0 0;font-size:12px">Affiliate Program</p></div>
<div class="body">
<p>Congratulations {a.full_name.split()[0] if a.full_name else ''}!</p>
<p>Your affiliate application has been approved.</p>
<div class="creds">
<p><strong>Affiliate Code:</strong> {a.affiliate_code}</p>
<p><strong>Commission Rate:</strong> {a.commission_rate}%</p>
<p><strong>Email:</strong> {a.email}</p>
<p><strong>Password:</strong> {password}</p>
</div>
<p>Your affiliate link format: <code>xerxez.com/lma/courses/:id?ref={a.affiliate_code}</code></p>
<p style="color:#9b9690">Please change your password after first login.</p>
<div style="text-align:center"><a class="cta" href="https://www.xerxez.com/lma/affiliate/dashboard">Open Affiliate Dashboard</a></div>
</div>
<div class="ftr">XERXEZ Academy &nbsp;·&nbsp; xerxez.com</div>
</div></body></html>"""
    return plain, html


def _rejection_email(a: Affiliate) -> tuple:
    first = a.full_name.split()[0] if a.full_name else 'there'
    reason_line = f"\n\nReason: {a.rejection_reason}" if a.rejection_reason else ''
    plain = f"""Hi {first},

Thanks for your interest in the XERXEZ Academy affiliate program. After
review, we're not able to approve your application at this time.{reason_line}

— The XERXEZ Team
""".strip()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
.wrap{{max-width:520px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
.hdr{{background:#071a33;padding:32px 36px;text-align:center}}
.hdr h1{{color:#D93522;font-family:Georgia,serif;font-size:20px;margin:0}}
.body{{padding:32px 36px;font-size:14px;color:#333;line-height:1.7}}
.ftr{{background:#071a33;padding:16px 36px;text-align:center;font-size:12px;color:rgba(255,255,255,.5)}}
</style></head><body><div class="wrap">
<div class="hdr"><h1>XERXEZ Academy</h1></div>
<div class="body"><p>Hi {first},</p>
<p>Thanks for your interest in the XERXEZ Academy affiliate program. After review, we're not
able to approve your application at this time.{('<br><br>Reason: ' + a.rejection_reason) if a.rejection_reason else ''}</p>
<p>— The XERXEZ Team</p></div>
<div class="ftr">XERXEZ Academy &nbsp;·&nbsp; xerxez.com</div>
</div></body></html>"""
    return plain, html


# ── public application ───────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def apply(request):
    """POST /api/v1/affiliates/apply/"""
    serializer = AffiliateApplySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    affiliate = serializer.save()

    # Both emails go through send_via_resend, which already wraps the send in
    # try/except and skips (with a logged warning, not an exception) when
    # RESEND_API_KEY isn't configured — see apps/core/email.py. Failures here
    # never block the response: the Affiliate row is already saved above.
    plain, html = _application_notification_email(affiliate)
    send_via_resend(to=ADMIN_EMAIL, subject=f'New affiliate application from {affiliate.full_name}', html=html, text=plain, from_email=FROM_EMAIL)
    plain2, html2 = _applicant_confirmation_email(affiliate)
    send_via_resend(to=affiliate.email, subject='We received your affiliate application', html=html2, text=plain2, from_email=FROM_EMAIL)

    return Response(AffiliateSerializer(affiliate).data, status=201)


# ── affiliate portal ─────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def affiliate_dashboard(request):
    """GET /api/v1/affiliates/dashboard/"""
    affiliate = getattr(request.user, 'affiliate', None)
    if not affiliate:
        return Response({'error': 'No affiliate profile for this account.'}, status=404)

    pending_earnings = AffiliateCommission.objects.filter(
        affiliate=affiliate, status__in=['pending', 'approved']
    ).aggregate(total=Sum('commission_amount'))['total'] or 0

    recent_commissions = affiliate.commissions.all()[:10]

    return Response({
        'affiliate': AffiliateSerializer(affiliate).data,
        'pending_earnings': pending_earnings,
        'recent_commissions': AffiliateCommissionSerializer(recent_commissions, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsApprovedAffiliate])
def affiliate_links(request):
    """GET /api/v1/affiliates/links/ — every published course + this
    affiliate's code, so the frontend can build /lma/courses/:id?ref=CODE."""
    affiliate = request.user.affiliate
    courses = Course.objects.filter(status='published').order_by('title')
    return Response({
        'affiliate_code': affiliate.affiliate_code,
        'courses': [{'id': c.id, 'title': c.title, 'price': c.price} for c in courses],
    })


@api_view(['GET'])
@permission_classes([IsApprovedAffiliate])
def affiliate_commissions(request):
    """GET /api/v1/affiliates/commissions/"""
    affiliate = request.user.affiliate
    commissions = affiliate.commissions.all()
    return Response(AffiliateCommissionSerializer(commissions, many=True).data)


@api_view(['PUT'])
@permission_classes([IsApprovedAffiliate])
def affiliate_bank_details(request):
    """PUT /api/v1/affiliates/bank-details/ — affiliate updates their own payout details."""
    affiliate = request.user.affiliate
    affiliate.bank_details = request.data.get('bank_details', {}) or {}
    affiliate.save(update_fields=['bank_details'])
    return Response(AffiliateSerializer(affiliate).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def track_click(request, code):
    """GET /api/v1/affiliates/track/<code>/?course=<id> — records a click
    (best-effort; an unknown/unapproved code just redirects with no
    tracking) and redirects to the course page with the ref preserved so
    the frontend can also set its own cookie. course= is optional; falls
    back to the course browse page."""
    course_id = request.GET.get('course')
    course = Course.objects.filter(id=course_id).first() if course_id else None

    try:
        affiliate = Affiliate.objects.get(affiliate_code=code.upper(), status='approved')
        expires = timezone.now() + timezone.timedelta(days=30)
        AffiliateClick.objects.create(
            affiliate=affiliate, course=course,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:1000],
            cookie_expires=expires,
        )
        affiliate.total_clicks += 1
        affiliate.save(update_fields=['total_clicks'])
    except Affiliate.DoesNotExist:
        affiliate = None

    target = f'/lma/courses/{course.id}?ref={code}' if course else f'/lma/courses?ref={code}'
    response = redirect(f'https://www.xerxez.com{target}')
    if affiliate:
        response.set_cookie(COOKIE_NAME, affiliate.affiliate_code, max_age=COOKIE_MAX_AGE, samesite='Lax')
    return response


# ── admin ─────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsStaffUser])
def admin_list_affiliates(request):
    """GET /api/v1/affiliates/admin/list/"""
    affiliates = Affiliate.objects.all().order_by('-created_at')
    status_filter = request.GET.get('status')
    if status_filter:
        affiliates = affiliates.filter(status=status_filter)
    return Response(AffiliateAdminListSerializer(affiliates, many=True).data)


@api_view(['POST'])
@permission_classes([IsStaffUser])
def admin_approve_affiliate(request, affiliate_id):
    """POST /api/v1/affiliates/admin/<id>/approve/"""
    try:
        affiliate = Affiliate.objects.get(id=affiliate_id)
    except Affiliate.DoesNotExist:
        return Response({'error': 'Affiliate not found.'}, status=404)

    alphabet = string.ascii_letters + string.digits + '!@#$'
    raw_password = ''.join(secrets.choice(alphabet) for _ in range(14))

    user = User.objects.filter(email=affiliate.email).first()
    if not user:
        user = User.objects.create_user(
            username=affiliate.email, email=affiliate.email,
            first_name=affiliate.full_name.split()[0] if affiliate.full_name else '',
            password=raw_password,
        )
    else:
        user.set_password(raw_password)
        user.save(update_fields=['password'])

    affiliate.user = user
    affiliate.status = 'approved'
    affiliate.rejection_reason = ''
    affiliate.approved_at = timezone.now()
    affiliate.save(update_fields=['user', 'status', 'rejection_reason', 'approved_at'])

    plain, html = _approval_email(affiliate, raw_password)
    send_via_resend(to=affiliate.email, subject='Your XERXEZ Academy affiliate application is approved!', html=html, text=plain, from_email=FROM_EMAIL)

    return Response(AffiliateAdminListSerializer(affiliate).data)


@api_view(['POST'])
@permission_classes([IsStaffUser])
def admin_reject_affiliate(request, affiliate_id):
    """POST /api/v1/affiliates/admin/<id>/reject/  body: {reason}"""
    try:
        affiliate = Affiliate.objects.get(id=affiliate_id)
    except Affiliate.DoesNotExist:
        return Response({'error': 'Affiliate not found.'}, status=404)

    affiliate.status = 'rejected'
    affiliate.rejection_reason = request.data.get('reason', '') or ''
    affiliate.save(update_fields=['status', 'rejection_reason'])

    plain, html = _rejection_email(affiliate)
    send_via_resend(to=affiliate.email, subject='Update on your XERXEZ Academy affiliate application', html=html, text=plain, from_email=FROM_EMAIL)

    return Response(AffiliateAdminListSerializer(affiliate).data)


@api_view(['PUT'])
@permission_classes([IsStaffUser])
def admin_set_commission(request, affiliate_id):
    """PUT /api/v1/affiliates/admin/<id>/commission/  body: {commission_rate}"""
    try:
        affiliate = Affiliate.objects.get(id=affiliate_id)
    except Affiliate.DoesNotExist:
        return Response({'error': 'Affiliate not found.'}, status=404)

    rate = request.data.get('commission_rate')
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        return Response({'error': 'commission_rate must be a number.'}, status=400)
    if not (0 <= rate <= 100):
        return Response({'error': 'commission_rate must be between 0 and 100.'}, status=400)

    affiliate.commission_rate = rate
    affiliate.save(update_fields=['commission_rate'])
    return Response(AffiliateAdminListSerializer(affiliate).data)


@api_view(['GET'])
@permission_classes([IsStaffUser])
def admin_list_commissions(request):
    """GET /api/v1/affiliates/admin/commissions/?status=pending"""
    commissions = AffiliateCommission.objects.select_related('affiliate', 'course').all()
    status_filter = request.GET.get('status')
    if status_filter:
        commissions = commissions.filter(status=status_filter)
    return Response(AffiliateCommissionAdminSerializer(commissions, many=True).data)


@api_view(['POST'])
@permission_classes([IsStaffUser])
def admin_mark_commission_paid(request, commission_id):
    """POST /api/v1/affiliates/admin/commissions/<id>/pay/"""
    try:
        commission = AffiliateCommission.objects.get(id=commission_id)
    except AffiliateCommission.DoesNotExist:
        return Response({'error': 'Commission not found.'}, status=404)

    commission.status = 'paid'
    commission.paid_at = timezone.now()
    commission.save(update_fields=['status', 'paid_at'])
    return Response(AffiliateCommissionAdminSerializer(commission).data)
