from django.apps import AppConfig


class TerazConfig(AppConfig):
    name = "teraz"
    verbose_name = "Teraz"

    def ready(self):
        from . import cache  # noqa: F401
