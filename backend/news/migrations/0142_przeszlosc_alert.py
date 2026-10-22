import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0141_clientnote'),
    ]

    operations = [
        migrations.CreateModel(
            name='PrzeszloscAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('kind', models.CharField(choices=[('topic', 'Temat'), ('person', 'Osoba publiczna')], max_length=8)),
                ('key', models.CharField(help_text='topic:<temat małymi literami> albo person:<id osoby>.', max_length=140)),
                ('query', models.CharField(blank=True, help_text='Temat w brzmieniu użytkownika.', max_length=120)),
                ('status', models.CharField(choices=[('pending', 'czeka na potwierdzenie'), ('confirmed', 'aktywny'), ('unsubscribed', 'wypisany')], db_index=True, default='pending', max_length=12)),
                ('token', models.CharField(help_text='Link potwierdzenia i wypisania - bez logowania.', max_length=64, unique=True)),
                ('consent_version', models.CharField(max_length=16)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('confirmation_sent_at', models.DateTimeField(blank=True, null=True)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('unsubscribed_at', models.DateTimeField(blank=True, null=True)),
                ('last_sent_at', models.DateTimeField(blank=True, help_text='Ostatni dzienny list z tym alertem.', null=True)),
                ('sent_ids', models.JSONField(blank=True, default=list, help_text='Ostatnio wysłane pozycje tematu (bez powtórek).')),
                ('figure', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='przeszlosc_alerts', to='news.publicfigure')),
            ],
            options={
                'verbose_name': 'alert przeszłość.today',
                'verbose_name_plural': 'alerty przeszłość.today',
                'ordering': ['-created_at'],
                'constraints': [models.UniqueConstraint(fields=('email', 'key'), name='przeszlosc_alert_email_key')],
            },
        ),
    ]
