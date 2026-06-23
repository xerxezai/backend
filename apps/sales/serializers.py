from rest_framework import serializers
from .models import Quotation, QuotationItem, SalesOrder


class QuotationItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationItem
        fields = '__all__'


class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True, read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = Quotation
        fields = '__all__'


class SalesOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    quotation_number = serializers.CharField(source='quotation.number', read_only=True)

    class Meta:
        model = SalesOrder
        fields = '__all__'
