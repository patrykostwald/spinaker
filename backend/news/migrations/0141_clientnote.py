from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0140_agents_dyrygent'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientNote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('project', models.CharField(db_index=True, max_length=60)),
                ('page', models.CharField(blank=True, max_length=200)),
                ('x', models.FloatField(blank=True, null=True)),
                ('y', models.FloatField(blank=True, null=True)),
                ('anchor', models.CharField(blank=True, max_length=200)),
                ('text', models.TextField(max_length=2000)),
                ('name', models.CharField(blank=True, max_length=120)),
                ('viewport', models.CharField(blank=True, max_length=20)),
                ('status', models.CharField(choices=[('new', 'Nowa'), ('done', 'Wprowadzona'), ('rejected', 'Nie wprowadzamy')], db_index=True, default='new', max_length=10)),
                ('staff_note', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'uwaga klienta (zbudujmi)',
                'verbose_name_plural': 'uwagi klientów (zbudujmi)',
                'ordering': ['-created_at'],
            },
        ),
    ]
