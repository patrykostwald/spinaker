from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('news', '0101_clinic_discussion')]
    operations = [
        migrations.CreateModel(name='AccountWardenRun', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('started_at', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
            ('finished_at', models.DateTimeField(null=True, blank=True)),
            ('lookups', models.PositiveIntegerField(default=0)),
            ('report', models.JSONField(default=dict)),
        ]),
        migrations.AddField('politicalaccount', 'last_verified_at', models.DateTimeField(null=True, blank=True, db_index=True, editable=False)),
        migrations.AddField('publicfigure', 'account_discovery_at', models.DateTimeField(null=True, blank=True, db_index=True, editable=False)),
        migrations.AlterField('politicalaccount', 'poll_interval_minutes', models.PositiveIntegerField(default=15,
            validators=[MinValueValidator(1), MaxValueValidator(525600)])),
    ]
