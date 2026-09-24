from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('news', '0070_public_figure_import_key_unique')]

    operations = [
        migrations.CreateModel(
            name='SourceReviewDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('decision', models.CharField(choices=[('covered', 'Pokryte aktywnym źródłem'), ('technical_recheck', 'Wymaga ponownej kontroli technicznej'), ('terms_review', 'Wymaga sprawdzenia warunków'), ('channel_discovery', 'Brak potwierdzonego kanału'), ('contact_required', 'Wymaga późniejszego potwierdzenia')], max_length=32)),
                ('reason', models.TextField()),
                ('evidence_urls', models.JSONField(blank=True, default=list)),
                ('audit_snapshot', models.JSONField(blank=True, default=dict)),
                ('reviewed_by', models.CharField(max_length=120)),
                ('reviewed_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('is_automated', models.BooleanField(default=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('source', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='review_decision', to='news.source')),
            ],
            options={'ordering': ['decision', 'source__name']},
        ),
    ]
