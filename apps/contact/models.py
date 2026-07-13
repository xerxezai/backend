from django.db import models


class ContactMessage(models.Model):
    URGENCY_CHOICES = [
        ('normal',   'Normal'),
        ('urgent',   'Urgent'),
        ('critical', 'Critical'),
    ]

    full_name  = models.CharField(max_length=200)
    email      = models.EmailField()
    phone      = models.CharField(max_length=50, blank=True)
    company    = models.CharField(max_length=200, blank=True)
    service    = models.CharField(max_length=200, blank=True)
    urgency    = models.CharField(max_length=20, choices=URGENCY_CHOICES, default='normal')
    subject    = models.CharField(max_length=300, blank=True)
    message    = models.TextField()

    # ERP enquiry qualification fields
    country         = models.CharField(max_length=50, blank=True)
    plan_interest   = models.CharField(max_length=50, blank=True)
    team_size       = models.CharField(max_length=20, blank=True)
    budget_currency = models.CharField(max_length=10, blank=True)
    budget_range    = models.CharField(max_length=50, blank=True)
    hear_about_us   = models.CharField(max_length=50, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    is_read    = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} — {self.subject or 'No subject'}"
