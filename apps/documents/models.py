from django.conf import settings
from django.db import models


class Document(models.Model):
    CATEGORY_CHOICES = [
        ('engineering_drawing', 'Engineering Drawing'),
        ('contract',            'Contract'),
        ('invoice',             'Invoice'),
        ('hr_document',         'HR Document'),
        ('safety_qhse',         'Safety / QHSE'),
        ('procurement',         'Procurement'),
        ('project_report',      'Project Report'),
        ('other',               'Other'),
    ]
    STATUS_CHOICES = [
        ('draft',        'Draft'),
        ('under_review', 'Under Review'),
        ('approved',     'Approved'),
        ('rejected',     'Rejected'),
    ]

    title       = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category    = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    file        = models.FileField(upload_to='documents/')
    version     = models.CharField(max_length=20, default='v1')
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_documents')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.version})'


class DocumentVersion(models.Model):
    document       = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='versions')
    version_number = models.CharField(max_length=20)
    file           = models.FileField(upload_to='document_versions/')
    uploaded_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='document_versions')
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.document.title} — {self.version_number}'
