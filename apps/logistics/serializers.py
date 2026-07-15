from rest_framework import serializers
from .models import Shipment, TrackingUpdate, Delivery, Warehouse, next_number


class TrackingUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TrackingUpdate
        fields = '__all__'


class ShipmentSerializer(serializers.ModelSerializer):
    tracking_updates = TrackingUpdateSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    sales_order_number = serializers.CharField(source='sales_order.number', read_only=True, default=None)
    origin_warehouse_name = serializers.CharField(source='origin_warehouse.name', read_only=True, default=None)

    class Meta:
        model = Shipment
        fields = '__all__'
        read_only_fields = ['shipment_number']

    def create(self, validated_data):
        validated_data['shipment_number'] = next_number(Shipment, 'shipment_number', 'SHP')
        return super().create(validated_data)


class DeliverySerializer(serializers.ModelSerializer):
    shipment_tracking_number = serializers.CharField(source='shipment.shipment_number', read_only=True)

    class Meta:
        model = Delivery
        fields = '__all__'


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = '__all__'
