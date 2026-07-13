import logging

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from apps.core.email import send_via_resend
from .models import ContactMessage
from .serializers import ContactMessageSerializer

logger = logging.getLogger(__name__)

ADMIN_EMAIL = getattr(settings, 'CONTACT_ADMIN_EMAIL', 'xerxez.in@gmail.com')
# TEMPORARY: xerxez.com is not yet verified in Resend, so sends must use
# Resend's shared onboarding@resend.dev sender until domain verification
# completes. Switch back to CONTACT_FROM_EMAIL (info@xerxez.com) once verified.
FROM_EMAIL = 'onboarding@resend.dev'


def _send_via_resend(*, to, subject, html, text, reply_to=None):
    send_via_resend(to=to, subject=subject, html=html, text=text, from_email=FROM_EMAIL, reply_to=reply_to)


URGENCY_LABELS = {
    'normal':   'Normal (within 24 h)',
    'urgent':   'Urgent (within 4 h)',
    'critical': 'Critical — Immediate',
}


def _notification_email(m: ContactMessage) -> tuple:
    """Build plain-text + HTML notification email for XERXEZ team."""
    urgency_label = URGENCY_LABELS.get(m.urgency, m.urgency)

    plain = f"""
New Contact Form Submission — XERXEZ Website
=============================================
Name     : {m.full_name}
Email    : {m.email}
Phone    : {m.phone or '—'}
Company  : {m.company or '—'}
Service  : {m.service or '—'}
Urgency  : {urgency_label}
Subject  : {m.subject or '—'}

Country       : {m.country or '—'}
Plan Interest : {m.plan_interest or '—'}
Team Size     : {m.team_size or '—'}
Budget        : {m.budget_range or '—'}
Heard Via     : {m.hear_about_us or '—'}

Message
-------
{m.message}

=============================================
Reply directly to {m.email} to respond.
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
  .badge{{display:inline-block;padding:5px 16px;border-radius:100px;font-size:11px;
           font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:26px}}
  .n{{background:#e8f5e9;color:#2e7d32}}
  .u{{background:#fff3e0;color:#e65100}}
  .c{{background:#ffebee;color:#c62828}}
  table{{width:100%;border-collapse:collapse}}
  tr:nth-child(even) td{{background:#fafaf8}}
  td{{padding:12px 14px;font-size:14px;color:#333;vertical-align:top;
      border-bottom:1px solid #f0ede8}}
  td:first-child{{width:32%;font-weight:700;color:#5a5650;font-size:11px;
                  text-transform:uppercase;letter-spacing:.09em}}
  .msg{{background:#fafaf8;border-left:3px solid #C9883A;border-radius:0 8px 8px 0;
        padding:18px 20px;margin-top:26px;font-size:14px;line-height:1.72;
        color:#333;white-space:pre-wrap;word-break:break-word}}
  .cta{{display:inline-block;margin-top:28px;padding:13px 32px;
        background:linear-gradient(145deg,#e8a84e,#C9883A);color:#fff!important;
        font-size:13px;font-weight:700;border-radius:100px;text-decoration:none;
        box-shadow:0 4px 12px rgba(201,136,58,.28)}}
  .ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:18px 44px;
        text-align:center;font-size:12px;color:#9b9690}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <h1>XERXEZ</h1>
    <p>New Contact Form Submission</p>
  </div>
  <div class="body">
    <span class="badge {'n' if m.urgency=='normal' else 'u' if m.urgency=='urgent' else 'c'}">{urgency_label}</span>
    <table>
      <tr><td>Name</td>    <td>{m.full_name}</td></tr>
      <tr><td>Email</td>   <td><a href="mailto:{m.email}" style="color:#C9883A">{m.email}</a></td></tr>
      <tr><td>Phone</td>   <td>{m.phone or '—'}</td></tr>
      <tr><td>Company</td> <td>{m.company or '—'}</td></tr>
      <tr><td>Service</td> <td>{m.service or '—'}</td></tr>
      <tr><td>Subject</td> <td>{m.subject or '—'}</td></tr>
      <tr><td>Country</td> <td>{m.country or '—'}</td></tr>
      <tr><td>Plan Interest</td> <td>{m.plan_interest or '—'}</td></tr>
      <tr><td>Team Size</td> <td>{m.team_size or '—'}</td></tr>
      <tr><td>Budget</td> <td>{m.budget_range or '—'}</td></tr>
      <tr><td>Heard Via</td> <td>{m.hear_about_us or '—'}</td></tr>
    </table>
    <div class="msg">{m.message}</div>
    <div style="text-align:center">
      <a class="cta"
         href="mailto:{m.email}?subject=Re%3A {m.subject or 'Your Enquiry'}">
        Reply to {m.full_name.split()[0]}
      </a>
    </div>
  </div>
  <div class="ftr">Submitted via xerxez.com &nbsp;·&nbsp; XERXEZ Enterprise AI Platform</div>
</div>
</body>
</html>"""
    return plain, html


def _auto_reply_email(m: ContactMessage) -> tuple:
    """Build auto-reply email for the person who submitted the form."""
    first = m.full_name.split()[0] if m.full_name else 'there'

    plain = f"""Hi {first},

Thank you for reaching out to XERXEZ. We've received your enquiry
and our team will get back to you within 24 hours.

Your details
  Subject : {m.subject or 'General Enquiry'}
  Service : {m.service or 'Not specified'}
  Urgency : {URGENCY_LABELS.get(m.urgency, m.urgency)}

For urgent matters, call us at +971 56 786 7451.

Best regards,
The XERXEZ Team
info@xerxez.com | xerxez.com
""".strip()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
  .wrap{{max-width:580px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;
         box-shadow:0 4px 32px rgba(0,0,0,.10)}}
  .hdr{{background:#1a1a1a;padding:36px 40px;text-align:center}}
  .hdr h1{{color:#D4A853;font-family:Georgia,serif;font-size:22px;margin:0 0 4px;letter-spacing:.04em}}
  .hdr p{{color:rgba(255,255,255,.55);font-size:13px;margin:0}}
  .body{{padding:36px 40px;font-size:14px;color:#333;line-height:1.74}}
  .detail-box{{background:#fafaf8;border-radius:10px;border:1px solid #f0ede8;border-left:3px solid #D4A853;
               padding:16px 20px;margin:20px 0;font-size:13px}}
  .detail-box p{{margin:4px 0;color:#5a5650}}
  .detail-box strong{{color:#1a1a1a}}
  .ftr{{background:#1a1a1a;border-top:1px solid #2c2c2c;padding:18px 40px;
        text-align:center;font-size:12px;color:rgba(255,255,255,.45)}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>Enterprise AI &amp; ERP Solutions</p></div>
  <div class="body">
    <p>Hi {first},</p>
    <p>Thank you for reaching out to <strong>XERXEZ</strong>. We've received your enquiry
    and our team will respond within <strong>24 hours</strong>.</p>
    <div class="detail-box">
      <p><strong>Subject:</strong> {m.subject or 'General Enquiry'}</p>
      <p><strong>Service:</strong> {m.service or 'Not specified'}</p>
      <p><strong>Priority:</strong> {URGENCY_LABELS.get(m.urgency, m.urgency)}</p>
    </div>
    <p>For urgent matters, call us at
       <a href="tel:+971567867451" style="color:#D4A853">+971 56 786 7451</a>.</p>
    <p>Best regards,<br><strong>The XERXEZ Team</strong></p>
  </div>
  <div class="ftr">XERXEZ &nbsp;·&nbsp; info@xerxez.com &nbsp;·&nbsp; xerxez.com</div>
</div>
</body>
</html>"""
    return plain, html


class ContactMessageCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """Pre-warm endpoint — keeps Railway awake and confirms API is ready."""
        return Response({"status": "ready", "endpoint": "contact"}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            instance: ContactMessage = serializer.save()
        except Exception as exc:
            logger.error("Contact save failed: %s", exc, exc_info=True)
            return Response(
                {'success': False, 'message': 'Failed to save your message. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # 1. Notify XERXEZ team
        urgency = instance.urgency or 'normal'
        prefix  = {'urgent': '[URGENT] ', 'critical': '[CRITICAL] '}.get(urgency, '')
        subject = f"{prefix}New Enquiry: {instance.subject or instance.full_name}"

        plain, html = _notification_email(instance)
        _send_via_resend(
            to=ADMIN_EMAIL,
            subject=subject,
            html=html,
            text=plain,
            reply_to=instance.email,
        )

        # 2. Auto-reply to enquirer
        ar_plain, ar_html = _auto_reply_email(instance)
        _send_via_resend(
            to=instance.email,
            subject="Thank you for contacting XERXEZ",
            html=ar_html,
            text=ar_plain,
        )

        return Response(
            {
                'success': True,
                'message': 'Your enquiry has been received. We will get back to you within 24 hours.',
            },
            status=status.HTTP_201_CREATED,
        )
