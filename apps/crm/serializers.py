from rest_framework import serializers
from .models import Customer, Contact, Lead, Activity, Deal, CustomerNote


def _gen_code(model, prefix, pad=4):
    n = model.objects.count()
    while True:
        code = f"{prefix}{str(n + 1).zfill(pad)}"
        if not model.objects.filter(code=code).exists():
            return code
        n += 1


class ContactInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'name', 'role', 'email', 'phone', 'is_primary']


class CustomerSerializer(serializers.ModelSerializer):
    code = serializers.CharField(required=False, allow_blank=True)
    contacts = ContactInlineSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = '__all__'
        read_only_fields = ['created_by']

    def create(self, validated_data):
        if not validated_data.get('code'):
            validated_data['code'] = _gen_code(Customer, 'CUST')
        return super().create(validated_data)


class ContactSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = Contact
        fields = '__all__'


class LeadSerializer(serializers.ModelSerializer):
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = Lead
        fields = '__all__'
        read_only_fields = ['created_by']


class ActivitySerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Activity
        fields = '__all__'


class DealSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True, default=None)
    lead_name = serializers.CharField(source='lead.name', read_only=True, default=None)
    assigned_to_username = serializers.CharField(source='assigned_to.username', read_only=True, default=None)
    assigned_to_name = serializers.SerializerMethodField()
    outcome = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = '__all__'

    def get_assigned_to_name(self, obj):
        if not obj.assigned_to:
            return None
        return obj.assigned_to.get_full_name() or obj.assigned_to.username

    def get_outcome(self, obj):
        """Derived, not stored — stage is already the single source of truth for won/lost
        so a separate outcome column would risk drifting out of sync with it."""
        if obj.stage == 'won':
            return 'won'
        if obj.stage == 'lost':
            return 'lost'
        return 'pending'


class DealStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deal
        fields = ['stage']


class CustomerNoteSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default=None)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomerNote
        fields = '__all__'
        read_only_fields = ['customer', 'lead', 'created_by']

    def get_created_by_name(self, obj):
        if not obj.created_by:
            return None
        return obj.created_by.get_full_name() or obj.created_by.username
