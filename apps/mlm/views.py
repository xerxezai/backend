"""
MLM Views for XERXEZ Backend
Handles referral registration, commission calculation, and earnings retrieval
"""

from decimal import Decimal
from django.db import transaction as db_transaction
from django.db.models import Sum
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import MLMProfile, CommissionStructure, Transaction, Commission, Earning
from .serializers import (
    MLMProfileSerializer,
    CommissionStructureSerializer,
    TransactionSerializer,
    CommissionSerializer,
    EarningSerializer,
    ReferralTreeNodeSerializer,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calculate_and_create_commissions(tx: Transaction):
    """
    Walk up the referral tree from the transaction's user and create Commission
    records for every active upline member that has a matching CommissionStructure.
    Also refreshes each upline member's Earning aggregate.
    """
    try:
        profile = tx.user.mlm_profile
    except MLMProfile.DoesNotExist:
        return

    current = profile.referrer
    level = 1

    while current is not None and level <= 10:
        try:
            structure = CommissionStructure.objects.get(level=level, is_active=True)
        except CommissionStructure.DoesNotExist:
            current = current.referrer
            level += 1
            continue

        commission_amount = tx.amount * (structure.commission_rate / Decimal('100'))

        Commission.objects.get_or_create(
            earner=current.user,
            transaction=tx,
            level=level,
            defaults={
                'source_user': tx.user,
                'commission_rate': structure.commission_rate,
                'amount': commission_amount,
            },
        )

        earning, _ = Earning.objects.get_or_create(user=current.user)
        earning.recalculate()

        current = current.referrer
        level += 1


# ---------------------------------------------------------------------------
# MLM Profile
# ---------------------------------------------------------------------------

class MLMProfileListCreateView(generics.ListCreateAPIView):
    """
    GET  — list own profile (staff sees all)
    POST — register current user in MLM (optionally supply referrer_code)
    """
    serializer_class = MLMProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return MLMProfile.objects.all().select_related('user', 'referrer__user')
        return MLMProfile.objects.filter(user=self.request.user)

    @swagger_auto_schema(
        request_body=MLMProfileSerializer,
        responses={201: MLMProfileSerializer},
    )
    def perform_create(self, serializer):
        referrer_code = self.request.data.get('referrer_code', '').strip()
        referrer = None

        if referrer_code:
            try:
                referrer = MLMProfile.objects.get(referral_code=referrer_code, is_active=True)
                MLMProfile.objects.filter(pk=referrer.pk).update(
                    total_referrals=referrer.total_referrals + 1
                )
            except MLMProfile.DoesNotExist:
                pass

        serializer.save(user=self.request.user, referrer=referrer)


class MLMProfileDetailView(generics.RetrieveUpdateAPIView):
    """GET / PATCH own profile (staff can access any profile by pk)."""
    serializer_class = MLMProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return MLMProfile.objects.all().select_related('user', 'referrer__user')
        return MLMProfile.objects.filter(user=self.request.user)


# ---------------------------------------------------------------------------
# Commission Structure  (admin only)
# ---------------------------------------------------------------------------

class CommissionStructureListCreateView(generics.ListCreateAPIView):
    """List and create commission rate structures. Admin only."""
    queryset = CommissionStructure.objects.all().order_by('level')
    serializer_class = CommissionStructureSerializer
    permission_classes = [permissions.IsAdminUser]


class CommissionStructureDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a commission rate. Admin only."""
    queryset = CommissionStructure.objects.all()
    serializer_class = CommissionStructureSerializer
    permission_classes = [permissions.IsAdminUser]


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

class TransactionListCreateView(generics.ListCreateAPIView):
    """
    GET  — list own transactions (staff sees all)
    POST — create a transaction; if status='completed' commissions fire immediately
    """
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Transaction.objects.all().select_related('user')
        return Transaction.objects.filter(user=self.request.user)

    @db_transaction.atomic
    def perform_create(self, serializer):
        tx = serializer.save(user=self.request.user)
        if tx.status == 'completed':
            _calculate_and_create_commissions(tx)


class TransactionDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   — retrieve a transaction
    PATCH — update status; if status moves to 'completed', commissions fire
    """
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Transaction.objects.all().select_related('user')
        return Transaction.objects.filter(user=self.request.user)

    @db_transaction.atomic
    def perform_update(self, serializer):
        old_status = self.get_object().status
        tx = serializer.save()
        if old_status != 'completed' and tx.status == 'completed':
            _calculate_and_create_commissions(tx)


# ---------------------------------------------------------------------------
# Commissions
# ---------------------------------------------------------------------------

class CommissionListView(generics.ListAPIView):
    """List commissions earned by the authenticated user (staff sees all)."""
    serializer_class = CommissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Commission.objects.all().select_related(
                'earner', 'source_user', 'transaction'
            )
        return Commission.objects.filter(earner=self.request.user).select_related(
            'source_user', 'transaction'
        )


# ---------------------------------------------------------------------------
# Earnings
# ---------------------------------------------------------------------------

class EarningsView(generics.RetrieveAPIView):
    """Return the authenticated user's aggregated earnings (auto-recalculated)."""
    serializer_class = EarningSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        earning, _ = Earning.objects.get_or_create(user=self.request.user)
        earning.recalculate()
        return earning


# ---------------------------------------------------------------------------
# Referral tree
# ---------------------------------------------------------------------------

@swagger_auto_schema(
    method='get',
    manual_parameters=[
        openapi.Parameter(
            'depth', openapi.IN_QUERY,
            description='How many levels deep to render (max 5, default 3)',
            type=openapi.TYPE_INTEGER,
        )
    ],
    responses={200: ReferralTreeNodeSerializer},
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def referral_tree_view(request):
    """Return the authenticated user's referral tree as a nested JSON structure."""
    try:
        profile = request.user.mlm_profile
    except MLMProfile.DoesNotExist:
        return Response(
            {'detail': 'MLM profile not found. Register first via /mlm/profile/.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    depth = min(int(request.query_params.get('depth', 3)), 5)
    serializer = ReferralTreeNodeSerializer(
        profile,
        context={'max_depth': depth, 'current_depth': 0},
    )
    return Response(serializer.data)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def dashboard_view(request):
    """
    MLM dashboard summary:
    - Profile info
    - Aggregated earnings
    - Commission breakdown by level
    - Direct referral count
    """
    try:
        profile = request.user.mlm_profile
    except MLMProfile.DoesNotExist:
        return Response(
            {'detail': 'MLM profile not found. Register first via /mlm/profile/.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    earning, _ = Earning.objects.get_or_create(user=request.user)
    earning.recalculate()

    commissions_by_level = (
        Commission.objects
        .filter(earner=request.user)
        .values('level')
        .annotate(total=Sum('amount'), count=Sum('id'))  # count via id
        .order_by('level')
    )

    return Response({
        'profile': MLMProfileSerializer(profile).data,
        'earnings': EarningSerializer(earning).data,
        'commissions_by_level': list(commissions_by_level),
        'direct_referrals': profile.referrals.filter(is_active=True).count(),
        'total_downline': len(profile.get_downline(max_depth=5)),
    })
