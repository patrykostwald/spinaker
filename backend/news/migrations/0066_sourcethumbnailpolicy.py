from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('news', '0065_user_x_connection')]

    operations = [
        migrations.CreateModel(
            name='SourceThumbnailPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('review_required', 'Wymaga kontroli pojedynczego obrazu'), ('allowed', 'Dozwolona po atrybucji'), ('prohibited', 'Niedozwolona')], default='review_required', max_length=24)),
                ('terms_url', models.URLField(max_length=1024)),
                ('license_url', models.URLField(blank=True, max_length=1024)),
                ('attribution_template', models.CharField(blank=True, max_length=512)),
                ('evidence', models.JSONField(default=dict)),
                ('reviewed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('reviewed_by', models.CharField(max_length=120)),
                ('next_review_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='thumbnail_policy', to='news.source')),
            ],
            options={'ordering': ['source__name']},
        ),
    ]
