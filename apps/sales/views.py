from rest_framework import viewsets, filters
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Quotation, QuotationItem, SalesOrder
from .serializers import QuotationSerializer, QuotationItemSerializer, SalesOrderSerializer


class QuotationViewSet(viewsets.ModelViewSet):
    queryset = Quotation.objects.select_related('customer').prefetch_related('items').all()
    serializer_class = QuotationSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['number', 'customer__name']
    filterset_fields = ['status', 'customer']
    ordering_fields = ['issue_date', 'total']


class QuotationItemViewSet(viewsets.ModelViewSet):
    queryset = QuotationItem.objects.select_related('quotation').all()
    serializer_class = QuotationItemSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['quotation']


class SalesOrderViewSet(viewsets.ModelViewSet):
    queryset = SalesOrder.objects.select_related('customer', 'quotation').all()
    serializer_class = SalesOrderSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['number', 'customer__name']
    filterset_fields = ['status', 'customer']
    ordering_fields = ['order_date', 'total']
