from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('news', '0057_social_handle_evidence')]

    operations = [
        migrations.CreateModel(
            name='PublicFigure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('canonical_name', models.CharField(max_length=255, unique=True)),
                ('role_category', models.CharField(choices=[('government', 'Rząd i administracja'), ('party', 'Partia lub klub parlamentarny'), ('parliamentary', 'Parlament krajowy'), ('european', 'Parlament Europejski'), ('local', 'Samorząd'), ('political', 'Inna osoba politycznie wpływowa')], max_length=16)),
                ('role_title', models.CharField(max_length=255)),
                ('organisation', models.CharField(blank=True, max_length=255)),
                ('status', models.CharField(choices=[('current', 'Aktualna rola'), ('former', 'Była rola')], default='current', max_length=12)),
                ('official_profile_url', models.URLField(blank=True, max_length=1024)),
                ('import_key', models.CharField(blank=True, db_index=True, help_text='Techniczny klucz oficjalnego importu; nie jest kontem społecznościowym.', max_length=1024)),
                ('evidence_url', models.URLField(help_text='Publiczne źródło potwierdzające rolę lub status wpisu.', max_length=1024)),
                ('evidence_note', models.TextField(blank=True)),
                ('political_alignment', models.CharField(blank=True, help_text='Opcjonalna, ręczna notatka redakcyjna; nie jest ustalana automatycznie.', max_length=255)),
                ('source_checked_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('archived', models.BooleanField(db_index=True, default=False, help_text='Wpis archiwalny pozostaje w rejestrze i nie jest usuwany.')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['archived', 'canonical_name']},
        ),
    ]
