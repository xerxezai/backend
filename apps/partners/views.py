import logging
from decimal import Decimal

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.email import send_via_resend
from apps.rbac.views import IsSuperAdmin
from .models import PartnerApplication, PartnerLead
from .serializers import PartnerApplicationCreateSerializer, PartnerApplicationSerializer, PartnerLeadSerializer
from .utils import get_partner_from_request

logger = logging.getLogger(__name__)

ADMIN_EMAIL = 'info@xerxez.com'
# TEMPORARY: xerxez.com is not yet verified in Resend — see apps.contact.views for the
# same note; switch to a verified xerxez.com sender once domain verification completes.
FROM_EMAIL = 'onboarding@resend.dev'


def _notification_email(app: PartnerApplication) -> tuple:
    modules_list = '\n'.join(f'- {m}' for m in app.modules) if app.modules else '- (none selected)'
    plain = f"""New partner application received.

Name: {app.full_name}
Email: {app.email}
Phone: {app.phone}
Country: {app.country}
City: {app.city}
Target Market: {app.target_market or '—'}
LinkedIn: {app.linkedin_url or '—'}

Experience:
- Profession: {app.current_profession}
- Years of Experience: {app.years_experience}
- Estimated Deals/Month: {app.estimated_deals}

Modules They Can Sell:
{modules_list}

Network Description:
{app.network_description}

Applied on: {app.created_at.strftime('%Y-%m-%d %H:%M')}

Review this application at:
xerxez.com/erp/partners
""".strip()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
  .wrap{{max-width:640px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;
         box-shadow:0 4px 32px rgba(0,0,0,.10)}}
  .hdr{{background:linear-gradient(135deg,#1a1208 0%,#0f0a05 100%);padding:36px 44px;text-align:center}}
  .hdr h1{{color:#C9883A;font-family:Georgia,serif;font-size:24px;margin:0 0 6px}}
  .hdr p{{color:rgba(255,255,255,.42);font-size:13px;margin:0}}
  .body{{padding:36px 44px}}
  table{{width:100%;border-collapse:collapse}}
  tr:nth-child(even) td{{background:#fafaf8}}
  td{{padding:12px 14px;font-size:14px;color:#333;vertical-align:top;border-bottom:1px solid #f0ede8}}
  td:first-child{{width:32%;font-weight:700;color:#5a5650;font-size:11px;text-transform:uppercase;letter-spacing:.09em}}
  .msg{{background:#fafaf8;border-left:3px solid #C9883A;border-radius:0 8px 8px 0;
        padding:18px 20px;margin-top:26px;font-size:14px;line-height:1.72;color:#333;white-space:pre-wrap;word-break:break-word}}
  .cta{{display:inline-block;margin-top:28px;padding:13px 32px;
        background:linear-gradient(145deg,#e8a84e,#C9883A);color:#fff!important;
        font-size:13px;font-weight:700;border-radius:100px;text-decoration:none;box-shadow:0 4px 12px rgba(201,136,58,.28)}}
  .ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:18px 44px;text-align:center;font-size:12px;color:#9b9690}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>New Partner Application</p></div>
  <div class="body">
    <table>
      <tr><td>Name</td>       <td>{app.full_name}</td></tr>
      <tr><td>Email</td>      <td><a href="mailto:{app.email}" style="color:#C9883A">{app.email}</a></td></tr>
      <tr><td>Phone</td>      <td>{app.phone}</td></tr>
      <tr><td>LinkedIn</td>   <td>{app.linkedin_url or '—'}</td></tr>
      <tr><td>Location</td>   <td>{app.city}, {app.country}</td></tr>
      <tr><td>Target Market</td><td>{app.target_market or '—'}</td></tr>
      <tr><td>Languages</td>  <td>{', '.join(app.languages)}</td></tr>
      <tr><td>Profession</td> <td>{app.current_profession}</td></tr>
      <tr><td>Experience</td> <td>{app.years_experience}</td></tr>
      <tr><td>Modules</td>    <td>{', '.join(app.modules)}</td></tr>
      <tr><td>Deals/Month</td><td>{app.estimated_deals}</td></tr>
    </table>
    <div class="msg">{app.network_description}</div>
    <div style="text-align:center">
      <a class="cta" href="mailto:{app.email}?subject=Re%3A Your XERXEZ Partner Application">Reply to {app.full_name.split()[0]}</a>
    </div>
  </div>
  <div class="ftr">Submitted via xerxez.com/contact &nbsp;·&nbsp; XERXEZ Enterprise AI Platform</div>
</div>
</body>
</html>"""
    return plain, html


def _applicant_confirmation_email(app: PartnerApplication) -> tuple:
    first = app.full_name.split()[0] if app.full_name else 'there'
    plain = f"""Hi {first},

Thank you for applying to become a XERXEZ Partner. We've received your
application and our team will review it within 48 hours.

We'll contact you at {app.email} with next steps.

Best regards,
The XERXEZ Team
info@xerxez.com | xerxez.com
""".strip()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
  .wrap{{max-width:580px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
  .hdr{{background:#1a1a1a;padding:36px 40px;text-align:center}}
  .hdr h1{{color:#D4A853;font-family:Georgia,serif;font-size:22px;margin:0 0 4px;letter-spacing:.04em}}
  .hdr p{{color:rgba(255,255,255,.55);font-size:13px;margin:0}}
  .body{{padding:36px 40px;font-size:14px;color:#333;line-height:1.74}}
  .ftr{{background:#1a1a1a;border-top:1px solid #2c2c2c;padding:18px 40px;text-align:center;font-size:12px;color:rgba(255,255,255,.45)}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>Partner Program</p></div>
  <div class="body">
    <p>Hi {first},</p>
    <p>Thank you for applying to become a <strong>XERXEZ Partner</strong>. We've received
    your application and our team will review it within <strong>48 hours</strong>.</p>
    <p>We'll contact you at <strong>{app.email}</strong> with next steps.</p>
    <p>Best regards,<br><strong>The XERXEZ Team</strong></p>
  </div>
  <div class="ftr">XERXEZ &nbsp;·&nbsp; info@xerxez.com &nbsp;·&nbsp; xerxez.com</div>
</div>
</body>
</html>"""
    return plain, html


def _portal_access_email(app: PartnerApplication) -> tuple:
    first = app.full_name.split()[0] if app.full_name else 'there'
    plain = f"""Hi {first},

Great news — your XERXEZ Partner application has been approved!

You can now log in to the Partner Portal to submit leads and track your
commission:

  Portal: https://www.xerxez.com/partner-portal
  Email:  {app.email}
  Access code: {app.portal_token}

Keep your access code private — it's how the portal confirms it's you.

Best regards,
The XERXEZ Team
info@xerxez.com | xerxez.com
""".strip()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
  .wrap{{max-width:580px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
  .hdr{{background:linear-gradient(135deg,#1a1208 0%,#0f0a05 100%);padding:36px 40px;text-align:center}}
  .hdr h1{{color:#C9883A;font-family:Georgia,serif;font-size:22px;margin:0 0 4px;letter-spacing:.04em}}
  .hdr p{{color:rgba(255,255,255,.55);font-size:13px;margin:0}}
  .body{{padding:36px 40px;font-size:14px;color:#333;line-height:1.74}}
  .creds{{background:#fafaf8;border-radius:10px;border:1px solid #f0ede8;border-left:3px solid #C9883A;
          padding:16px 20px;margin:20px 0;font-size:13px}}
  .creds p{{margin:4px 0;color:#5a5650}}
  .creds strong{{color:#1a1a1a}}
  .cta{{display:inline-block;margin-top:10px;padding:13px 32px;
        background:linear-gradient(145deg,#e8a84e,#C9883A);color:#fff!important;
        font-size:13px;font-weight:700;border-radius:100px;text-decoration:none;box-shadow:0 4px 12px rgba(201,136,58,.28)}}
  .ftr{{background:#1a1a1a;border-top:1px solid #2c2c2c;padding:18px 40px;text-align:center;font-size:12px;color:rgba(255,255,255,.45)}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>Partner Program</p></div>
  <div class="body">
    <p>Hi {first},</p>
    <p>Great news — your <strong>XERXEZ Partner</strong> application has been approved! You can
    now log in to the Partner Portal to submit leads and track your commission.</p>
    <div class="creds">
      <p><strong>Email:</strong> {app.email}</p>
      <p><strong>Access code:</strong> {app.portal_token}</p>
      <p style="color:#9b9690;margin-top:10px">Keep your access code private — it's how the portal confirms it's you.</p>
    </div>
    <div style="text-align:center">
      <a class="cta" href="https://www.xerxez.com/partner-portal">Open Partner Portal</a>
    </div>
    <p>Best regards,<br><strong>The XERXEZ Team</strong></p>
  </div>
  <div class="ftr">XERXEZ &nbsp;·&nbsp; info@xerxez.com &nbsp;·&nbsp; xerxez.com</div>
</div>
</body>
</html>"""
    return plain, html


class PartnerApplyView(APIView):
    """POST /api/v1/partners/apply/ — public, no auth required."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PartnerApplicationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            app: PartnerApplication = serializer.save()
        except Exception as exc:
            logger.error('Partner application save failed: %s', exc, exc_info=True)
            return Response(
                {'success': False, 'message': 'Failed to save your application. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        plain, html = _notification_email(app)
        send_via_resend(to=ADMIN_EMAIL, subject=f'New Partner Application — {app.full_name} from {app.country}', html=html, text=plain, from_email=FROM_EMAIL, reply_to=app.email)

        plain2, html2 = _applicant_confirmation_email(app)
        send_via_resend(to=app.email, subject='XERXEZ Partner Application Received', html=html2, text=plain2, from_email=FROM_EMAIL)

        return Response({'success': True, 'message': 'Application received', 'id': app.id}, status=status.HTTP_201_CREATED)


class PartnerApplicationListView(APIView):
    """GET /api/v1/partners/applications/ — super_admin only. Optional ?status=pending filter."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        qs = PartnerApplication.objects.select_related('reviewed_by').all()
        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        country_param = request.query_params.get('country')
        if country_param:
            qs = qs.filter(country=country_param)
        return Response(PartnerApplicationSerializer(qs, many=True).data)


class PartnerApplicationDetailView(APIView):
    """PUT /api/v1/partners/applications/{id}/ — super_admin only. Updates status/notes."""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsSuperAdmin]

    def get(self, request, pk):
        try:
            app = PartnerApplication.objects.select_related('reviewed_by').get(pk=pk)
        except PartnerApplication.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        return Response(PartnerApplicationSerializer(app).data)

    def put(self, request, pk):
        try:
            app = PartnerApplication.objects.get(pk=pk)
        except PartnerApplication.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        new_status = request.data.get('status')
        if new_status and new_status not in dict(PartnerApplication.STATUS_CHOICES):
            return Response({'error': f'status must be one of: {", ".join(dict(PartnerApplication.STATUS_CHOICES))}'}, status=400)
        was_approved = app.status == 'approved'
        if new_status:
            app.status = new_status
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
        if 'notes' in request.data:
            app.notes = request.data.get('notes') or ''
        app.save()

        # First time approved -> mint the Partner Portal access code and email it.
        # `was_approved` guard keeps a later notes-only edit (or re-saving 'approved')
        # from re-sending this every time.
        if new_status == 'approved' and not was_approved:
            app.ensure_portal_token()
            plain, html = _portal_access_email(app)
            send_via_resend(to=app.email, subject='Your XERXEZ Partner Portal access', html=html, text=plain, from_email=FROM_EMAIL)

        return Response(PartnerApplicationSerializer(app).data)


class PartnerLoginView(APIView):
    """POST /api/v1/partners/login/ — {email, token} -> partner profile, or 401."""
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip()
        token = (request.data.get('token') or '').strip()
        if not email or not token:
            return Response({'error': 'Email and access code are required.'}, status=400)
        try:
            app = PartnerApplication.objects.get(email__iexact=email, portal_token=token, status='approved')
        except PartnerApplication.DoesNotExist:
            return Response({'error': 'Invalid email or access code.'}, status=401)
        return Response({'id': app.id, 'full_name': app.full_name, 'email': app.email})


class PartnerMeView(APIView):
    """GET /api/v1/partners/me/ — the logged-in partner's profile + lead/commission stats."""
    permission_classes = [AllowAny]  # auth is the X-Partner-* headers, checked below

    def get(self, request):
        partner = get_partner_from_request(request)
        if not partner:
            return Response({'error': 'Not authenticated'}, status=401)

        leads = partner.leads.all()
        won_leads = leads.filter(status='won')
        total_commission = sum((l.commission_amount for l in won_leads), Decimal('0'))
        pending_commission = sum((l.commission_amount for l in leads.exclude(status__in=['won', 'lost'])), Decimal('0'))

        return Response({
            'id': partner.id, 'full_name': partner.full_name, 'email': partner.email,
            'total_leads': leads.count(),
            'won_leads': won_leads.count(),
            'total_commission': str(total_commission),
            'pending_commission': str(pending_commission),
        })


class PartnerLeadListCreateView(APIView):
    """GET/POST /api/v1/partners/leads/ — the logged-in partner's own leads."""
    permission_classes = [AllowAny]  # auth is the X-Partner-* headers, checked below

    def get(self, request):
        partner = get_partner_from_request(request)
        if not partner:
            return Response({'error': 'Not authenticated'}, status=401)
        return Response(PartnerLeadSerializer(partner.leads.all(), many=True).data)

    def post(self, request):
        partner = get_partner_from_request(request)
        if not partner:
            return Response({'error': 'Not authenticated'}, status=401)
        serializer = PartnerLeadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        lead = serializer.save(partner=partner)
        return Response(PartnerLeadSerializer(lead).data, status=201)
