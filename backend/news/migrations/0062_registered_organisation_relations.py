from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ('news', '0061_senior_cabinet_account_candidates'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RegisteredOrganisation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=512)),
                ('krs_number', models.CharField(max_length=10, unique=True)),
                ('kind', models.CharField(choices=[('foundation', 'Fundacja'), ('association', 'Stowarzyszenie'), ('company', 'Spółka'), ('other', 'Inny podmiot rejestrowy')], max_length=16)),
                ('official_register_url', models.URLField(help_text='Link do publicznego wpisu KRS albo urzędowego odpisu.', max_length=1024)),
                ('source_checked_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('archived', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['kind', 'name']},
        ),
        migrations.CreateModel(
            name='PublicFigureOrganisationRelation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public_role', models.CharField(help_text='Wyłącznie rola jawnie wskazana w źródle publicznym.', max_length=255)),
                ('relation_status', models.CharField(choices=[('current', 'Obecna'), ('former', 'Historyczna')], default='current', max_length=12)),
                ('evidence_url', models.URLField(help_text='Bezpośredni publiczny dowód relacji; nie sam wynik dopasowania nazwiska.', max_length=1024)),
                ('evidence_note', models.TextField(blank=True)),
                ('verification_status', models.CharField(choices=[('pending_review', 'Wymaga potwierdzenia redakcji'), ('confirmed', 'Potwierdzona w źródle publicznym'), ('rejected', 'Odrzucona')], db_index=True, default='pending_review', max_length=20)),
                ('verified_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organisation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='public_figure_relations', to='news.registeredorganisation')),
                ('public_figure', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='organisation_relations', to='news.publicfigure')),
                ('verified_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_public_figure_organisation_relations', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['public_figure__canonical_name', 'organisation__kind', 'organisation__name']},
        ),
        migrations.AddConstraint(
            model_name='publicfigureorganisationrelation',
            constraint=models.UniqueConstraint(fields=('public_figure', 'organisation', 'public_role', 'relation_status'), name='unique_public_figure_organisation_role_status'),
        ),
    ]
