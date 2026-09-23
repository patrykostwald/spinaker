# Generated manually for the reviewed official YouTube channel registry.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
        ('news', '0074_publicoffice_publicfigurerole_public_office'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfficialVideoChannel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject_object_id', models.PositiveBigIntegerField()),
                ('channel_url', models.URLField(help_text='Bezpośredni link youtube.com/channel/... albo youtube.com/@...', max_length=1024)),
                ('channel_id', models.CharField(blank=True, db_index=True, help_text='Niezmienny identyfikator kanału, gdy został potwierdzony.', max_length=64)),
                ('display_name', models.CharField(blank=True, max_length=255)),
                ('evidence_url', models.URLField(help_text='Oficjalna strona podmiotu lub osoby, która linkuje ten kanał.', max_length=1024)),
                ('status', models.CharField(choices=[('pending_review', 'Do przeglądu'), ('confirmed', 'Potwierdzony przez redakcję'), ('rejected', 'Odrzucony')], db_index=True, default='pending_review', max_length=24)),
                ('collection_enabled', models.BooleanField(default=False, help_text='Włącza wyłącznie przyszłe pobieranie metadanych kanału; nie napisów.')),
                ('source_checked_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('reviewed_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_official_video_channels', to=settings.AUTH_USER_MODEL)),
                ('subject_content_type', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='contenttypes.contenttype')),
            ],
            options={'ordering': ['status', 'display_name', 'channel_url']},
        ),
        migrations.AddConstraint(
            model_name='officialvideochannel',
            constraint=models.UniqueConstraint(fields=('subject_content_type', 'subject_object_id', 'channel_url'), name='news_official_video_channel_subject_url_unique'),
        ),
    ]
