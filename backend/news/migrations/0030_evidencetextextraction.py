from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("news", "0029_quality_profiles_relations_state")]
    operations = [
        migrations.AddField(
            model_name="evidencesnapshot",
            name="allowed_uses",
            field=models.JSONField(blank=True, default=list, help_text="Wersjonowany zakres zgody. Pusta lista nie zezwala na ekstrakcję, RAG ani trening.", verbose_name="jawnie dozwolone zastosowania"),
        ),
        migrations.CreateModel(
            name="EvidenceTextExtraction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("method", models.CharField(max_length=32)),
                ("pipeline_version", models.CharField(max_length=60)),
                ("engine_version", models.CharField(blank=True, max_length=120)),
                ("input_sha256", models.CharField(max_length=64)),
                ("text_sha256", models.CharField(blank=True, max_length=64)),
                ("text", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("pending", "Oczekuje"), ("succeeded", "Gotowe"), ("failed", "Błąd")], default="pending", max_length=16)),
                ("language", models.CharField(blank=True, max_length=32)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("article", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="evidence_text_extractions", to="news.article")),
                ("snapshot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="text_extractions", to="news.evidencesnapshot")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddConstraint(
            model_name="evidencetextextraction",
            constraint=models.UniqueConstraint(fields=("snapshot", "pipeline_version", "input_sha256"), name="unique_snapshot_text_pipeline_input"),
        ),
    ]
