from django.core.validators import FileExtensionValidator
from django.db import models

from apps.core.validators import validate_phone_with_country_code


class CareerApplication(models.Model):
    STATUS_CHOICES = [
        ('new',         'New'),
        ('reviewing',   'Reviewing'),
        ('shortlisted', 'Shortlisted'),
        ('rejected',    'Rejected'),
    ]

    name          = models.CharField(max_length=200)
    email         = models.EmailField()
    phone         = models.CharField(max_length=50, blank=True, validators=[validate_phone_with_country_code])
    position      = models.CharField(max_length=200)
    experience    = models.CharField(max_length=50, blank=True)
    linkedin      = models.URLField(blank=True)
    portfolio     = models.URLField(blank=True)
    cover_letter  = models.TextField(blank=True)
    resume_file   = models.FileField(
        upload_to='careers/resumes/',
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])],
    )
    applied_at    = models.DateTimeField(auto_now_add=True)
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')

    class Meta:
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.name} — {self.position}"
