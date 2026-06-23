from rest_framework import serializers
from .models import Customer, Contact, Lead, Activity


class ContactInlineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ['id', 'name', 'role', 'email', 'phone', 'is_primary']


class CustomerSerializer(serializers.ModelSerializer):
    contacts = ContactInlineSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = '__all__'


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
