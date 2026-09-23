# Generated manually for the durable public-office registry.
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0073_publicfigurearticlereference'),
    ]

    operations = [
        migrations.CreateModel(
            name='PublicOffice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('import_key', models.CharField(max_length=1024, unique=True)),
                ('title', models.CharField(max_length=255)),
                ('role_category', models.CharField(choices=[('government', 'Rząd i administracja'), ('party', 'Partia lub klub parlamentarny'), ('parliamentary', 'Parlament krajowy'), ('european', 'Parlament Europejski'), ('local', 'Samorząd'), ('political', 'Inna osoba politycznie wpływowa')], max_length=16)),
                ('organisation', models.CharField(blank=True, max_length=255)),
                ('official_roster_url', models.URLField(max_length=1024)),
                ('evidence_note', models.TextField(blank=True)),
                ('source_checked_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('archived', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('current_holder', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='currently_held_public_offices', to='news.publicfigure')),
            ],
            options={'ordering': ['archived', 'role_category', 'organisation', 'title']},
        ),
        migrations.AddField(
            model_name='publicfigurerole',
            name='public_office',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='holder_roles', to='news.publicoffice'),
        ),
    ]
