"""Wspólny przekaz: szuka prawie identycznych wpisów z co najmniej 3 kont w 6 godzin i pokazuje, co wyszło."""
from django.core.management.base import BaseCommand

from news import coordinated


class Command(BaseCommand):
    help = 'Przelicza klastry wspólnego przekazu z wpisów polityków na X.'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=coordinated.LOOKBACK_HOURS, help='Ile godzin wstecz (domyślnie 48).')

    def handle(self, *args, hours=None, **options):
        from news.analysis_models import CoordinatedCluster
        self.stdout.write(str(coordinated.refresh(hours=hours)))
        for c in CoordinatedCluster.objects.order_by('-first_at')[:10]:
            kind = 'międzypartyjny' if c.cross_party else 'jedna partia lub bez partii'
            self.stdout.write(f'{c.first_at:%d.%m %H:%M} · {c.accounts_count} kont · {kind} · {", ".join(c.parties) or "-"} · {c.phrase[:90]}')
