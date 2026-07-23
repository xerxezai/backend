import logging
from decimal import Decimal

from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.email import send_via_resend
from apps.rbac.views import IsSuperAdmin
from .models import Partner, PartnerDeal, COMMISSION_RATES, generate_partner_code
from .serializers import PartnerApplySerializer, PartnerSerializer, PartnerDealSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

ADMIN_EMAIL = 'xerxez.in@gmail.com'
# TEMPORARY: xerxez.com is not yet verified in Resend — see apps.contact.views for the
# same note; switch to a verified xerxez.com sender once domain verification completes.
FROM_EMAIL = 'onboarding@resend.dev'


class IsApprovedPartner(IsAuthenticated):
    """Gates the partner-facing portal endpoints — the request must be a JWT-authenticated
    Django user that has a linked, approved Partner profile (set at approval time)."""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        partner = getattr(request.user, 'partner', None)
        return partner is not None and partner.status == 'approved'


# ── emails ──────────────────────────────────────────────────────────────────

def _application_notification_email(p: Partner) -> tuple:
    modules_list = '\n'.join(f'- {m}' for m in p.modules) if p.modules else '- (none selected)'
    plain = f"""New partner application received.

Name: {p.full_name}
Email: {p.email}
Phone: {p.phone}
Country: {p.country}
City: {p.city}
Target Market: {p.target_market or '—'}
LinkedIn: {p.linkedin_url or '—'}

Experience:
- Profession: {p.current_profession}
- Years of Experience: {p.years_experience}
- Estimated Deals/Month: {p.estimated_deals}

Packages They Applied For:
{modules_list}

Network Description:
{p.network_description}

Review this application at:
xerxez.com/erp/partners
""".strip()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
.wrap{{max-width:640px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
.hdr{{background:linear-gradient(135deg,#1a1208 0%,#0f0a05 100%);padding:36px 44px;text-align:center}}
.hdr h1{{color:#C9883A;font-family:Georgia,serif;font-size:24px;margin:0 0 6px}}
.hdr p{{color:rgba(255,255,255,.42);font-size:13px;margin:0}}
.body{{padding:36px 44px}}
table{{width:100%;border-collapse:collapse}}
tr:nth-child(even) td{{background:#fafaf8}}
td{{padding:12px 14px;font-size:14px;color:#333;vertical-align:top;border-bottom:1px solid #f0ede8}}
td:first-child{{width:32%;font-weight:700;color:#5a5650;font-size:11px;text-transform:uppercase;letter-spacing:.09em}}
.msg{{background:#fafaf8;border-left:3px solid #C9883A;border-radius:0 8px 8px 0;padding:18px 20px;margin-top:26px;font-size:14px;line-height:1.72;color:#333;white-space:pre-wrap;word-break:break-word}}
.ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:18px 44px;text-align:center;font-size:12px;color:#9b9690}}
</style></head><body><div class="wrap">
<div class="hdr"><h1>XERXEZ</h1><p>New Partner Application</p></div>
<div class="body"><table>
<tr><td>Name</td><td>{p.full_name}</td></tr>
<tr><td>Email</td><td><a href="mailto:{p.email}" style="color:#C9883A">{p.email}</a></td></tr>
<tr><td>Phone</td><td>{p.phone}</td></tr>
<tr><td>Location</td><td>{p.city}, {p.country}</td></tr>
<tr><td>Target Market</td><td>{p.target_market or '—'}</td></tr>
<tr><td>Languages</td><td>{', '.join(p.languages)}</td></tr>
<tr><td>Profession</td><td>{p.current_profession}</td></tr>
<tr><td>Experience</td><td>{p.years_experience}</td></tr>
<tr><td>Packages</td><td>{', '.join(p.modules)}</td></tr>
<tr><td>Deals/Month</td><td>{p.estimated_deals}</td></tr>
</table><div class="msg">{p.network_description}</div></div>
<div class="ftr">Submitted via xerxez.com/contact &nbsp;·&nbsp; XERXEZ Enterprise AI Platform</div>
</div></body></html>"""
    return plain, html


def _applicant_confirmation_email(p: Partner) -> tuple:
    first = p.full_name.split()[0] if p.full_name else 'there'
    plain = f"""Hi {first},

Thank you for applying to become a XERXEZ Partner. We've received your
application and our team will review it within 48 hours.

We'll contact you at {p.email} with next steps.

Best regards,
The XERXEZ Team
xerxez.in@gmail.com | xerxez.com
""".strip()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
.wrap{{max-width:580px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
.hdr{{background:#1a1a1a;padding:36px 40px;text-align:center}}
.hdr h1{{color:#D4A853;font-family:Georgia,serif;font-size:22px;margin:0 0 4px;letter-spacing:.04em}}
.hdr p{{color:rgba(255,255,255,.55);font-size:13px;margin:0}}
.body{{padding:36px 40px;font-size:14px;color:#333;line-height:1.74}}
.ftr{{background:#1a1a1a;border-top:1px solid #2c2c2c;padding:18px 40px;text-align:center;font-size:12px;color:rgba(255,255,255,.45)}}
</style></head><body><div class="wrap">
<div class="hdr"><h1>XERXEZ</h1><p>Partner Program</p></div>
<div class="body"><p>Hi {first},</p>
<p>Thank you for applying to become a <strong>XERXEZ Partner</strong>. We've received
your application and our team will review it within <strong>48 hours</strong>.</p>
<p>We'll contact you at <strong>{p.email}</strong> with next steps.</p>
<p>Best regards,<br><strong>The XERXEZ Team</strong></p></div>
<div class="ftr">XERXEZ &nbsp;·&nbsp; xerxez.in@gmail.com &nbsp;·&nbsp; xerxez.com</div>
</div></body></html>"""
    return plain, html


def _welcome_email(p: Partner, password: str) -> tuple:
    plain = f"""Congratulations {p.full_name.split()[0] if p.full_name else ''}!

Your partner application has been approved. You can now login to your
partner portal.

Partner Code: {p.partner_code}
Login: xerxez.com/partner
Email: {p.email}
Password: {password}

Commission Structure:
Basic Package (1-2 modules): 10%
Professional Package (3-5 modules): 20%
Enterprise Package (all modules): 30%
- Paid within 30 days of client payment
- No cap on earnings
- Payment in AED, USD, or INR

Please change your password after first login.

How to Get Started:
1. Login at xerxez.com/partner
2. Complete your profile
3. Explore training materials
4. Submit your first client deal
5. Track your commissions

Need Help?
Email: info@xerxez.com
WhatsApp: +971 56 786 7451
Partner Portal: xerxez.com/partner

Welcome to the XERXEZ Partner family!
XERXEZ Team
""".strip()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
.wrap{{max-width:580px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
.hdr{{background:linear-gradient(135deg,#1a1208 0%,#0f0a05 100%);padding:36px 40px;text-align:center}}
.hdr h1{{color:#C9883A;font-family:Georgia,serif;font-size:22px;margin:0 0 4px;letter-spacing:.04em}}
.hdr p{{color:rgba(255,255,255,.55);font-size:13px;margin:0}}
.body{{padding:36px 40px;font-size:14px;color:#333;line-height:1.74}}
.creds{{background:#fafaf8;border-radius:10px;border:1px solid #f0ede8;border-left:3px solid #C9883A;padding:16px 20px;margin:20px 0;font-size:13px}}
.creds p{{margin:4px 0;color:#5a5650}}
.creds strong{{color:#1a1a1a}}
.tiers{{background:#fafaf8;border-radius:10px;padding:14px 20px;margin:16px 0;font-size:13px;color:#5a5650}}
.tiers ul{{margin:8px 0 0;padding-left:20px}}
.steps{{background:#fafaf8;border-radius:10px;padding:16px 20px;margin:16px 0;font-size:13px;color:#5a5650}}
.steps strong{{color:#1a1a1a;display:block;margin-bottom:6px}}
.steps ol{{margin:0;padding-left:20px}}
.cta{{display:inline-block;margin-top:10px;padding:13px 32px;background:linear-gradient(145deg,#e8a84e,#C9883A);color:#fff!important;font-size:13px;font-weight:700;border-radius:100px;text-decoration:none;box-shadow:0 4px 12px rgba(201,136,58,.28)}}
.ftr{{background:#1a1a1a;border-top:1px solid #2c2c2c;padding:18px 40px;text-align:center;font-size:12px;color:rgba(255,255,255,.45)}}
</style></head><body><div class="wrap">
<div class="hdr"><h1>XERXEZ</h1><p>Partner Program</p></div>
<div class="body">
<p>Congratulations {p.full_name.split()[0] if p.full_name else ''}!</p>
<p>Your partner application has been approved. You can now login to your <strong>partner portal</strong>.</p>
<div class="creds">
<p><strong>Partner Code:</strong> {p.partner_code}</p>
<p><strong>Login:</strong> xerxez.com/partner</p>
<p><strong>Email:</strong> {p.email}</p>
<p><strong>Password:</strong> {password}</p>
</div>
<div class="tiers">
<strong>Commission Structure</strong><br>
Basic Package (1-2 modules): 10%<br>Professional Package (3-5 modules): 20%<br>Enterprise Package (all modules): 30%
<ul><li>Paid within 30 days of client payment</li><li>No cap on earnings</li><li>Payment in AED, USD, or INR</li></ul>
</div>
<p style="color:#9b9690">Please change your password after first login.</p>
<div class="steps">
<strong>How to Get Started</strong>
<ol><li>Login at xerxez.com/partner</li><li>Complete your profile</li><li>Explore training materials</li>
<li>Submit your first client deal</li><li>Track your commissions</li></ol>
</div>
<div style="text-align:center"><a class="cta" href="https://www.xerxez.com/partner">Open Partner Portal</a></div>
<p style="margin-top:24px">Need help? Email <a href="mailto:info@xerxez.com" style="color:#C9883A">info@xerxez.com</a>
or WhatsApp +971 56 786 7451.</p>
<p>Welcome to the XERXEZ Partner family!<br><strong>The XERXEZ Team</strong></p></div>
<div class="ftr">XERXEZ &nbsp;·&nbsp; info@xerxez.com &nbsp;·&nbsp; xerxez.com</div>
</div></body></html>"""
    return plain, html


def _deal_notification_email(d: PartnerDeal) -> tuple:
    plain = f"""New deal submitted by {d.partner.full_name} ({d.partner.partner_code}).

Deal Number: {d.deal_number}
Client Company: {d.client_company}
Contact Person: {d.client_contact_person}
Phone: {d.client_phone}
Email: {d.client_email}
Country: {d.client_country}

Package: {d.get_package_display()}
Number of Employees: {d.num_employees}
Current System: {d.get_current_system_display()}

Notes:
{d.notes or '—'}

Review this deal at:
xerxez.com/erp/partners
""".strip()
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
.wrap{{max-width:640px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
.hdr{{background:linear-gradient(135deg,#1a1208 0%,#0f0a05 100%);padding:36px 44px;text-align:center}}
.hdr h1{{color:#C9883A;font-family:Georgia,serif;font-size:24px;margin:0 0 6px}}
.hdr p{{color:rgba(255,255,255,.42);font-size:13px;margin:0}}
.body{{padding:36px 44px}}
table{{width:100%;border-collapse:collapse}}
tr:nth-child(even) td{{background:#fafaf8}}
td{{padding:12px 14px;font-size:14px;color:#333;vertical-align:top;border-bottom:1px solid #f0ede8}}
td:first-child{{width:34%;font-weight:700;color:#5a5650;font-size:11px;text-transform:uppercase;letter-spacing:.09em}}
.msg{{background:#fafaf8;border-left:3px solid #C9883A;border-radius:0 8px 8px 0;padding:18px 20px;margin-top:26px;font-size:14px;line-height:1.72;color:#333;white-space:pre-wrap;word-break:break-word}}
.ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:18px 44px;text-align:center;font-size:12px;color:#9b9690}}
</style></head><body><div class="wrap">
<div class="hdr"><h1>XERXEZ</h1><p>New Deal Submitted</p></div>
<div class="body"><table>
<tr><td>Partner</td><td>{d.partner.full_name} ({d.partner.partner_code})</td></tr>
<tr><td>Deal Number</td><td>{d.deal_number}</td></tr>
<tr><td>Client Company</td><td>{d.client_company}</td></tr>
<tr><td>Contact Person</td><td>{d.client_contact_person}</td></tr>
<tr><td>Phone</td><td>{d.client_phone}</td></tr>
<tr><td>Email</td><td><a href="mailto:{d.client_email}" style="color:#C9883A">{d.client_email}</a></td></tr>
<tr><td>Country</td><td>{d.client_country}</td></tr>
<tr><td>Package</td><td>{d.get_package_display()}</td></tr>
<tr><td>Employees</td><td>{d.num_employees}</td></tr>
<tr><td>Current System</td><td>{d.get_current_system_display()}</td></tr>
</table><div class="msg">{d.notes or 'No additional notes.'}</div></div>
<div class="ftr">Submitted via xerxez.com/partner &nbsp;·&nbsp; XERXEZ Enterprise AI Platform</div>
</div></body></html>"""
    return plain, html


# ── public application ───────────────────────────────────────────────────────

class PartnerApplyView(APIView):
    """POST /api/v1/partners/apply/ — public, no auth required."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PartnerApplySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            partner: Partner = serializer.save()
        except Exception as exc:
            logger.error('Partner application save failed: %s', exc, exc_info=True)
            return Response({'success': False, 'message': 'Failed to save your application. Please try again later.'}, status=500)

        plain, html = _application_notification_email(partner)
        send_via_resend(to=ADMIN_EMAIL, subject=f'New Partner Application — {partner.full_name} from {partner.country}', html=html, text=plain, from_email=FROM_EMAIL, reply_to=partner.email)
        plain2, html2 = _applicant_confirmation_email(partner)
        send_via_resend(to=partner.email, subject='XERXEZ Partner Application Received', html=html2, text=plain2, from_email=FROM_EMAIL)

        return Response({'success': True, 'message': 'Application received', 'id': partner.id}, status=status.HTTP_201_CREATED)


# ── partner auth (JWT, real Django user) ─────────────────────────────────────

class PartnerLoginView(APIView):
    """POST /api/v1/partners/login/ — {email, password} -> JWT access/refresh + partner profile."""
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip()
        password = request.data.get('password') or ''
        if not email or not password:
            return Response({'error': 'Email and password are required.'}, status=400)

        # Django's ModelBackend authenticates by USERNAME_FIELD ('username'), not email —
        # this form collects email, so resolve it to the account's username first.
        user_obj = User.objects.filter(email__iexact=email).first()
        if not user_obj:
            return Response({'error': 'Invalid email or password.'}, status=401)

        user = authenticate(request, username=user_obj.username, password=password)
        if not user:
            return Response({'error': 'Invalid email or password.'}, status=401)

        partner = getattr(user, 'partner', None)
        if not partner:
            return Response({'error': 'This account is not a partner account.'}, status=403)
        if partner.status != 'approved':
            return Response({'error': f'Your partner account is {partner.get_status_display().lower()}.'}, status=403)

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'partner': PartnerSerializer(partner).data,
        })


class PartnerMeView(APIView):
    """GET /api/v1/partners/me/ — the logged-in partner's profile."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsApprovedPartner]

    def get(self, request):
        return Response(PartnerSerializer(request.user.partner).data)


class PartnerDashboardView(APIView):
    """GET /api/v1/partners/dashboard/ — stat cards for the partner dashboard."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsApprovedPartner]

    def get(self, request):
        partner = request.user.partner
        deals = partner.deals.all()
        pending = deals.exclude(status__in=['won', 'lost', 'cancelled']).count()
        won = deals.filter(status='won').count()
        lost = deals.filter(status='lost').count()
        pending_commission = partner.total_commission_earned - partner.total_commission_paid

        return Response({
            'total_deals': partner.total_deals,
            'pending_deals': pending,
            'won_deals': won,
            'lost_deals': lost,
            'total_commission_earned': str(partner.total_commission_earned),
            'total_commission_pending': str(pending_commission),
            'total_commission_paid': str(partner.total_commission_paid),
            'partner_code': partner.partner_code,
            'commission_tier': partner.commission_tier,
        })


class PartnerDealListCreateView(APIView):
    """GET/POST /api/v1/partners/deals/ — the logged-in partner's own deals."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsApprovedPartner]

    def get(self, request):
        return Response(PartnerDealSerializer(request.user.partner.deals.all(), many=True).data)

    def post(self, request):
        serializer = PartnerDealSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        deal = serializer.save(partner=request.user.partner)
        request.user.partner.sync_stats()

        plain, html = _deal_notification_email(deal)
        send_via_resend(
            to=ADMIN_EMAIL,
            subject=f'New Deal Submitted — {deal.partner.full_name} — {deal.client_company}',
            html=html, text=plain, from_email=FROM_EMAIL, reply_to=deal.client_email,
        )
        return Response(PartnerDealSerializer(deal).data, status=201)


class PartnerDealDetailView(APIView):
    """GET /api/v1/partners/deals/{id}/ — a single deal, scoped to the logged-in partner."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsApprovedPartner]

    def get(self, request, pk):
        try:
            deal = request.user.partner.deals.get(pk=pk)
        except PartnerDeal.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        return Response(PartnerDealSerializer(deal).data)


class PartnerMaterialsView(APIView):
    """GET /api/v1/partners/materials/ — static training materials list."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsApprovedPartner]

    def get(self, request):
        return Response([
            {'id': 1, 'title': 'Product Overview', 'description': 'Complete guide to XERXEZ ERP modules and features.', 'action': 'view', 'url': '/ai-erp'},
            {'id': 2, 'title': 'Sales Script', 'description': 'Step by step guide on how to approach and pitch to clients.', 'action': 'download', 'url': None},
            {'id': 3, 'title': 'Module Descriptions', 'description': 'Detailed description of each ERP module to explain to clients.', 'action': 'view', 'url': '/ai-erp'},
        ])


# ── admin (super_admin only) ─────────────────────────────────────────────────

class AdminPartnerListView(APIView):
    """GET /api/v1/partners/admin/partners/ — all partners, optional ?status= filter."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = Partner.objects.select_related('approved_by').all()
        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return Response(PartnerSerializer(qs, many=True).data)


class AdminPartnerDetailView(APIView):
    """GET/PUT /api/v1/partners/admin/partners/{id}/ — generic edit (notes, commission_tier, suspend)."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request, pk):
        try:
            partner = Partner.objects.select_related('approved_by').get(pk=pk)
        except Partner.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        return Response(PartnerSerializer(partner).data)

    def put(self, request, pk):
        try:
            partner = Partner.objects.get(pk=pk)
        except Partner.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        new_status = request.data.get('status')
        if new_status and new_status not in dict(Partner.STATUS_CHOICES):
            return Response({'error': f'status must be one of: {", ".join(dict(Partner.STATUS_CHOICES))}'}, status=400)
        # A partner can only reach 'approved' here as a *reactivation* (they already have a
        # partner_code/user from a prior approval) — first-time approval must go through
        # AdminPartnerApproveView so the login account + welcome email actually get created.
        if new_status == 'approved' and not partner.partner_code:
            return Response({'error': 'Use the Approve action to approve a partner for the first time.'}, status=400)
        if new_status:
            partner.status = new_status
        if 'notes' in request.data:
            partner.notes = request.data.get('notes') or ''
        if 'commission_tier' in request.data and request.data['commission_tier'] in dict(Partner.COMMISSION_TIER_CHOICES):
            partner.commission_tier = request.data['commission_tier']
        partner.save()
        return Response(PartnerSerializer(partner).data)

    def delete(self, request, pk):
        try:
            partner = Partner.objects.get(pk=pk)
        except Partner.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        user = partner.user
        partner.delete()
        if user:
            user.delete()
        return Response(status=204)


class AdminPartnerApproveView(APIView):
    """PUT /api/v1/partners/admin/partners/{id}/approve/ — create Django user, mint partner
    code, email login credentials."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def put(self, request, pk):
        try:
            partner = Partner.objects.get(pk=pk)
        except Partner.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        if partner.status == 'approved':
            return Response({'error': 'This partner is already approved.'}, status=400)
        if User.objects.filter(username=partner.email).exists():
            return Response({'error': f'A user account already exists for {partner.email}. Resolve manually before approving.'}, status=400)

        password = request.data.get('password')
        if not password:
            return Response({'error': 'Password is required.'}, status=400)
        if len(password) < 8:
            return Response({'error': 'Password must be at least 8 characters.'}, status=400)

        user = User.objects.create_user(
            username=partner.email, email=partner.email,
            first_name=partner.full_name.split()[0] if partner.full_name else '',
            password=password,
        )

        partner.user = user
        partner.status = 'approved'
        partner.partner_code = generate_partner_code()
        partner.approved_by = request.user
        partner.approved_at = timezone.now()
        partner.save()

        plain, html = _welcome_email(partner, password)
        send_via_resend(to=partner.email, subject='Welcome to XERXEZ Partner Program!', html=html, text=plain, from_email=FROM_EMAIL)

        return Response(PartnerSerializer(partner).data)


class AdminPartnerRejectView(APIView):
    """PUT /api/v1/partners/admin/partners/{id}/reject/"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def put(self, request, pk):
        try:
            partner = Partner.objects.get(pk=pk)
        except Partner.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        partner.status = 'rejected'
        partner.approved_by = request.user
        partner.approved_at = timezone.now()
        if 'notes' in request.data:
            partner.notes = request.data.get('notes') or ''
        partner.save()
        return Response(PartnerSerializer(partner).data)


class AdminDealListView(APIView):
    """GET /api/v1/partners/admin/deals/ — all deals, filter by ?status=&partner=&package="""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = PartnerDeal.objects.select_related('partner').all()
        if request.query_params.get('status'):
            qs = qs.filter(status=request.query_params['status'])
        if request.query_params.get('partner'):
            qs = qs.filter(partner_id=request.query_params['partner'])
        if request.query_params.get('package'):
            qs = qs.filter(package=request.query_params['package'])
        return Response(PartnerDealSerializer(qs, many=True).data)


class AdminDealDetailView(APIView):
    """PUT /api/v1/partners/admin/deals/{id}/ — update status, pricing, commission."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def put(self, request, pk):
        try:
            deal = PartnerDeal.objects.select_related('partner').get(pk=pk)
        except PartnerDeal.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        data = request.data
        if 'status' in data:
            if data['status'] not in dict(PartnerDeal.STATUS_CHOICES):
                return Response({'error': f'status must be one of: {", ".join(dict(PartnerDeal.STATUS_CHOICES))}'}, status=400)
            deal.status = data['status']
        if 'deal_value' in data:
            deal.deal_value = data['deal_value']
        if 'commission_rate' in data:
            deal.commission_rate = data['commission_rate']
        if 'commission_amount' in data:
            deal.commission_amount = data['commission_amount']
        elif deal.deal_value and deal.commission_rate:
            deal.commission_amount = (Decimal(str(deal.deal_value)) * Decimal(str(deal.commission_rate)) / Decimal('100')).quantize(Decimal('0.01'))
        if 'commission_status' in data:
            if data['commission_status'] not in dict(PartnerDeal.COMMISSION_STATUS_CHOICES):
                return Response({'error': f'commission_status must be one of: {", ".join(dict(PartnerDeal.COMMISSION_STATUS_CHOICES))}'}, status=400)
            deal.commission_status = data['commission_status']
            if data['commission_status'] == 'paid' and not deal.commission_paid_at:
                deal.commission_paid_at = timezone.now()
        deal.reviewed_by = request.user
        deal.save()
        deal.partner.sync_stats()

        return Response(PartnerDealSerializer(deal).data)

    def delete(self, request, pk):
        try:
            deal = PartnerDeal.objects.select_related('partner').get(pk=pk)
        except PartnerDeal.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        partner = deal.partner
        deal.delete()
        partner.sync_stats()
        return Response(status=204)
