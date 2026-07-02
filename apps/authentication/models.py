"""
Authentication models — OTPToken for forgot-password flow
"""
import random
from datetime import timedelta

from django.db import models
from django.utils import timezone


class OTPToken(models.Model):
    email       = models.EmailField(db_index=True)
    otp         = models.CharField(max_length=6)
    reset_token = models.CharField(max_length=64, blank=True, db_index=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    expires_at  = models.DateTimeField()
    is_used     = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"OTPToken({self.email}, used={self.is_used})"

    @classmethod
    def generate_for_email(cls, email: str) -> "OTPToken":
        cls.objects.filter(email=email, is_used=False).update(is_used=True)
        otp_code = f"{random.randint(0, 999999):06d}"
        return cls.objects.create(
            email=email,
            otp=otp_code,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
