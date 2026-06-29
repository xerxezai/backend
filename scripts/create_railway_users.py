import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xerxez_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from apps.users.models import UserProfile
User = get_user_model()

ACCOUNTS = [
    {'username': 'Danish', 'password': 'Danish1234', 'role': 'admin', 'first_name': 'Danish', 'is_staff': True},
    {'username': 'Tanzeem', 'password': 'Tanzeem1234', 'role': 'manager', 'first_name': 'Tanzeem', 'is_staff': True},
]

for acc in ACCOUNTS:
    user, created = User.objects.get_or_create(username=acc['username'])
    user.set_password(acc['password'])
    user.first_name = acc['first_name']
    user.is_staff = acc['is_staff']
    user.role = acc['role']
    user.is_active = True
    user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.role = acc['role']
    profile.save()
    print(('Created' if created else 'Updated') + ': ' + acc['username'])
