from django.core.management.base import BaseCommand, CommandError

from scraper.archive import run_batch
from scraper.gov_justice_archive import InvalidGovArticleLink, discover
from scraper.utils import HostRateLimited


class Command(BaseCommand):
    help = "Odkrywa komunikaty wskazanej jednostki gov.pl i pobiera je przez bramkę archiwum."

    def add_arguments(self, parser):
        parser.add_argument("--source-id", type=int, required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        if not 1 <= options["limit"] <= 24:
            raise CommandError("limit musi być w zakresie 1..24")
        if not options["apply"]:
            self.stdout.write("PLAN: bez --apply nie wykonuję żądań ani nie tworzę kolejki.")
            return
        try:
            found = discover(options["source_id"])
        except HostRateLimited as exc:
            self.stdout.write(
                f"ODROCZONE: wspólny limit hosta; ponów po {exc.retry_after_seconds:.1f} s."
            )
            return
        except InvalidGovArticleLink as exc:
            self.stdout.write("WYMAGA_NAPRAWY_ADAPTERA: " + ", ".join(exc.links))
            return
        metrics = {}
        completed = run_batch(limit=options["limit"], source_ids=[options["source_id"]],
            per_source_limit=options["limit"], metrics=metrics)
        self.stdout.write(
            f"ODKRYTO={found['queued']} UKOŃCZONO={completed} "
            f"NOWE={metrics['new_articles']} BŁĘDY={metrics['failed_jobs']}"
        )
