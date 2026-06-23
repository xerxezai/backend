"""Logistics: Shipments, Routes, Tracking."""
from django.db import models
from apps.sales.models import SalesOrder
from apps.crm.models import Customer


class Shipment(models.Model):
    STATUS = [
        ('pending', 'Pending'),
        ('dispatched', 'Dispatched'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    ]
    tracking_number = models.CharField(max_length=60, unique=True)
    sales_order = models.ForeignKey(SalesOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name='shipments')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='shipments')
    carrier = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    origin = models.CharField(max_length=255, blank=True)
    destination = models.CharField(max_length=255)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.tracking_number


class TrackingUpdate(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_updates')
    status = models.CharField(max_length=100)
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    occurred_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-occurred_at']

    def __str__(self):
        return f'{self.shipment.tracking_number} - {self.status}'
