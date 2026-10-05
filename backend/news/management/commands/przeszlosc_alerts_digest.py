import json

from django.core.management.base import BaseCommand

from news.przeszlosc_alerts import send_digests


class Command(BaseCommand):
    help = 'Dzienny list alertów przeszłość.today (to samo co zadanie o 7:00). --dry-run pokazuje treść bez wysyłki.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        report = send_digests(dry_run=options['dry_run'])
        preview = report.pop('preview', '')
        self.stdout.write(json.dumps(report, ensure_ascii=False))
        if preview:
            self.stdout.write('\n--- przykład listu ---\n' + preview)
