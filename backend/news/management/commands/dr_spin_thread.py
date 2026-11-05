import json

from django.core.management.base import BaseCommand

from news.dr_spin_threads import build_daily_thread


class Command(BaseCommand):
    help = 'Buduje codzienną spinkę kontekstową Dr. Spina z materiałów Bazy.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Pokaż plan bez zapisu spinki.')

    def handle(self, *args, dry_run=False, **options):
        from news.features import threads_enabled, threads_disabled_result
        if not threads_enabled():
            self.stdout.write(str(threads_disabled_result()))
            return
        self.stdout.write(json.dumps(build_daily_thread(dry_run=dry_run), ensure_ascii=False, indent=2))
