from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [('contenttypes', '0002_remove_content_type_name'), ('news', '0056_central_party_account_candidates')]

    operations = [
        migrations.CreateModel(
            name='SocialHandleEvidence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('platform', models.CharField(choices=[('x', 'X')], default='x', max_length=16)),
                ('handle', models.CharField(max_length=15)),
                ('evidence_url', models.URLField(max_length=1024)),
                ('extracted_url', models.URLField(max_length=1024)),
                ('observed_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('status', models.CharField(choices=[('pending_review', 'Do przeglądu'), ('candidate_created', 'Przekazano do kandydatur'), ('rejected', 'Odrzucono')], db_index=True, default='pending_review', max_length=24)),
                ('reviewed_at', models.DateTimeField(blank=True, editable=False, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('candidate', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='social_evidence', to='news.politicalaccountcandidate')),
                ('reviewed_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_social_handle_evidence', to=settings.AUTH_USER_MODEL)),
                ('roster_entry', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='social_handle_evidence', to='news.parliamentaryrosterentry')),
                ('subject_object_id', models.PositiveBigIntegerField(blank=True, null=True)),
                ('subject_content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='contenttypes.contenttype')),
            ],
            options={'ordering': ['-observed_at', 'roster_entry__full_name', 'handle']},
        ),
        migrations.AddConstraint(
            model_name='socialhandleevidence',
            constraint=models.UniqueConstraint(fields=('roster_entry', 'platform', 'handle'), name='news_social_evidence_roster_platform_handle_unique'),
        ),
    ]
