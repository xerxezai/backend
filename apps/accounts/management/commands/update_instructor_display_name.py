"""
Updates the display name (first_name/last_name only) of the user account
currently shown as "Tanzeem" in instructor-facing UI, so the LMA frontend's
dynamically-rendered instructor name reads "Expert Instructor" instead.
Leaves username, password, email, role and every other field untouched.
Run with:  python manage.py update_instructor_display_name
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Update the first_name/last_name of the user with first_name='Tanzeem' to 'Expert'/'Instructor'."

    def handle(self, *args, **kwargs):
        User = get_user_model()

        try:
            user = User.objects.get(first_name="Tanzeem")
        except User.DoesNotExist:
            raise CommandError("No user found with first_name='Tanzeem'.")
        except User.MultipleObjectsReturned:
            raise CommandError("Multiple users found with first_name='Tanzeem' — resolve manually before running this command.")

        old_name = f"{user.first_name} {user.last_name}".strip()
        user.first_name = "Expert"
        user.last_name = "Instructor"
        user.save(update_fields=["first_name", "last_name"])
        new_name = f"{user.first_name} {user.last_name}".strip()

        self.stdout.write(self.style.SUCCESS(
            f"Updated display name: \"{old_name}\" -> \"{new_name}\" (user id={user.id}, username={user.username})"
        ))
