import logging

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.email import send_via_resend
from apps.rbac.views import IsSuperAdmin
from .models import PartnerApplication
from .serializers import PartnerApplicationCreateSerializer, PartnerApplicationSerializer

logger = logging.getLogger(__name__)

ADMIN_EMAIL = 'info@xerxez.com'
# TEMPORARY: xerxez.com is not yet verified in Resend — see apps.contact.views for the
# same note; switch to a verified xerxez.com sender once domain verification completes.
FROM_EMAIL = 'onboarding@resend.dev'


def _notification_email(app: PartnerApplication) -> tuple:
    plain = f"""
New Partner Application — XERXEZ Website
=========================================
Name          : {app.full_name}
Email         : {app.email}
Phone         : {app.phone}
LinkedIn      : {app.linkedin_url or '—'}
Location      : {app.city}, {app.country}
Languages     : {', '.join(app.languages)}

Profession    : {app.current_profession}
Experience    : {app.years_experience}
Industries    : {', '.join(app.industries)}
Deals/Month   : {app.estimated_deals}

Network
-------
{app.network_description}

=========================================
Reply directly to {app.email} to respond.
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
      <tr><td>Languages</td>  <td>{', '.join(app.languages)}</td></tr>
      <tr><td>Profession</td> <td>{app.current_profession}</td></tr>
      <tr><td>Experience</td> <td>{app.years_experience}</td></tr>
      <tr><td>Industries</td> <td>{', '.join(app.industries)}</td></tr>
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
        send_via_resend(to=ADMIN_EMAIL, subject=f'New Partner Application — {app.full_name}', html=html, text=plain, from_email=FROM_EMAIL, reply_to=app.email)

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
        if new_status:
            app.status = new_status
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
        if 'notes' in request.data:
            app.notes = request.data.get('notes') or ''
        app.save()
        return Response(PartnerApplicationSerializer(app).data)
