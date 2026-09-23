# Generated manually to keep the roster schema separate from political X accounts.
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('news', '0054_public_candidate_confirmation_sources')]

    operations = [
        migrations.CreateModel(
            name='ParliamentaryRosterEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source', models.CharField(choices=[('sejm', 'Sejm RP'), ('senat', 'Senat RP'), ('ep', 'Parlament Europejski')], max_length=12)),
                ('external_id', models.CharField(max_length=128)),
                ('full_name', models.CharField(max_length=255)),
                ('club', models.CharField(blank=True, max_length=255)),
                ('district', models.CharField(blank=True, max_length=255)),
                ('profile_url', models.URLField(blank=True, max_length=1024)),
                ('source_url', models.URLField(max_length=1024)),
                ('active', models.BooleanField(db_index=True, default=True)),
                ('last_seen_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['source', 'full_name', 'external_id']},
        ),
        migrations.AddConstraint(
            model_name='parliamentaryrosterentry',
            constraint=models.UniqueConstraint(fields=('source', 'external_id'), name='news_parliamentary_roster_source_id_unique'),
        ),
    ]