from django.db import migrations


def seed_xerxez(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    Company.objects.get_or_create(
        slug='xerxez',
        defaults={
            'name': 'XERXEZ Solutions', 'industry': 'Technology', 'country': 'UAE',
            'city': 'Abu Dhabi', 'status': 'active', 'plan': 'platform',
        },
    )


def unseed_xerxez(apps, schema_editor):
    Company = apps.get_model('companies', 'Company')
    Company.objects.filter(slug='xerxez').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_xerxez, unseed_xerxez),
    ]
