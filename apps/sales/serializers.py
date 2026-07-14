from rest_framework import serializers
from .models import Quotation, QuotationItem, SalesOrder, SalesOrderItem


class QuotationItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = QuotationItem
        fields = ['id', 'quotation', 'product', 'product_name', 'description', 'quantity', 'unit_price', 'line_total']
        read_only_fields = ['id', 'line_total']
        extra_kwargs = {'quotation': {'required': False}}


class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True, required=False)
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = Quotation
        fields = '__all__'
        read_only_fields = ['subtotal', 'tax', 'total']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        quotation = Quotation.objects.create(**validated_data)
        for item in items_data:
            QuotationItem.objects.create(quotation=quotation, **item)
        quotation.recalc()
        quotation.save()
        return quotation

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                QuotationItem.objects.create(quotation=instance, **item)
        instance.recalc()
        instance.save()
        return instance


class SalesOrderItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = SalesOrderItem
        fields = ['id', 'order', 'product', 'product_name', 'description', 'quantity', 'unit_price', 'line_total']
        read_only_fields = ['id', 'line_total']
        extra_kwargs = {'order': {'required': False}}


class SalesOrderSerializer(serializers.ModelSerializer):
    items = SalesOrderItemSerializer(many=True, required=False)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    quotation_number = serializers.CharField(source='quotation.number', read_only=True, default=None)
    salesperson_name = serializers.SerializerMethodField()
    distributor_name = serializers.SerializerMethodField()
    invoice_number = serializers.SerializerMethodField()

    class Meta:
        model = SalesOrder
        fields = '__all__'

    def create(self, validated_data):
        items_data = validated_data.pop('items', None)
        order = SalesOrder.objects.create(**validated_data)
        if items_data:
            for item in items_data:
                SalesOrderItem.objects.create(order=order, **item)
            order.recalc()
            order.save()
        return order

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                SalesOrderItem.objects.create(order=instance, **item)
            instance.recalc()
            instance.save()
        return instance

    def get_salesperson_name(self, obj):
        if not obj.salesperson_id:
            return None
        return obj.salesperson.get_full_name() or obj.salesperson.username

    def get_distributor_name(self, obj):
        if not obj.distributor_id:
            return None
        return f'{obj.distributor.name} ({obj.distributor.distributor_id})'

    def get_invoice_number(self, obj):
        invoice = obj.invoices.order_by('-issue_date').first()
        return invoice.number if invoice else None
