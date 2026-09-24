import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('news', '0062_registered_organisation_relations'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='registeredorganisation',
            name='krs_number',
            field=models.CharField(max_length=10, unique=True, validators=[
                django.core.validators.RegexValidator(r'^\d{10}$', 'Numer KRS musi zawierać dokładnie 10 cyfr.'),
            ]),
        ),
        migrations.CreateModel(
            name='PersonalContextThread',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=140)),
                ('description', models.CharField(blank=True, default='', max_length=500)),
                ('query', models.CharField(blank=True, default='', max_length=200)),
                ('categories', models.JSONField(default=list)),
                ('topics', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='personal_context_threads', to=settings.AUTH_USER_MODEL)),
                ('sources', models.ManyToManyField(blank=True, related_name='personal_context_threads', to='news.source')),
            ],
            options={'ordering': ['-updated_at', '-id']},
        ),
        migrations.CreateModel(
            name='ArticleFavorite',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='favorites', to='news.article')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='article_favorites', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at', '-id']},
        ),
        migrations.CreateModel(
            name='CommentReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('spam', 'Spam'), ('abuse', 'Naruszenie zasad'), ('privacy', 'Dane prywatne'), ('off_topic', 'Poza tematem'), ('other', 'Inne')], max_length=16)),
                ('details', models.CharField(blank=True, default='', max_length=500)),
                ('status', models.CharField(choices=[('new', 'Nowe'), ('reviewed', 'Rozpatrzone'), ('hidden', 'Ukryte')], db_index=True, default='new', max_length=16)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('article_opinion', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='news.articleopinion')),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comment_reports', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_comment_reports', to=settings.AUTH_USER_MODEL)),
                ('thread_opinion', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='news.threadopinion')),
            ],
            options={'ordering': ['status', '-created_at']},
        ),
        migrations.CreateModel(
            name='PersonalContextThreadItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('position', models.PositiveSmallIntegerField()),
                ('article', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='personal_context_thread_items', to='news.article')),
                ('thread', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='news.personalcontextthread')),
            ],
            options={'ordering': ['position', 'id']},
        ),
        migrations.AddConstraint(model_name='articlefavorite', constraint=models.UniqueConstraint(fields=('user', 'article'), name='unique_user_article_favorite')),
        migrations.AddConstraint(model_name='commentreport', constraint=models.CheckConstraint(
            condition=(models.Q(article_opinion__isnull=False, thread_opinion__isnull=True) |
                       models.Q(article_opinion__isnull=True, thread_opinion__isnull=False)),
            name='comment_report_has_exactly_one_target',
        )),
        migrations.AddConstraint(model_name='commentreport', constraint=models.UniqueConstraint(fields=('reporter', 'article_opinion'), name='unique_reporter_article_comment_report')),
        migrations.AddConstraint(model_name='commentreport', constraint=models.UniqueConstraint(fields=('reporter', 'thread_opinion'), name='unique_reporter_thread_comment_report')),
        migrations.AddConstraint(model_name='personalcontextthreaditem', constraint=models.UniqueConstraint(fields=('thread', 'article'), name='unique_personal_context_thread_article')),
        migrations.AddConstraint(model_name='personalcontextthreaditem', constraint=models.UniqueConstraint(fields=('thread', 'position'), name='unique_personal_context_thread_position')),
    ]
