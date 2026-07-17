from django.db import migrations

MODULES = [
    ('dashboard', 'Dashboard', 'fas fa-th-large', 1),
    ('crm', 'CRM', 'fas fa-users', 2),
    ('sales', 'Sales', 'fas fa-shopping-cart', 3),
    ('procurement', 'Procurement', 'fas fa-truck', 4),
    ('logistics', 'Logistics', 'fas fa-shipping-fast', 5),
    ('accounting', 'Accounting', 'fas fa-book', 6),
    ('mlm', 'MLM', 'fas fa-sitemap', 7),
    ('hr', 'HR Overview', 'fas fa-user-tie', 8),
]


def seed_modules(apps, schema_editor):
    Module = apps.get_model('rbac', 'Module')
    for name, display_name, icon, order in MODULES:
        Module.objects.get_or_create(
            name=name,
            defaults={'display_name': display_name, 'icon': icon, 'order': order, 'is_active': True},
        )


def unseed_modules(apps, schema_editor):
    Module = apps.get_model('rbac', 'Module')
    Module.objects.filter(name__in=[m[0] for m in MODULES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('rbac', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_modules, unseed_modules),
    ]
