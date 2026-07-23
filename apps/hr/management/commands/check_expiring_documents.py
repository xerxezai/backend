"""Emails xerxez.in@gmail.com for every employee document that has drifted into its
30-day-until-expiry window since the last time this ran.

Nothing in this Django deployment schedules jobs on its own — there's no Celery/beat,
APScheduler, or django-crontab installed, and the Procfile runs a single `web` gunicorn
process only. To actually fire this daily, point an external scheduler at it (same approach
as send_daily_attendance_report):

  * Railway Cron Job (recommended) — add a new service in the Railway project, type
    "Cron Job", schedule e.g. `0 8 * * *`, start command:
        python manage.py check_expiring_documents

Uploading or editing a document whose expiry is already within 30 days sends this same
alert immediately (see apps.hr.views._maybe_notify_document_expiring) — this command only
covers the other case: a document that ages into the 30-day window purely because time
passed, with nobody re-saving the row to trigger the inline check.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.hr.models import EmployeeDocument
from apps.hr.views import _send_document_expiring_email


class Command(BaseCommand):
    help = "Emails xerxez.in@gmail.com for documents newly within 30 days of expiry."

    def handle(self, *args, **options):
        today = date.today()
        window_end = today + timedelta(days=30)
        qs = EmployeeDocument.objects.filter(
            expiry_date__gte=today, expiry_date__lte=window_end, expiry_notified=False,
        ).select_related('employee')

        sent = 0
        for document in qs:
            _send_document_expiring_email(document)
            document.expiry_notified = True
            document.save(update_fields=['expiry_notified'])
            sent += 1

        self.stdout.write(self.style.SUCCESS(f'Sent {sent} expiring-document alert(s) for {today.isoformat()}.'))
