"""
Idempotent setup for LMA instructor accounts.
Safe to run multiple times — never deletes existing data.

Usage:
    python manage.py setup_lma_instructors

Run this on Railway via:
    railway run python manage.py setup_lma_instructors
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

INSTRUCTORS = [
    {'username': 'Danish',  'email': 'danish@xerxez.com'},
    {'username': 'Tanzeem', 'email': 'tanzeem@xerxez.com'},
]


class Command(BaseCommand):
    help = "Ensure Danish and Tanzeem have correct emails and LMA instructor access"

    def handle(self, *args, **kwargs):
        from apps.lma.models import LMAProfile

        User = get_user_model()

        for data in INSTRUCTORS:
            username = data['username']
            email    = data['email']

            # Match by username (case-insensitive) or email
            user = (
                User.objects.filter(username__iexact=username).first() or
                User.objects.filter(email__iexact=email).first()
            )

            if not user:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [SKIP] No account found for {username} / {email}. "
                        f"Register via /lma/register first, then re-run."
                    )
                )
                continue

            with transaction.atomic():
                # Ensure email is set correctly
                if user.email.lower() != email:
                    user.email = email
                    user.save(update_fields=['email'])

                # Ensure is_active and is_staff
                if not user.is_active or not user.is_staff:
                    user.is_active = True
                    user.is_staff  = True
                    user.save(update_fields=['is_active', 'is_staff'])

                # Create or update LMAProfile with instructor access
                profile, created = LMAProfile.objects.get_or_create(user=user)
                profile.lma_role           = 'both'
                profile.can_access_student = True
                profile.can_access_instructor = True
                profile.save()

            tag = '[CREATED]' if created else '[UPDATED]'
            self.stdout.write(self.style.SUCCESS(
                f"  {tag} {user.username} | email={user.email} | instructor=True"
            ))

        self.stdout.write(self.style.SUCCESS("\nDone. LMA instructor accounts are ready."))
