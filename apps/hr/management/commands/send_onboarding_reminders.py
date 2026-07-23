"""Emails the assigned person for every onboarding task due tomorrow that isn't completed
yet — one day's advance notice per the spec.

Nothing in this Django deployment schedules jobs on its own — there's no Celery/beat,
APScheduler, or django-crontab installed, and the Procfile runs a single `web` gunicorn
process only. To actually fire this daily, point an external scheduler at it (same approach
as send_daily_attendance_report / check_expiring_documents):

  * Railway Cron Job (recommended) — add a new service in the Railway project, type
    "Cron Job", schedule e.g. `0 8 * * *`, start command:
        python manage.py send_onboarding_reminders

`reminder_sent` prevents re-emailing the same task on every subsequent run.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.core.email import send_via_resend
from apps.hr.models import OnboardingChecklist

FROM_EMAIL = 'onboarding@resend.dev'


class Command(BaseCommand):
    help = "Emails assignees for onboarding tasks due tomorrow that aren't completed."

    def handle(self, *args, **options):
        tomorrow = date.today() + timedelta(days=1)
        qs = OnboardingChecklist.objects.filter(
            due_date=tomorrow, reminder_sent=False,
        ).exclude(status='completed').select_related('employee', 'assigned_to')

        sent = 0
        for task in qs:
            if task.assigned_to and task.assigned_to.email:
                subject = f"Reminder: '{task.task}' due tomorrow — {task.employee.full_name}"
                plain = f"""
The onboarding task "{task.task}" for {task.employee.full_name} is due tomorrow ({task.due_date.strftime('%d %b %Y')}).

— XERXEZ HR
""".strip()
                html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8">
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#F2EFE9;margin:0;padding:0}}
  .wrap{{max-width:560px;margin:32px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 32px rgba(0,0,0,.10)}}
  .hdr{{background:linear-gradient(135deg,#1a1208 0%,#0f0a05 100%);padding:36px 44px;text-align:center}}
  .hdr h1{{color:#C9883A;font-family:Georgia,serif;font-size:24px;margin:0 0 6px}}
  .hdr p{{color:rgba(255,255,255,.42);font-size:13px;margin:0}}
  .body{{padding:36px 44px;font-size:14px;color:#333}}
  .ftr{{background:#F8F7F4;border-top:1px solid #e8e4de;padding:18px 44px;text-align:center;font-size:12px;color:#9b9690}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hdr"><h1>XERXEZ</h1><p>Onboarding Task Reminder</p></div>
  <div class="body">
    <p>The onboarding task <strong>{task.task}</strong> for <strong>{task.employee.full_name}</strong> is due tomorrow, {task.due_date.strftime('%d %b %Y')}.</p>
  </div>
  <div class="ftr">XERXEZ HR &nbsp;·&nbsp; xerxez.com</div>
</div>
</body>
</html>"""
                send_via_resend(to=task.assigned_to.email, subject=subject, html=html, text=plain, from_email=FROM_EMAIL)
            task.reminder_sent = True
            task.save(update_fields=['reminder_sent'])
            sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} onboarding reminder(s) for tasks due {tomorrow.isoformat()}.'))
