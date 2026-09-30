import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('news', '0094_walletbalance')]
    operations = [
        migrations.AddField(model_name=name, name='repair_attempts',
                            field=models.PositiveSmallIntegerField(default=0))
        for name in ('spindiagnosis', 'clinicinterview')
    ] + [
        migrations.CreateModel(name='RepairAction', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('created_at', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
            ('rule', models.CharField(max_length=40)),
            ('target', models.CharField(max_length=160)),
            ('result', models.CharField(max_length=16, choices=[(s, s) for s in
                ('fixed', 'retried', 'skipped', 'failed', 'needs_owner')])),
            ('description', models.CharField(max_length=300)),
        ], options={'ordering': ['-created_at', '-pk'], 'indexes': [
            models.Index(fields=['rule', 'target', 'created_at'], name='repair_target_time')]}),
        migrations.CreateModel(name='RepairerState', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('key', models.CharField(max_length=40, unique=True)),
            ('data', models.JSONField(default=dict)),
        ]),
    ]
