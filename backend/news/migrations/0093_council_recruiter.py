import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0092_council_expansion'),
    ]

    operations = [
        migrations.CreateModel(
            name='CouncilSeat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(max_length=32)),
                ('model', models.CharField(max_length=200)),
                ('company', models.CharField(blank=True, max_length=100)),
                ('origin', models.CharField(default='config', help_text='config — stały skład, recruiter — przyjęty przez Rekrutera.', max_length=16)),
                ('roles', models.JSONField(blank=True, default=list, help_text='Role przyznane przez Konsylium (dla origin=recruiter).')),
                ('status', models.CharField(choices=[('active', 'aktywny'), ('suspended', 'zawieszony')], db_index=True, default='active', max_length=12)),
                ('admitted_at', models.DateTimeField(blank=True, null=True)),
                ('suspended_at', models.DateTimeField(blank=True, null=True)),
                ('last_ok_at', models.DateTimeField(blank=True, null=True)),
                ('first_fail_at', models.DateTimeField(blank=True, help_text='Początek nieprzerwanej serii twardych błędów (np. 404).', null=True)),
                ('last_error', models.CharField(blank=True, max_length=160)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('provider', 'model'), name='council_seat_unique')],
            },
        ),
        migrations.CreateModel(
            name='CouncilRecruitment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('kind', models.CharField(default='candidate', help_text='candidate, suspension, return', max_length=16)),
                ('provider', models.CharField(max_length=32)),
                ('model', models.CharField(max_length=200)),
                ('company', models.CharField(blank=True, max_length=100)),
                ('source', models.JSONField(blank=True, default=dict, help_text='Skąd kandydat: katalog dostawcy, kontekst, uwagi sita.')),
                ('exam', models.JSONField(blank=True, default=dict)),
                ('votes', models.JSONField(blank=True, default=list)),
                ('decision', models.CharField(blank=True, help_text='admitted, rejected, would_admit, would_reject, suspended, returned', max_length=20)),
                ('roles', models.JSONField(blank=True, default=list)),
                ('mode', models.CharField(default='trial', help_text='trial — tylko rekomendacja, auto — decyzja wykonana.', max_length=8)),
                ('reason', models.TextField(blank=True)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
