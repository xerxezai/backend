from rest_framework import viewsets, filters
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Customer, Contact, Lead, Activity
from .serializers import CustomerSerializer, ContactSerializer, LeadSerializer, ActivitySerializer


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['name', 'company', 'email', 'code']
    filterset_fields = ['is_active', 'industry']
    ordering_fields = ['name', 'created_at']


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.select_related('customer').all()
    serializer_class = ContactSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'email', 'customer__name']
    filterset_fields = ['customer', 'is_primary']


class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.select_related('assigned_to', 'customer').all()
    serializer_class = LeadSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    search_fields = ['name', 'company', 'email']
    filterset_fields = ['status', 'source', 'assigned_to']
    ordering_fields = ['created_at', 'estimated_value']


class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.select_related('user', 'lead', 'customer').all()
    serializer_class = ActivitySerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['summary', 'body']
    filterset_fields = ['type', 'lead', 'customer']
