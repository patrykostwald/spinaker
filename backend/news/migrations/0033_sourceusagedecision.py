from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('news', '0032_sourcerecoverycase_sourcecontactcard')]

    operations = [
        migrations.CreateModel(
            name='SourceUsageDecision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=1)),
                ('status', models.CharField(choices=[('draft', 'Szkic'), ('approved', 'Zatwierdzona'), ('suspended', 'Wstrzymana')], default='draft', max_length=20)),
                ('allowed_uses', models.JSONField(default=list)),
                ('applies_until_acquired_at', models.DateTimeField()),
                ('frozen_host', models.CharField(max_length=255)),
                ('terms_url', models.URLField(blank=True, max_length=1024)),
                ('evidence', models.JSONField(default=dict)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_by', models.CharField(blank=True, max_length=120)),
                ('valid_until', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='usage_decisions', to='news.source')),
            ],
            options={'ordering': ['source_id', '-version']},
        ),
        migrations.AddConstraint(
            model_name='sourceusagedecision',
            constraint=models.UniqueConstraint(fields=('source', 'version'), name='unique_source_usage_decision_version'),
        ),
    ]
