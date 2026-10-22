from django.core.management.base import BaseCommand, CommandError

from news.raportysta import request_sample, step
from news.report_models import REPORT_TYPES


class Command(BaseCommand):
    help = 'Przygotowuje bezpłatny przykład do recenzji i zatwierdzenia. Bez wysyłki.'

    def add_arguments(self, parser):
        parser.add_argument('--type', required=True, choices=[key for key, _ in REPORT_TYPES])
        parser.add_argument('--audience', required=True)
        parser.add_argument('--figure-id', type=int)
        parser.add_argument('--topic', default='')

    def handle(self, *args, **options):
        scope = {key: options[key] for key in ('figure_id', 'topic') if options.get(key)}
        try:
            report = request_sample(options['type'], options['audience'], scope)
            # Same protections as the scheduled task; unfinished work resumes next night.
            for _ in range(45):
                if step(report.pk) not in ('working', 'queued'):
                    break
            report.refresh_from_db()
        except ValueError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f'Raport {report.pk}: {report.get_status_display()}. Panel: /admin/news/institutionalreport/{report.pk}/change/')
        for missing in report.gate.get('missing', []):
            self.stdout.write(missing)
