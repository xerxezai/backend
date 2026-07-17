from rest_framework import serializers

from .models import Incident, Inspection, RiskRegister, SafetyChecklist, ChecklistItem, ComplianceRecord


class IncidentSerializer(serializers.ModelSerializer):
    reported_by_name = serializers.CharField(source='reported_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = Incident
        fields = '__all__'
        read_only_fields = ['incident_number']
        extra_kwargs = {'reported_by': {'required': False}}


class InspectionSerializer(serializers.ModelSerializer):
    conducted_by_name = serializers.CharField(source='conducted_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = Inspection
        fields = '__all__'


class RiskRegisterSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True, default=None)

    class Meta:
        model = RiskRegister
        fields = '__all__'
        read_only_fields = ['risk_id', 'risk_score', 'risk_level']


class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = '__all__'
        extra_kwargs = {'checklist': {'required': False}}


class SafetyChecklistSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)
    items = ChecklistItemSerializer(many=True, required=False)

    class Meta:
        model = SafetyChecklist
        fields = '__all__'
        extra_kwargs = {'created_by': {'required': False}}

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        checklist = super().create(validated_data)
        ChecklistItem.objects.bulk_create([ChecklistItem(checklist=checklist, **item) for item in items_data])
        return checklist

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        checklist = super().update(instance, validated_data)
        if items_data is not None:
            checklist.items.all().delete()
            ChecklistItem.objects.bulk_create([ChecklistItem(checklist=checklist, **item) for item in items_data])
        return checklist


class ComplianceRecordSerializer(serializers.ModelSerializer):
    responsible_person_name = serializers.CharField(source='responsible_person.get_full_name', read_only=True, default=None)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = ComplianceRecord
        fields = '__all__'

    def get_is_overdue(self, obj):
        from django.utils import timezone
        return bool(obj.due_date < timezone.now().date() and obj.status != 'compliant')
