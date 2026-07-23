"""One-time-safe data fix: ensure Danish and Tanzeem have Employee records
linked to their User accounts. Idempotent via get_or_create(user=...), so it
is safe to leave in the deploy chain."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.hr.models import Employee


class Command(BaseCommand):
    help = "Create Employee records for Danish and Tanzeem if they don't already exist."

    def handle(self, *args, **kwargs):
        User = get_user_model()
        from apps.companies.utils import get_user_company_or_default
        for username, code in (('Danish', 'EMP-ADMIN-DANISH'), ('Tanzeem', 'EMP-ADMIN-TANZEEM')):
            try:
                user = User.objects.get(username__iexact=username)
                employee, created = Employee.objects.get_or_create(
                    user=user,
                    defaults={
                        'code': code,
                        'full_name': username,
                        'email': user.email,
                        # Bug fix: this never set company on create, so every Employee row
                        # this command produced was invisible to any company-scoped query
                        # (Company Admin's employee list, attendance, leave, payroll...) —
                        # see apps.hr.management.commands.backfill_employee_company for the
                        # one-time repair of rows this already created without one.
                        'company': get_user_company_or_default(user),
                    },
                )
                # Backfill on an existing-but-orphaned row too, so re-running this command
                # (it runs on every deploy) also repairs a row created before this fix.
                if not created and employee.company_id is None:
                    company = get_user_company_or_default(user)
                    if company:
                        employee.company = company
                        employee.save(update_fields=['company'])
                status = 'created' if created else 'already exists'
                self.stdout.write(f"{username}: employee {status} -> employee_id: {employee.id}, company_id: {employee.company_id}")
            except Exception as e:
                self.stdout.write(f"Error setting up {username}: {e}")
        self.stdout.write(self.style.SUCCESS("Done!"))
