from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lma', '0003_lmaprofile_bio_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='video_url',
            field=models.URLField(blank=True, default=''),
        ),
    ]
