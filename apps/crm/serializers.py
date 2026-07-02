from rest_framework import serializers
from .models import Customer, Contact, Lead, Activity


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


class ActivitySerializer(serializers.ModelSerializer):
    user_username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Activity
        fields = '__all__'
