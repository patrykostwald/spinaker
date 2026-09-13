from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Source",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, verbose_name="nazwa")),
                ("url", models.URLField(unique=True, verbose_name="adres URL")),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("rss", "RSS"),
                            ("twitter", "Twitter"),
                            ("newsapi", "NewsAPI"),
                            ("gdelt", "GDELT"),
                            ("editorial", "Redakcja"),
                        ],
                        default="rss",
                        max_length=32,
                        verbose_name="typ źródła",
                    ),
                ),
                ("rss_url", models.URLField(blank=True, verbose_name="adres RSS")),
                ("twitter_user_id", models.CharField(blank=True, max_length=64, verbose_name="Twitter user ID")),
                ("is_active", models.BooleanField(default=True, verbose_name="aktywne")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "źródło", "verbose_name_plural": "źródła", "ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Article",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=512, verbose_name="tytuł")),
                ("url", models.URLField(max_length=1024, unique=True, verbose_name="adres URL")),
                ("published_date", models.DateTimeField(db_index=True, verbose_name="data publikacji")),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("article", "Artykuł"),
                            ("tweet", "Tweet"),
                            ("factcheck", "Fact-check"),
                            ("context", "Kontekst"),
                            ("opinion", "Opinia"),
                        ],
                        db_index=True,
                        default="article",
                        max_length=32,
                        verbose_name="kategoria",
                    ),
                ),
                ("image_url", models.URLField(blank=True, max_length=1024, verbose_name="obraz")),
                ("is_premium", models.BooleanField(default=False, verbose_name="premium")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="articles",
                        to="news.source",
                        verbose_name="źródło",
                    ),
                ),
            ],
            options={"verbose_name": "artykuł", "verbose_name_plural": "artykuły", "ordering": ["-published_date"]},
        ),
        migrations.CreateModel(
            name="Thread",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255, verbose_name="tytuł")),
                ("slug", models.SlugField(max_length=255, unique=True, verbose_name="slug")),
                (
                    "thread_type",
                    models.CharField(
                        choices=[("factcheck", "Fact-check"), ("context", "Kontekst")],
                        db_index=True,
                        max_length=32,
                        verbose_name="typ wątku",
                    ),
                ),
                ("is_featured", models.BooleanField(default=False, verbose_name="wyróżniony")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "wątek", "verbose_name_plural": "wątki", "ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="ThreadItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("position", models.PositiveIntegerField(default=0, verbose_name="pozycja")),
                ("editorial_note", models.TextField(blank=True, verbose_name="notatka redakcyjna")),
                (
                    "article",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="thread_items",
                        to="news.article",
                        verbose_name="artykuł",
                    ),
                ),
                (
                    "thread",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="thread_items",
                        to="news.thread",
                        verbose_name="wątek",
                    ),
                ),
            ],
            options={
                "verbose_name": "pozycja wątku",
                "verbose_name_plural": "pozycje wątków",
                "ordering": ["position", "id"],
                "unique_together": {("thread", "article")},
            },
        ),
        migrations.AddField(
            model_name="thread",
            name="items",
            field=models.ManyToManyField(
                blank=True,
                related_name="threads",
                through="news.ThreadItem",
                to="news.article",
                verbose_name="pozycje",
            ),
        ),
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["published_date", "category"], name="news_articl_publish_idx"),
        ),
        migrations.AddIndex(
            model_name="article",
            index=models.Index(fields=["title"], name="news_articl_title_idx"),
        ),
    ]
