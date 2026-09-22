from django.db import models


class PartnerCourse(models.Model):
    """An external course (Linux Foundation, Coursera, Udemy, AWS, …) shown
    on the XERXEZ website — enrollment happens on the partner's own site via
    an affiliate link, not through the LMA. Any partner works: this model
    has no hardcoded assumptions about who the partner is, just free-text
    partner_name/logo/website fields set by whoever adds the course."""

    LEVEL_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
    ]

    # Partner info
    partner_name = models.CharField(max_length=255)
    partner_logo = models.ImageField(upload_to='partner_courses/logos/', blank=True, null=True)
    partner_website = models.URLField()

    # Course info
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=100)
    level = models.CharField(max_length=50, choices=LEVEL_CHOICES, default='Beginner')
    duration = models.CharField(max_length=50, blank=True, default='')
    price = models.CharField(max_length=50, blank=True, default='')
    thumbnail = models.ImageField(upload_to='partner_courses/thumbnails/', blank=True, null=True)

    # Affiliate tracking — a placeholder link works fine before real
    # affiliate codes exist; swapping this field later is all that's needed.
    affiliate_link = models.URLField()
    affiliate_code = models.CharField(max_length=100, blank=True, default='')

    # Settings
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', '-is_featured', '-created_at']

    def __str__(self):
        return f"{self.partner_name} — {self.title}"
