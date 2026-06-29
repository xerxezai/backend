"""
Seed ERP admin accounts.
Run: python manage.py shell < scripts/seed_admins.py
"""

from django.contrib.auth.models import User
from apps.users.models import UserProfile

ACCOUNTS = [
    {"username": "Tanzeem", "password": "Tanzeem1234", "role": "manager", "first_name": "Tanzeem", "is_staff": True},
    {"username": "Danish",  "password": "Danish1234",  "role": "admin",   "first_name": "Danish",  "is_staff": True},
]

for acc in ACCOUNTS:
    user, created = User.objects.get_or_create(username=acc["username"])
    user.set_password(acc["password"])
    user.first_name = acc["first_name"]
    user.is_staff   = acc["is_staff"]
    user.save()

    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = acc["role"]
    profile.save()

    action = "Created" if created else "Updated"
    print(f"✓ {action}: {acc['username']} (role={acc['role']})")

print("\nSeed complete.")
