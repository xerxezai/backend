import logging

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser

from apps.core.email import send_via_resend
from .models import CareerApplication
from .serializers import CareerApplicationSerializer

logger = logging.getLogger(__name__)

ADMIN_EMAIL = 'xerxez.in@gmail.com'
# TEMPORARY: xerxez.com is not yet verified in Resend, so sends must use
# Resend's shared onboarding@resend.dev sender until domain verification
# completes. Switch to CONTACT_FROM_EMAIL (xerxez.in@gmail.com) once verified.
FROM_EMAIL = 'onboarding@resend.dev'

OPEN_POSITIONS = [
    {
        'id': 'full-stack-ai-trainer',
        'title': 'Full Stack AI Trainer',
        'type': 'Full Time',
        'location': 'Remote',
        'description': (
            'Train and develop AI models, create AI course content for our '
            'Academy platform, work with students and instructors.'
        ),
        'requirements': ['Python', 'Machine Learning', 'React', 'Django', 'Content Creation'],
    },
    {
        'id': 'mlops-engineer-mlflow',
        'title': 'MLOps Engineer (MLflow)',
        'type': 'Full Time',
        'location': 'Remote',
        'description': (
            'Build and maintain ML pipelines using MLflow, monitor model '
            'performance, deploy models to production.'
        ),
        'requirements': ['MLflow', 'Docker', 'Kubernetes', 'Python', 'AWS/GCP', 'CI/CD'],
    },
]


def _notification_email(app: CareerApplication) -> tuple:
    plain = f"""
New Career Application — XERXEZ Website
========================================
Name       : {app.name}
Email      : {app.email}
Phone      : {app.phone or '—'}
Position   : {app.position}
Experience : {app.experience or '—'}
LinkedIn   : {app.linkedin or '—'}
Portfolio  : {app.portfolio or '—'}

Cover Letter
------------
{app.cover_letter or '—'}

Resume: {app.resume_file.url if app.resume_file else '—'}

========================================
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
  .badge{{display:inline-block;padding:5px 16px;border-radius:100px;font-size:11px;
           font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:26px;
           background:#fff3e0;color:#e65100}}
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
    <p>New Career Application</p>
  </div>
  <div class="body">
    <span class="badge">{app.position}</span>
    <table>
      <tr><td>Name</td>       <td>{app.name}</td></tr>
      <tr><td>Email</td>      <td><a href="mailto:{app.email}" style="color:#C9883A">{app.email}</a></td></tr>
      <tr><td>Phone</td>      <td>{app.phone or '—'}</td></tr>
      <tr><td>Experience</td> <td>{app.experience or '—'}</td></tr>
      <tr><td>LinkedIn</td>   <td>{app.linkedin or '—'}</td></tr>
      <tr><td>Portfolio</td>  <td>{app.portfolio or '—'}</td></tr>
    </table>
    <div class="msg">{app.cover_letter or 'No cover letter provided.'}</div>
    <div style="text-align:center">
      <a class="cta" href="mailto:{app.email}?subject=Re%3A Your Application for {app.position}">
        Reply to {app.name.split()[0]}
      </a>
    </div>
  </div>
  <div class="ftr">Submitted via xerxez.com/careers &nbsp;·&nbsp; XERXEZ Enterprise AI Platform</div>
</div>
</body>
</html>"""
    return plain, html


class CareerPositionsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'success': True, 'positions': OPEN_POSITIONS}, status=status.HTTP_200_OK)


class CareerApplyView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = CareerApplicationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            instance: CareerApplication = serializer.save()
        except Exception as exc:
            logger.error("Career application save failed: %s", exc, exc_info=True)
            return Response(
                {'success': False, 'message': 'Failed to save your application. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        plain, html = _notification_email(instance)
        send_via_resend(
            to=ADMIN_EMAIL,
            subject=f"New Career Application: {instance.position} — {instance.name}",
            html=html,
            text=plain,
            from_email=FROM_EMAIL,
            reply_to=instance.email,
        )

        return Response(
            {
                'success': True,
                'message': 'Application submitted! We will contact you within 3-5 business days.',
            },
            status=status.HTTP_201_CREATED,
        )
