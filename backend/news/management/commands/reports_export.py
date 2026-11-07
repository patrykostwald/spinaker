from pathlib import Path

from django.core.management.base import BaseCommand

from news import raportysta, report_data
from news.report_models import InstitutionalReport


class Command(BaseCommand):
    help = 'Zapisuje gotowe raporty (PDF, CSV, metoda) do katalogu - te same warunki co pobranie w panelu. Bez wysyłki.'

    def add_arguments(self, parser):
        parser.add_argument('--dir', default='/tmp/raporty')

    def handle(self, *args, **options):
        out = Path(options['dir'])
        out.mkdir(parents=True, exist_ok=True)
        saved = 0
        for report in InstitutionalReport.objects.order_by('pk'):
            ready = (report.status in ('awaiting_approval', 'approved') and report.pdf
                     and raportysta.artifact_fingerprint(report) == report.artifact_hash
                     and report_data.sources_current(report.snapshot))
            if not ready:
                self.stdout.write(f'{report.pk} {report.kind} {report.audience}: {report.get_status_display()} - bez pliku')
                continue
            base = f'raport-{report.pk}-{report.kind}-{report.audience}'
            (out / f'{base}.pdf').write_bytes(bytes(report.pdf))
            if report.csv:
                (out / f'{base}.csv').write_bytes(bytes(report.csv) if not isinstance(report.csv, str) else report.csv.encode('utf-8'))
            if report.method:
                (out / f'{base}-metoda.txt').write_text(str(report.method), encoding='utf-8')
            saved += 1
            self.stdout.write(f'{report.pk} {report.kind} {report.audience}: {report.get_status_display()} - zapisano {base}.pdf')
        self.stdout.write(f'Zapisane raporty: {saved}, katalog: {out}')
