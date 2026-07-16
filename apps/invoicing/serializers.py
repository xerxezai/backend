from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from .models import Invoice, InvoiceItem, Payment, RecurringInvoice, CreditNote


def _build_invoice_items(invoice, items_data):
    """Builds unsaved InvoiceItem instances for bulk_create. bulk_create skips
    each instance's save(), so line_total/description are computed here to
    mirror InvoiceItem.save() exactly."""
    items = []
    for item in items_data:
        obj = InvoiceItem(invoice=invoice, **item)
        if not obj.description and obj.product_id:
            obj.description = obj.product.name
        obj.line_total = (obj.quantity or 0) * (obj.unit_price or 0)
        items.append(obj)
    return items


class InvoiceItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True, default=None)

    class Meta:
        model = InvoiceItem
        fields = ['id', 'invoice', 'product', 'product_name', 'description', 'quantity', 'unit_price', 'line_total']
        read_only_fields = ['id', 'line_total']
        extra_kwargs = {'invoice': {'required': False}}


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, required=False)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    sales_order_number = serializers.CharField(source='sales_order.number', read_only=True, default=None)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = '__all__'
        read_only_fields = ['subtotal', 'tax', 'total', 'amount_paid']

    def get_is_overdue(self, obj):
        return bool(obj.due_date and obj.due_date < timezone.now().date() and obj.status not in ('paid', 'cancelled'))

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        with transaction.atomic():
            invoice = Invoice.objects.create(**validated_data)
            InvoiceItem.objects.bulk_create(_build_invoice_items(invoice, items_data))
            invoice.recalc()
            invoice.save()
        return invoice

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        with transaction.atomic():
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            if items_data is not None:
                instance.items.all().delete()
                InvoiceItem.objects.bulk_create(_build_invoice_items(instance, items_data))
            instance.recalc()
            instance.save()
        return instance


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source='invoice.number', read_only=True)
    customer_name = serializers.CharField(source='invoice.customer.name', read_only=True, default=None)

    class Meta:
        model = Payment
        fields = '__all__'


class RecurringInvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = RecurringInvoice
        fields = '__all__'
        read_only_fields = ['last_generated_at']


class CreditNoteSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    invoice_number = serializers.CharField(source='invoice.number', read_only=True)

    class Meta:
        model = CreditNote
        fields = '__all__'
        read_only_fields = ['customer', 'status']

    def create(self, validated_data):
        # customer is derived from the linked invoice, not entered separately —
        # keeps it from ever disagreeing with which invoice the credit note is against.
        validated_data['customer'] = validated_data['invoice'].customer
        return super().create(validated_data)
