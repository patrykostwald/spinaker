from django.apps import AppConfig


class ScraperConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scraper"
    verbose_name = "Scrapery"

    def ready(self):
        # Warunki zgody RCL (okno 01:00-06:00, User-Agent, wstrzymanie po 429/503) obowiązują każde zapytanie do tego hosta.
        from scraper.rcl_guard import install_requests_guard
        install_requests_guard()
