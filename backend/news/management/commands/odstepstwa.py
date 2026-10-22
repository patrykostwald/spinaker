"""Odstępstwa od klubu w głosowaniach Sejmu: przelicza wynik i pokazuje, ilu posłów i głosów wbrew klubowi wychodzi."""
from django.core.management.base import BaseCommand

from news import voting_anomalies


class Command(BaseCommand):
    help = 'Przelicza odstępstwa posłów od większości klubu (cała kadencja i ostatnie 90 dni).'

    def add_arguments(self, parser):
        parser.add_argument('--term', type=int, default=None, help='Kadencja (domyślnie najnowsza w bazie).')

    def handle(self, *args, term=None, **options):
        result = voting_anomalies.refresh(term)
        self.stdout.write(str(result))
        snap = voting_anomalies.snapshot(result.get('term'), '90d') or voting_anomalies.snapshot(result.get('term'), 'term')
        for club in (snap.data['clubs'] if snap else []):
            self.stdout.write(f"{club['club']}: posłów {club['mps']}, mediana {club['median']} %, wyróżnieni {len(club['flagged'])}, "
                              f"głosy wbrew klubowi {club['rebellions_total']}")
