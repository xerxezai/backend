from rest_framework import serializers
from .models import Shipment, TrackingUpdate


class TrackingUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingUpdate
        fields = '__all__'


class ShipmentSerializer(serializers.ModelSerializer):
    tracking_updates = TrackingUpdateSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = Shipment
        fields = '__all__'
