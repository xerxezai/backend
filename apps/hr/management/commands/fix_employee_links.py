"""One-time-safe data fix: correct the swapped Employee↔User links for
Danish and Tanzeem. Idempotent — re-running always sets the same links, so it
is safe to leave in the deploy chain."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.hr.models import Employee


class Command(BaseCommand):
    help = "Repair swapped employee-user links for Danish and Tanzeem."

    def handle(self, *args, **kwargs):
        User = get_user_model()
        try:
            emp_danish = Employee.objects.get(full_name='Danish')
            emp_tanzeem = Employee.objects.get(full_name='Tanzeem')
            danish = User.objects.get(username__iexact='Danish')
            tanzeem = User.objects.get(username__iexact='Tanzeem')

            # Unlink both first so the one-to-one swap can't collide.
            emp_danish.user = None
            emp_danish.save(update_fields=['user'])
            emp_tanzeem.user = None
            emp_tanzeem.save(update_fields=['user'])

            # Link correctly.
            emp_danish.user = danish
            emp_danish.save(update_fields=['user'])
            emp_tanzeem.user = tanzeem
            emp_tanzeem.save(update_fields=['user'])

            self.stdout.write(f"Danish employee -> user_id: {emp_danish.user_id}")
            self.stdout.write(f"Tanzeem employee -> user_id: {emp_tanzeem.user_id}")
            self.stdout.write(self.style.SUCCESS("Fixed!"))
        except Exception as e:
            self.stdout.write(f"Error: {e}")
