from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0090_diagnosis_x_posted'),
    ]

    operations = [
        migrations.CreateModel(
            name='SocialPost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(choices=[('facebook', 'Facebook (film)'), ('instagram', 'Instagram (Reels)'), ('bluesky', 'Bluesky'), ('manual', 'TikTok i YouTube Shorts (mail z filmem)')], max_length=12)),
                ('external_id', models.CharField(blank=True, max_length=200)),
                ('url', models.URLField(blank=True, max_length=500)),
                ('posted_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('error', models.CharField(blank=True, max_length=240)),
                ('diagnosis', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='social_posts', to='news.spindiagnosis')),
            ],
            options={
                'ordering': ['-posted_at'],
                'constraints': [models.UniqueConstraint(fields=('diagnosis', 'platform'), name='social_post_once_per_platform')],
            },
        ),
    ]
