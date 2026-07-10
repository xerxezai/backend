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
        for username, code in (('Danish', 'EMP-ADMIN-DANISH'), ('Tanzeem', 'EMP-ADMIN-TANZEEM')):
            try:
                user = User.objects.get(username__iexact=username)
                employee, created = Employee.objects.get_or_create(
                    user=user,
                    defaults={
                        'code': code,
                        'full_name': username,
                        'email': user.email,
                    },
                )
                status = 'created' if created else 'already exists'
                self.stdout.write(f"{username}: employee {status} -> employee_id: {employee.id}")
            except Exception as e:
                self.stdout.write(f"Error setting up {username}: {e}")
        self.stdout.write(self.style.SUCCESS("Done!"))
