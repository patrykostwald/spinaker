from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('news', '0028_evidencesnapshot')]
    operations = [
        migrations.CreateModel(name='ArticleQualityProfile', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('canonical_url', models.URLField(max_length=1024)), ('canonical_sha256', models.CharField(db_index=True, max_length=64)),
            ('title_sha256', models.CharField(db_index=True, max_length=64)), ('content_sha256', models.CharField(blank=True, db_index=True, max_length=64)),
            ('provenance', models.JSONField(default=dict)), ('rules_version', models.CharField(max_length=32)),
            ('checked_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('article', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='quality_profile', to='news.article')),
        ]),
        migrations.CreateModel(name='SourceQualityState', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('sample_size', models.PositiveIntegerField(default=0)), ('metrics', models.JSONField(default=dict)),
            ('baseline_metrics', models.JSONField(default=dict)), ('drift', models.JSONField(default=dict)),
            ('rules_version', models.CharField(max_length=32)), ('checked_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('source', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='quality_state', to='news.source')),
        ]),
        migrations.CreateModel(name='ArticleRelation', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('relation_type', models.CharField(choices=[('similar_publication', 'Podobna publikacja')], max_length=24)),
            ('score', models.DecimalField(decimal_places=4, max_digits=5)), ('evidence', models.JSONField(default=dict)),
            ('rules_version', models.CharField(max_length=32)), ('checked_at', models.DateTimeField(default=django.utils.timezone.now)),
            ('left', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quality_relations_left', to='news.article')),
            ('right', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quality_relations_right', to='news.article')),
        ], options={'constraints': [
            models.UniqueConstraint(fields=('left', 'right', 'relation_type'), name='unique_article_quality_relation'),
            models.CheckConstraint(condition=models.Q(('left_id__lt', models.F('right_id'))), name='article_relation_ordered'),
        ]}),
    ]
