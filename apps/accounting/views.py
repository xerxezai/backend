from rest_framework import viewsets, filters
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Account, JournalEntry, JournalLine
from .serializers import AccountSerializer, JournalEntrySerializer, JournalLineSerializer


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name', 'code']
    filterset_fields = ['type', 'is_active']


class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.prefetch_related('lines__account').all()
    serializer_class = JournalEntrySerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, DjangoFilterBackend, filters.OrderingFilter]
    search_fields = ['number', 'description', 'reference']
    filterset_fields = ['posted']
    ordering_fields = ['date', 'created_at']


class JournalLineViewSet(viewsets.ModelViewSet):
    queryset = JournalLine.objects.select_related('entry', 'account').all()
    serializer_class = JournalLineSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['entry', 'account']
