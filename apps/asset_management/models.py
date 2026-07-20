"""Asset Management: equipment/vehicle/tool register with maintenance and depreciation tracking."""
from django.conf import settings
from django.db import models


def next_number(model, field, prefix):
    """Next sequential '<PREFIX>-NNN' value for a model field, based on the highest existing one."""
    last = model.objects.order_by('-id').first()
    n = 1
    val = getattr(last, field, '') if last else ''
    if val and val.startswith(prefix + '-') and val[len(prefix) + 1:].isdigit():
        n = int(val[len(prefix) + 1:]) + 1
    return f'{prefix}-{n:03d}'


class Asset(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    CATEGORY = [
        ('machinery', 'Machinery'),
        ('vehicle', 'Vehicle'),
        ('equipment', 'Equipment'),
        ('tool', 'Tool'),
        ('it_equipment', 'IT Equipment'),
        ('safety', 'Safety'),
        ('other', 'Other'),
    ]
    STATUS = [
        ('active', 'Active'),
        ('under_maintenance', 'Under Maintenance'),
        ('retired', 'Retired'),
        ('disposed', 'Disposed'),
        ('lost', 'Lost'),
    ]
    name = models.CharField(max_length=255)
    asset_code = models.CharField(max_length=20, unique=True, help_text='e.g. AST-001')
    category = models.CharField(max_length=20, choices=CATEGORY)
    status = models.CharField(max_length=20, choices=STATUS, default='active')
    location = models.CharField(max_length=255)
    department = models.CharField(max_length=120, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_assets')
    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=14, decimal_places=2)
    current_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    depreciation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text='Annual % depreciation')
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance = models.DateField(null=True, blank=True)
    maintenance_interval_days = models.IntegerField(default=90)
    qr_code = models.CharField(max_length=255, blank=True, help_text='QR code payload (data/URL) encoded into qr_code_image')
    qr_code_image = models.ImageField(upload_to='assets/qr/', null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.asset_code} — {self.name}'


class MaintenanceRecord(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    TYPE = [
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('emergency', 'Emergency'),
        ('inspection', 'Inspection'),
    ]
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='maintenance_records')
    maintenance_type = models.CharField(max_length=20, choices=TYPE)
    performed_by = models.CharField(max_length=150)
    vendor = models.CharField(max_length=150, blank=True)
    date = models.DateField()
    cost = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField()
    parts_replaced = models.TextField(blank=True)
    next_due = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='logged_maintenance')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f'{self.asset.asset_code} — {self.get_maintenance_type_display()} ({self.date})'


class AssetDepreciation(models.Model):
    company = models.ForeignKey(
        'companies.Company', on_delete=models.CASCADE, null=True, blank=True,
        related_name='%(app_label)s_%(class)s',
    )
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='depreciation_entries')
    year = models.IntegerField()
    opening_value = models.DecimalField(max_digits=14, decimal_places=2)
    depreciation_amount = models.DecimalField(max_digits=14, decimal_places=2)
    closing_value = models.DecimalField(max_digits=14, decimal_places=2)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year']
        unique_together = ('asset', 'year')

    def __str__(self):
        return f'{self.asset.asset_code} — {self.year}'
