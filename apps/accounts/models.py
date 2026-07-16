from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models

from apps.core.validators import validate_phone_with_country_code, validate_human_name


class User(AbstractUser):
    ROLE_CHOICES = [('admin', 'Admin'), ('manager', 'Manager')]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    last_login_at = models.DateTimeField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True, default='', validators=[validate_phone_with_country_code])
    bio = models.TextField(blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    # Re-declared (over AbstractUser's defaults) purely to attach validate_human_name —
    # keeps every other constraint (unique username, max_length, etc.) unchanged.
    username = models.CharField(
        max_length=150, unique=True,
        validators=[UnicodeUsernameValidator(), validate_human_name],
        help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.',
        error_messages={'unique': 'A user with that username already exists.'},
    )
    first_name = models.CharField(max_length=150, blank=True, validators=[validate_human_name])
    last_name = models.CharField(max_length=150, blank=True, validators=[validate_human_name])

    def __str__(self):
        return self.username
