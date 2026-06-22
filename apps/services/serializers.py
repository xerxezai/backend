from rest_framework import serializers
from .models import Service


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = [
            'id', 'name', 'slug', 'short_description', 'description',
            'icon', 'image', 'price', 'order',
            'is_published', 'publish_date', 'created_at', 'updated_at',
        ]