from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [("news", "0076_public_figure_merged_into")]

    operations = [migrations.CreateModel(
        name="ArticleChangeEvent",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("change_type", models.CharField(choices=[("modified", "Zmieniona treść"), ("removed", "Usunięty materiał")], max_length=16)),
            ("status", models.CharField(choices=[("pending", "Oczekuje na zatwierdzenie"), ("approved", "Zatwierdzone"), ("rejected", "Odrzucone")], db_index=True, default="pending", max_length=16)),
            ("previous_title_sha256", models.CharField(blank=True, max_length=64)),
            ("current_title_sha256", models.CharField(blank=True, max_length=64)),
            ("previous_content_sha256", models.CharField(blank=True, max_length=64)),
            ("current_content_sha256", models.CharField(blank=True, max_length=64)),
            ("source_status", models.PositiveSmallIntegerField(blank=True, null=True)),
            ("details", models.JSONField(blank=True, default=dict)),
            ("detected_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ("reviewed_at", models.DateTimeField(blank=True, null=True)),
            ("article", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="change_events", to="news.article")),
            ("evidence_snapshot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="change_events", to="news.evidencesnapshot")),
            ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_article_changes", to=settings.AUTH_USER_MODEL)),
        ],
        options={"ordering": ["-detected_at", "-pk"]},
    ), migrations.AddConstraint(
        model_name="articlechangeevent",
        constraint=models.UniqueConstraint(fields=("article", "change_type", "current_content_sha256", "current_title_sha256"), name="unique_article_observed_change"),
    )]
