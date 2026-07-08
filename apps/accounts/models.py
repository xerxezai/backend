from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [('admin', 'Admin'), ('manager', 'Manager')]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    last_login_at = models.DateTimeField(null=True, blank=True)
    phone = models.CharField(max_length=30, blank=True, default='')
    bio = models.TextField(blank=True, default='')
    department = models.CharField(max_length=100, blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    def __str__(self):
        return self.username
