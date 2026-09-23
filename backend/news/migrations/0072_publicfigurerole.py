# Generated manually to keep the evidence-only registry migration explicit.
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.query_utils
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('news', '0071_sourcereviewdecision')]

    operations = [
        migrations.CreateModel(
            name='PublicFigureRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role_category', models.CharField(choices=[('government', 'Rząd i administracja'), ('party', 'Partia lub klub parlamentarny'), ('parliamentary', 'Parlament krajowy'), ('european', 'Parlament Europejski'), ('local', 'Samorząd'), ('political', 'Inna osoba politycznie wpływowa')], max_length=16)),
                ('role_title', models.CharField(max_length=255)),
                ('organisation', models.CharField(blank=True, max_length=255)),
                ('status', models.CharField(choices=[('current', 'Aktualna rola'), ('former', 'Była rola')], default='current', max_length=12)),
                ('official_profile_url', models.URLField(blank=True, max_length=1024)),
                ('evidence_url', models.URLField(max_length=1024)),
                ('evidence_note', models.TextField(blank=True)),
                ('import_key', models.CharField(blank=True, db_index=True, help_text='Techniczny klucz źródłowej roli; nie jest kontem społecznościowym.', max_length=1024)),
                ('source_checked_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('archived', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('public_figure', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='public_roles', to='news.publicfigure')),
            ],
            options={'ordering': ['archived', 'role_category', 'organisation', 'role_title']},
        ),
        migrations.AddConstraint(
            model_name='publicfigurerole',
            constraint=models.UniqueConstraint(condition=django.db.models.query_utils.Q(('import_key__gt', '')), fields=('import_key',), name='news_public_figure_role_nonempty_import_key_unique'),
        ),
    ]
