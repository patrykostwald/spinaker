from __future__ import annotations

from django.apps import AppConfig


class NewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "news"
    verbose_name = "Wiadomości"

    def ready(self):
        from news import signals  # noqa: F401
