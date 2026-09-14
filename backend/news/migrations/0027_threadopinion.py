from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('news', '0026_profilepreference_theme_preference'),
    ]

    operations = [
        migrations.CreateModel(
            name='ThreadOpinion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('polarity', models.CharField(choices=[('positive', 'Pozytywny'), ('negative', 'Negatywny')], max_length=8)),
                ('body', models.CharField(blank=True, default='', max_length=240)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='opinions', to='news.thread')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='thread_opinions', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at', '-id']},
        ),
        migrations.AddConstraint(
            model_name='threadopinion',
            constraint=models.UniqueConstraint(fields=('user', 'thread'), name='one_opinion_per_user_thread'),
        ),
        migrations.AddConstraint(
            model_name='threadopinion',
            constraint=models.CheckConstraint(condition=models.Q(('polarity__in', ['positive', 'negative'])), name='thread_opinion_valid_polarity'),
        ),
    ]
