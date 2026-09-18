from rest_framework import serializers

from apps.core.serializers import SanitizedModelSerializer
from .models import CareerApplication


class CareerApplicationSerializer(SanitizedModelSerializer):
    class Meta:
        model = CareerApplication
        fields = '__all__'
        read_only_fields = ['id', 'applied_at', 'status']
