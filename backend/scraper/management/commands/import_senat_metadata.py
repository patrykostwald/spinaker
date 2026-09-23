from django.core.management.base import BaseCommand, CommandError

from scraper.archive import run_batch
from scraper.senat_archive import discover_senat


class Command(BaseCommand):
    help = "Jednorazowo odkrywa i zapisuje metadane własnych aktualności Senatu."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 20:
            raise CommandError("limit musi być w zakresie 1..20")
        if not options["apply"]:
            self.stdout.write("PLAN: bez --apply nie wykonuję żądań ani nie tworzę rekordów.")
            return
        found = discover_senat()
        if found["status"] != "ok":
            self.stdout.write(str(found))
            return
        metrics = {}
        completed = run_batch(limit=options["limit"], source_ids=[found["source_id"]],
                              per_source_limit=options["limit"], metrics=metrics)
        self.stdout.write(f"ODKRYTO={found['queued']} UKOŃCZONO={completed} NOWE={metrics['new_articles']} BŁĘDY={metrics['failed_jobs']}")
