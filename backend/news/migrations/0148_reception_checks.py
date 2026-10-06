# Jak spin zadziałał (news/odbior_spinu.py): odbiór wpisu dobę później, tylko liczby zbiorcze.

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0147_position_checks'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReceptionCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('retry', 'Ponowić odczyt'), ('done', 'Sprawdzone'), ('no_model', 'Liczniki bez oceny modelu'), ('unavailable', 'Wpis niedostępny'), ('failed', 'Nieudane')], db_index=True, default='retry', max_length=12)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('checked_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('hours_after', models.FloatField(blank=True, null=True)),
                ('metrics_before', models.JSONField(blank=True, default=dict, help_text='Liczniki wpisu przy pobraniu.')),
                ('metrics_after', models.JSONField(blank=True, default=dict, help_text='Liczniki wpisu po dobie.')),
                ('requested', models.PositiveSmallIntegerField(default=0)),
                ('sample', models.PositiveSmallIntegerField(default=0, help_text='Liczba przeanalizowanych odpowiedzi.')),
                ('shares', models.JSONField(blank=True, default=dict, help_text='Udziały w procentach: zgoda, sprzeciw, kpina, inne, powtarza, zrodla.')),
                ('sentiment', models.JSONField(blank=True, default=dict)),
                ('phrases', models.JSONField(blank=True, default=list, help_text='Najwyżej 3 zwroty z co najmniej 3 odpowiedzi, bez nazw i @.')),
                ('figures', models.JSONField(blank=True, default=list, help_text='Odpowiedzi osób publicznych z rejestru: nazwa, konto, odnośnik.')),
                ('verdict', models.CharField(blank=True, max_length=12)),
                ('model_name', models.CharField(blank=True, max_length=200)),
                ('reads_used', models.PositiveSmallIntegerField(default=0)),
                ('cost_usd', models.DecimalField(decimal_places=4, default=0, max_digits=8)),
                ('error', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('diagnosis', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='reception', to='news.spindiagnosis')),
            ],
            options={
                'verbose_name': 'odbiór spinu',
                'verbose_name_plural': 'odbiór spinu',
            },
        ),
    ]
