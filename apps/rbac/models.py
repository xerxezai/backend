"""RBAC: per-module role assignment and data-level access filtering for the 8 core ERP
modules (Dashboard/CRM/Sales/Procurement/Logistics/Accounting/MLM/HR). The EPC modules
(Document Management, Project Management, Asset Management, QHSE) are intentionally never
gated here — see apps.rbac.utils.has_module_access."""
from django.conf import settings
from django.db import models


class Module(models.Model):
    MODULE_CHOICES = [
        ('dashboard', 'Dashboard'),
        ('crm', 'CRM'),
        ('sales', 'Sales'),
        ('procurement', 'Procurement'),
        ('logistics', 'Logistics'),
        ('accounting', 'Accounting'),
        ('mlm', 'MLM'),
        ('hr', 'HR Overview'),
    ]
    name = models.CharField(max_length=50, unique=True, choices=MODULE_CHOICES)
    display_name = models.CharField(max_length=100)
    icon = models.CharField(max_length=100, default='fas fa-circle')
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.display_name


class UserModuleAccess(models.Model):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('module_admin', 'Module Admin'),
        ('regular_user', 'Regular User'),
        ('read_only', 'Read Only'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='module_access')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='user_access')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='regular_user')
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='granted_access')
    granted_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user', 'module']

    def __str__(self):
        return f'{self.user} - {self.module}'


class AccessRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='access_requests')
    module = models.ForeignKey(Module, on_delete=models.CASCADE)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user} - {self.module}'
