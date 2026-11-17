import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0105_warden_second_key_seba'),
    ]

    operations = [
        migrations.CreateModel(
            name='PollVote',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('poll', models.CharField(max_length=40)),
                ('voter', models.CharField(max_length=32)),
                ('network', models.CharField(db_index=True, max_length=32)),
                ('answers', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'constraints': [models.UniqueConstraint(fields=('poll', 'voter'), name='poll_one_voter')],
            },
        ),
    ]
