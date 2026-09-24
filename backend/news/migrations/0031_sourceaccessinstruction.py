from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('news', '0030_evidencetextextraction')]

    operations = [
        migrations.CreateModel(
            name='SourceAccessInstruction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=1)),
                ('status', models.CharField(choices=[('draft', 'Szkic'), ('approved', 'Zatwierdzona'), ('suspended', 'Wstrzymana'), ('contact_required', 'Wymaga kontaktu')], default='draft', max_length=20)),
                ('channel', models.CharField(choices=[('api', 'API'), ('rss', 'RSS / Atom'), ('export', 'Eksport danych'), ('oai_pmh', 'OAI-PMH'), ('sitemap', 'Sitemap'), ('html', 'Jawnie dozwolony HTML')], max_length=16)),
                ('allowed_scope', models.CharField(choices=[('metadata', 'Metadane'), ('content', 'Treść'), ('snapshot', 'Snapshot')], default='metadata', max_length=16)),
                ('endpoint', models.URLField(max_length=1024)),
                ('terms_url', models.URLField(blank=True, max_length=1024)),
                ('evidence', models.JSONField(default=dict, help_text='URL-e i krótkie fakty potwierdzające decyzję.')),
                ('minimum_interval_seconds', models.PositiveIntegerField(default=3)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_by', models.CharField(blank=True, max_length=120)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='access_instructions', to='news.source')),
            ],
            options={'ordering': ['source_id', '-version']},
        ),
        migrations.AddConstraint(
            model_name='sourceaccessinstruction',
            constraint=models.UniqueConstraint(fields=('source', 'version'), name='unique_source_access_instruction_version'),
        ),
    ]
