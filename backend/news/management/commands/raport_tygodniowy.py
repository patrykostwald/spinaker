"""python manage.py raport_tygodniowy [--dzien 2026-10-12] [--od-nowa] [--zapisz katalog]

Liczy Raport tygodniowy dla instytucji za tydzień poprzedzający podany dzień (domyślnie: dziś) i opcjonalnie zapisuje
PDF i CSV do katalogu. Bez AI i bez wysyłki."""
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from news.raport_tygodniowy import generate


class Command(BaseCommand):
    help = 'Raport tygodniowy dla instytucji (PDF + CSV) za poprzedni pełny tydzień. Bez wysyłki.'

    def add_arguments(self, parser):
        parser.add_argument('--dzien', type=date.fromisoformat)
        parser.add_argument('--od-nowa', action='store_true')
        parser.add_argument('--zapisz', default='')

    def handle(self, *args, **options):
        from news.sales_models import WeeklyReportIssue
        result = generate(options['dzien'], force=options['od_nowa'])
        issue = WeeklyReportIssue.objects.get(pk=result['issue'])
        self.stdout.write(f"{issue}: {issue.get_status_display()}, wypowiedzi: {(issue.data or {}).get('total', 0)}")
        if options['zapisz'] and issue.pdf:
            out = Path(options['zapisz'])
            out.mkdir(parents=True, exist_ok=True)
            (out / f'raport-tygodniowy-{issue.week_start}.pdf').write_bytes(bytes(issue.pdf))
            (out / f'raport-tygodniowy-{issue.week_start}.csv').write_bytes(bytes(issue.csv))
            self.stdout.write(f'Zapisano w {out}')
