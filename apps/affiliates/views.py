import logging
import re
import secrets
import string

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.shortcuts import redirect
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response

from apps.core.email import send_via_resend, render_v2_email, v2_detail_table
from apps.lma.models import Course

from .models import Affiliate, AffiliateClick, AffiliateCommission
from .serializers import (
    AffiliateApplySerializer, AffiliateSerializer, AffiliateAdminListSerializer,
    AffiliateAdminDetailSerializer,
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
    """Gates the affiliate-facing portal endpoints. is_staff/is_superuser
    accounts are let in even without their own Affiliate row, so admins can
    open the affiliate dashboard/links/commissions views too — each view
    below serves them a platform-wide aggregate instead of a personal one."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        if user.is_staff or user.is_superuser:
            return True
        affiliate = getattr(user, 'affiliate', None)
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
    rows = [
        ('Name', a.full_name), ('Email', a.email), ('Code', a.affiliate_code),
        ('Company', a.company_name or '—'), ('Website', a.website or '—'),
        ('Promotion Method', a.promotion_method), ('Audience Size', a.audience_size),
    ]
    html = render_v2_email(title='New Affiliate Application', body_html=v2_detail_table(rows))
    return plain, html


def _applicant_confirmation_email(a: Affiliate) -> tuple:
    first = a.full_name.split()[0] if a.full_name else 'there'
    plain = f"""Hi {first},

Thanks for applying to the XERXEZ Academy affiliate program. We've received
your application (code: {a.affiliate_code}) and will review it shortly.

— The XERXEZ Team
""".strip()
    body_html = (
        f'<p>Hi {first},</p>'
        f'<p>Thanks for applying to the XERXEZ Academy affiliate program. We\'ve received your application '
        f'(code: <strong>{a.affiliate_code}</strong>) and will review it shortly.</p>'
    )
    html = render_v2_email(title='Application received', body_html=body_html)
    return plain, html


def _approval_email(a: Affiliate) -> tuple:
    """No password here — the affiliate set their own password at apply
    time (see `apply()` below), so approval just activates that account."""
    first = a.full_name.split()[0] if a.full_name else ''
    plain = f"""Congratulations {first}!

Your affiliate application has been approved! Login at xerxez.com/lma/login

Affiliate Code: {a.affiliate_code}
Commission Rate: {a.commission_rate}%
Email: {a.email}

Your affiliate link format:
xerxez.com/lma/courses/:id?ref={a.affiliate_code}

— The XERXEZ Team
""".strip()
    body_html = (
        f'<p>Congratulations {first}! Your affiliate application has been approved! '
        f'Login with the email and password you used to apply.</p>'
        + v2_detail_table([
            ('Affiliate Code', a.affiliate_code),
            ('Commission Rate', f'{a.commission_rate}%'),
            ('Email', a.email),
        ])
        + f'<p>Your affiliate link format: <code>xerxez.com/lma/courses/:id?ref={a.affiliate_code}</code></p>'
    )
    html = render_v2_email(
        title="You're approved!", body_html=body_html,
        cta_label='Log In', cta_url='https://xerxez.com/lma/login',
    )
    return plain, html


def _rejection_email(a: Affiliate) -> tuple:
    first = a.full_name.split()[0] if a.full_name else 'there'
    reason_line = f"\n\nReason: {a.rejection_reason}" if a.rejection_reason else ''
    plain = f"""Hi {first},

Thanks for your interest in the XERXEZ Academy affiliate program. After
review, we're not able to approve your application at this time.{reason_line}

— The XERXEZ Team
""".strip()
    body_html = (
        f'<p>Hi {first},</p>'
        f"<p>Thanks for your interest in the XERXEZ Academy affiliate program. After review, we're not "
        f"able to approve your application at this time.{('<br><br>Reason: ' + a.rejection_reason) if a.rejection_reason else ''}</p>"
    )
    html = render_v2_email(title='Application update', body_html=body_html)
    return plain, html


# ── public application ───────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def check_code_availability(request):
    """GET /api/v1/affiliates/check-code/?code=XXX — real-time availability
    check for the apply form's Affiliate Code field, before the applicant
    submits. Same format rule as AffiliateApplySerializer.validate_affiliate_code."""
    code = (request.GET.get('code') or '').strip().upper()
    if not re.match(r'^[A-Z0-9]{3,20}$', code):
        return Response({'available': False, 'code': code, 'error': 'Use 3-20 letters/numbers only.'})
    taken = Affiliate.objects.filter(affiliate_code=code).exists()
    return Response({
        'available': not taken,
        'code': code,
        'error': None if not taken else 'This code is already taken.',
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def apply(request):
    """POST /api/v1/affiliates/apply/ — the applicant sets their own login
    password here; a Django User is created immediately but inactive
    (is_active=False) until an admin approves the application, so no
    temporary/generated password ever needs to be emailed later."""
    password = request.data.get('password', '')
    confirm_password = request.data.get('confirm_password', '')
    if not password or len(password) < 8:
        return Response({'password': ['Password must be at least 8 characters.']}, status=400)
    if password != confirm_password:
        return Response({'confirm_password': ["Passwords don't match."]}, status=400)

    serializer = AffiliateApplySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    email = serializer.validated_data['email']
    if User.objects.filter(email=email).exists():
        return Response({'email': ['An account with this email already exists. Please log in instead.']}, status=400)

    with transaction.atomic():
        affiliate = serializer.save()
        user = User(
            username=email, email=email,
            first_name=affiliate.full_name.split()[0] if affiliate.full_name else '',
            last_name=' '.join(affiliate.full_name.split()[1:]) if len(affiliate.full_name.split()) > 1 else '',
            is_active=False,
        )
        user.set_password(password)
        user._skip_profile_signal = True
        user.save()
        affiliate.user = user
        affiliate.save(update_fields=['user'])

    # Both emails go through send_via_resend (SMTP-based — see apps/core/email.py),
    # which already wraps the send in try/except and just logs on failure.
    # Failures here never block the response: the Affiliate row is already saved above.
    plain, html = _application_notification_email(affiliate)
    send_via_resend(to=ADMIN_EMAIL, subject=f'New affiliate application from {affiliate.full_name}', html=html, text=plain, from_email=FROM_EMAIL)
    plain2, html2 = _applicant_confirmation_email(affiliate)
    send_via_resend(to=affiliate.email, subject='We received your affiliate application', html=html2, text=plain2, from_email=FROM_EMAIL)

    return Response(AffiliateSerializer(affiliate).data, status=201)


# ── affiliate portal ─────────────────────────────────────────────────────

def _admin_affiliate_view(user):
    """Synthetic 'affiliate' payload for a staff/superuser account with no
    Affiliate row of its own — lets them open the affiliate dashboard and
    see platform-wide totals instead of a personal profile."""
    totals = Affiliate.objects.aggregate(
        clicks=Sum('total_clicks'), conversions=Sum('total_conversions'), earnings=Sum('total_earnings'),
    )
    return {
        'id': 0, 'full_name': user.get_full_name() or user.username, 'email': user.email,
        'affiliate_code': 'ALL AFFILIATES', 'company_name': '', 'website': '',
        'promotion_method': '', 'audience_size': '', 'status': 'admin', 'rejection_reason': '',
        'commission_rate': 0, 'total_clicks': totals['clicks'] or 0,
        'total_conversions': totals['conversions'] or 0, 'total_earnings': totals['earnings'] or 0,
        'bank_details': {}, 'created_at': None, 'approved_at': None, 'is_admin_view': True,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def affiliate_dashboard(request):
    """GET /api/v1/affiliates/dashboard/ — is_staff/is_superuser accounts
    with no Affiliate row of their own see a platform-wide aggregate
    (every affiliate's totals + the 10 most recent commissions across all
    affiliates) instead of a 404."""
    user = request.user
    affiliate = getattr(user, 'affiliate', None)

    if not affiliate:
        if user.is_staff or user.is_superuser:
            pending_earnings = AffiliateCommission.objects.filter(
                status__in=['pending', 'approved']
            ).aggregate(total=Sum('commission_amount'))['total'] or 0
            recent_commissions = AffiliateCommission.objects.select_related('affiliate', 'course').order_by('-created_at')[:10]
            return Response({
                'affiliate': _admin_affiliate_view(user),
                'pending_earnings': pending_earnings,
                'recent_commissions': AffiliateCommissionAdminSerializer(recent_commissions, many=True).data,
            })
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
    affiliate's code, so the frontend can build /lma/courses/:id?ref=CODE.
    Admins with no Affiliate row see the same course list with a
    placeholder code (they're browsing, not generating real referral links)."""
    affiliate = getattr(request.user, 'affiliate', None)
    courses = Course.objects.filter(status='published').order_by('title')
    return Response({
        'affiliate_code': affiliate.affiliate_code if affiliate else 'ADMIN',
        'courses': [{'id': c.id, 'title': c.title, 'price': c.price} for c in courses],
    })


@api_view(['GET'])
@permission_classes([IsApprovedAffiliate])
def affiliate_commissions(request):
    """GET /api/v1/affiliates/commissions/ — admins with no Affiliate row
    see every affiliate's commissions instead of their own (they have none)."""
    affiliate = getattr(request.user, 'affiliate', None)
    if not affiliate:
        commissions = AffiliateCommission.objects.select_related('affiliate', 'course').all()
        return Response(AffiliateCommissionAdminSerializer(commissions, many=True).data)
    commissions = affiliate.commissions.all()
    return Response(AffiliateCommissionSerializer(commissions, many=True).data)


@api_view(['PUT'])
@permission_classes([IsApprovedAffiliate])
def affiliate_bank_details(request):
    """PUT /api/v1/affiliates/bank-details/ — affiliate updates their own
    payout details. Admins viewing the platform-wide aggregate (no Affiliate
    row of their own) have nothing to save here."""
    affiliate = getattr(request.user, 'affiliate', None)
    if not affiliate:
        return Response({'error': 'No affiliate profile for this account.'}, status=400)
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


@api_view(['GET'])
@permission_classes([IsStaffUser])
def admin_affiliate_detail(request, affiliate_id):
    """GET /api/v1/affiliates/admin/<id>/detail/ — full profile plus every
    course sold through this affiliate (student, amount, commission, date),
    the same commissions grouped for a per-course click/conversion
    breakdown. Powers the admin "View" panel."""
    try:
        affiliate = Affiliate.objects.get(id=affiliate_id)
    except Affiliate.DoesNotExist:
        return Response({'error': 'Affiliate not found.'}, status=404)

    commissions = (
        AffiliateCommission.objects.filter(affiliate=affiliate)
        .select_related('course', 'enrollment__student')
        .order_by('-created_at')
    )
    clicks_by_course = (
        AffiliateClick.objects.filter(affiliate=affiliate, course__isnull=False)
        .values('course_id', 'course__title')
        .annotate(clicks=Count('id'), conversions=Count('id', filter=Q(converted=True)))
        .order_by('-clicks')
    )

    return Response({
        'affiliate': AffiliateAdminDetailSerializer(affiliate).data,
        'commissions': AffiliateCommissionAdminSerializer(commissions, many=True).data,
        'clicks_by_course': [
            {'course_id': c['course_id'], 'course_title': c['course__title'], 'clicks': c['clicks'], 'conversions': c['conversions']}
            for c in clicks_by_course
        ],
    })


@api_view(['DELETE'])
@permission_classes([IsStaffUser])
def admin_delete_affiliate(request, affiliate_id):
    """DELETE /api/v1/affiliates/admin/<id>/delete/ — permanently removes the
    affiliate application/account row. Cascades to its clicks and commission
    records (AffiliateCommission.affiliate is on_delete=CASCADE) — the
    frontend confirms with the admin before calling this since it's
    destructive. Does not touch the linked login User; use reject (which
    deactivates it) if the account itself should also be disabled."""
    try:
        affiliate = Affiliate.objects.get(id=affiliate_id)
    except Affiliate.DoesNotExist:
        return Response({'error': 'Affiliate not found.'}, status=404)
    affiliate.delete()
    return Response(status=204)


@api_view(['POST'])
@permission_classes([IsStaffUser])
def admin_approve_affiliate(request, affiliate_id):
    """POST /api/v1/affiliates/admin/<id>/approve/ — the affiliate already
    has a login account (created inactive at apply time, with the password
    they chose themselves), so approval just activates it. No password is
    generated or emailed here."""
    try:
        affiliate = Affiliate.objects.get(id=affiliate_id)
    except Affiliate.DoesNotExist:
        return Response({'error': 'Affiliate not found.'}, status=404)

    if affiliate.user:
        affiliate.user.is_active = True
        affiliate.user.save(update_fields=['is_active'])
    else:
        # Legacy fallback — an application created before apply() started
        # creating the User up front, or one whose account is otherwise
        # missing. Generates a temporary password since there's no
        # applicant-chosen one to reuse.
        alphabet = string.ascii_letters + string.digits + '!@#$'
        raw_password = ''.join(secrets.choice(alphabet) for _ in range(14))
        user = User.objects.filter(email=affiliate.email).first()
        if not user:
            user = User(
                username=affiliate.email, email=affiliate.email,
                first_name=affiliate.full_name.split()[0] if affiliate.full_name else '',
            )
            user._skip_profile_signal = True
        user.set_password(raw_password)
        user.is_active = True
        user.save()
        affiliate.user = user

    affiliate.status = 'approved'
    affiliate.rejection_reason = ''
    affiliate.approved_at = timezone.now()
    affiliate.save(update_fields=['user', 'status', 'rejection_reason', 'approved_at'])

    plain, html = _approval_email(affiliate)
    send_via_resend(to=affiliate.email, subject='Your XERXEZ Academy affiliate application is approved!', html=html, text=plain, from_email=FROM_EMAIL)

    return Response(AffiliateAdminListSerializer(affiliate).data)


@api_view(['POST'])
@permission_classes([IsStaffUser])
def admin_reject_affiliate(request, affiliate_id):
    """POST /api/v1/affiliates/admin/<id>/reject/  body: {reason}
    Deactivates (not deletes) the login account created at apply time, so a
    later re-approval can simply reactivate it rather than recreate it."""
    try:
        affiliate = Affiliate.objects.get(id=affiliate_id)
    except Affiliate.DoesNotExist:
        return Response({'error': 'Affiliate not found.'}, status=404)

    if affiliate.user:
        affiliate.user.is_active = False
        affiliate.user.save(update_fields=['is_active'])

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
    commissions = AffiliateCommission.objects.select_related('affiliate', 'course', 'enrollment__student').all()
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
