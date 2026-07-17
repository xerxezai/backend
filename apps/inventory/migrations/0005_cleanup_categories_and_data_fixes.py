from decimal import Decimal

from django.db import migrations

NEW_CATEGORIES = [
    ('CAT-ELEC', 'Electronics'),
    ('CAT-SOFT', 'Software'),
    ('CAT-HARD', 'Hardware'),
    ('CAT-SERV', 'Services'),
]

# Sign convention duplicated from StockMovement.POSITIVE_TYPES/NEGATIVE_TYPES (models.py) —
# migrations use a frozen historical model, so the real property/methods aren't available.
POSITIVE_TYPES = ('in', 'adjust', 'return')
NEGATIVE_TYPES = ('out', 'damage')


def forwards(apps, schema_editor):
    ProductCategory = apps.get_model('inventory', 'ProductCategory')
    Product = apps.get_model('inventory', 'Product')

    # 1. Add the missing standard categories (idempotent — safe to re-run).
    categories = {}
    for code, name in NEW_CATEGORIES:
        cat, _ = ProductCategory.objects.get_or_create(name=name, defaults={'code': code})
        categories[name] = cat

    # 2. "Hana" was miscategorised as "pipes" — its name strongly suggests SAP HANA
    # (enterprise database/analytics software), not a physical pipe product, so it's
    # reassigned to the new Software category. Scoped tightly (name + current category
    # both matched) so this can never touch an unrelated product that happens to be
    # named Hana with a deliberately-chosen category.
    Product.objects.filter(
        name__iexact='Hana', category__name__icontains='pipe',
    ).update(category=categories['Software'])

    # 3. Laptop's min_stock_level was set high enough that a healthy 30-unit stock level
    # still showed as "Low Stock". Lower it to a realistic reorder threshold. Only applied
    # when the current computed stock is at or above 20 units and still flagged low, so
    # this can't accidentally mask a genuinely low-stock laptop.
    for product in Product.objects.filter(name__iexact='Laptop'):
        movements = product.stock_movements.all()
        current_stock = sum(
            (m.quantity if m.type in POSITIVE_TYPES else -m.quantity if m.type in NEGATIVE_TYPES else Decimal('0'))
            for m in movements
        )
        if current_stock >= 20 and product.min_stock_level > current_stock:
            product.min_stock_level = Decimal('10')
            product.save(update_fields=['min_stock_level'])


def backwards(apps, schema_editor):
    # Data corrections aren't reversed — re-running forwards is always safe (idempotent),
    # but undoing a "which category is correct" judgment call on reverse migration isn't.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_alter_stockmovement_reason'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
