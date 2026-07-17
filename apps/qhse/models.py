"""QHSE: Quality, Health, Safety & Environment — Incidents, Inspections, Risk Register,
Safety Checklists and Compliance tracking for EPC site operations."""
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


class Incident(models.Model):
    TYPE = [
        ('near_miss', 'Near Miss'),
        ('first_aid', 'First Aid'),
        ('medical_treatment', 'Medical Treatment'),
        ('lost_time', 'Lost Time'),
        ('fatality', 'Fatality'),
        ('environmental', 'Environmental'),
        ('property_damage', 'Property Damage'),
        ('security', 'Security'),
    ]
    SEVERITY = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    STATUS = [
        ('open', 'Open'),
        ('investigating', 'Investigating'),
        ('action_required', 'Action Required'),
        ('closed', 'Closed'),
        ('resolved', 'Resolved'),
    ]
    incident_number = models.CharField(max_length=20, unique=True, help_text='e.g. INC-001')
    title = models.CharField(max_length=255)
    incident_type = models.CharField(max_length=20, choices=TYPE)
    severity = models.CharField(max_length=10, choices=SEVERITY)
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=255)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='reported_incidents')
    injured_person = models.CharField(max_length=150, blank=True)
    description = models.TextField()
    immediate_action = models.TextField(blank=True)
    root_cause = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='open')
    closed_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.incident_number} — {self.title}'

    def save(self, *args, **kwargs):
        if not self.incident_number:
            self.incident_number = next_number(Incident, 'incident_number', 'INC')
        super().save(*args, **kwargs)


class Inspection(models.Model):
    TYPE = [
        ('safety', 'Safety'),
        ('quality', 'Quality'),
        ('environmental', 'Environmental'),
        ('process', 'Process'),
        ('fire', 'Fire'),
        ('electrical', 'Electrical'),
        ('scaffold', 'Scaffold'),
    ]
    STATUS = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    title = models.CharField(max_length=255)
    inspection_type = models.CharField(max_length=20, choices=TYPE)
    scheduled_date = models.DateField()
    completed_date = models.DateField(null=True, blank=True)
    conducted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='conducted_inspections')
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='scheduled')
    findings = models.TextField(blank=True)
    corrective_actions = models.TextField(blank=True)
    score = models.IntegerField(null=True, blank=True, help_text='0-100')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_date', '-id']

    def __str__(self):
        return self.title


def risk_level_for_score(score: int) -> str:
    if score >= 16:
        return 'critical'
    if score >= 10:
        return 'high'
    if score >= 5:
        return 'medium'
    return 'low'


class RiskRegister(models.Model):
    CATEGORY = [
        ('safety', 'Safety'),
        ('environmental', 'Environmental'),
        ('quality', 'Quality'),
        ('operational', 'Operational'),
        ('financial', 'Financial'),
        ('legal', 'Legal'),
    ]
    SCALE = [(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')]
    LEVEL = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    STATUS = [
        ('open', 'Open'),
        ('mitigated', 'Mitigated'),
        ('closed', 'Closed'),
        ('accepted', 'Accepted'),
    ]
    risk_id = models.CharField(max_length=20, unique=True, help_text='e.g. RISK-001')
    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY)
    likelihood = models.IntegerField(choices=SCALE)
    consequence = models.IntegerField(choices=SCALE)
    risk_score = models.IntegerField(editable=False, help_text='Auto-calculated: likelihood x consequence')
    risk_level = models.CharField(max_length=10, choices=LEVEL, editable=False)
    mitigation = models.TextField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='owned_risks')
    status = models.CharField(max_length=10, choices=STATUS, default='open')
    review_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-risk_score', '-id']

    def __str__(self):
        return f'{self.risk_id} — {self.title}'

    def save(self, *args, **kwargs):
        if not self.risk_id:
            self.risk_id = next_number(RiskRegister, 'risk_id', 'RISK')
        self.risk_score = (self.likelihood or 0) * (self.consequence or 0)
        self.risk_level = risk_level_for_score(self.risk_score)
        super().save(*args, **kwargs)


class SafetyChecklist(models.Model):
    TYPE = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('pre_task', 'Pre-Task'),
        ('toolbox_talk', 'Toolbox Talk'),
        ('permit_to_work', 'Permit to Work'),
    ]
    STATUS = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    title = models.CharField(max_length=255)
    checklist_type = models.CharField(max_length=20, choices=TYPE)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_checklists')
    date = models.DateField()
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f'{self.title} ({self.date})'


class ChecklistItem(models.Model):
    ANSWER = [
        ('yes', 'Yes'),
        ('no', 'No'),
        ('na', 'N/A'),
    ]
    checklist = models.ForeignKey(SafetyChecklist, on_delete=models.CASCADE, related_name='items')
    question = models.CharField(max_length=255)
    answer = models.CharField(max_length=3, choices=ANSWER)
    remarks = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f'{self.question} — {self.answer}'


class ComplianceRecord(models.Model):
    TYPE = [
        ('legal', 'Legal'),
        ('regulatory', 'Regulatory'),
        ('iso', 'ISO'),
        ('company_policy', 'Company Policy'),
        ('client_requirement', 'Client Requirement'),
    ]
    STATUS = [
        ('compliant', 'Compliant'),
        ('non_compliant', 'Non-Compliant'),
        ('partially_compliant', 'Partially Compliant'),
        ('under_review', 'Under Review'),
    ]
    title = models.CharField(max_length=255)
    compliance_type = models.CharField(max_length=20, choices=TYPE)
    description = models.TextField()
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS, default='under_review')
    responsible_person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='compliance_items')
    evidence = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_date']

    def __str__(self):
        return self.title
