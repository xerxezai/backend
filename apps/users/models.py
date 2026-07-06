from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('manager', 'Manager'),
    ]
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='admin')
    last_login_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    # LMA registration sets _skip_profile_signal=True on the instance so the
    # signal never fires a DB query — avoids the FK mismatch between
    # users_userprofile (pointing to auth_user) and accounts.User table.
    if created and not getattr(instance, '_skip_profile_signal', False):
        try:
            with transaction.atomic():
                UserProfile.objects.get_or_create(user=instance)
        except Exception:
            pass
