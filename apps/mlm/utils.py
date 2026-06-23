"""
MLM utility functions — shared between views and admin
"""

from decimal import Decimal


def calculate_and_create_commissions(tx):
    """
    Walk up the referral tree from the transaction's user and create Commission
    records for every active upline member that has a matching CommissionStructure.
    Also refreshes each upline member's Earning aggregate.
    """
    from .models import MLMProfile, CommissionStructure, Commission, Earning

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
