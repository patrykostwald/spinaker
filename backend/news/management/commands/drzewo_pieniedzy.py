"""Drzewo przepływu pieniędzy (właściciel 6.10): identyfikatory podmiotów z KRS i stan powiązań.

Przykłady:
  python manage.py drzewo_pieniedzy --plan                      # bez sieci: ile podmiotów nie ma jeszcze NIP
  python manage.py drzewo_pieniedzy --identyfikatory --limit 200 # NIP i REGON z oficjalnego API KRS (OdpisAktualny), idempotentne
  python manage.py drzewo_pieniedzy --stan                       # bez sieci: ile rekordów TED, BZP, FTS, Kohesio czeka na drzewa

Zamówienia i dotacje łączymy tylko po identyfikatorach, więc bez NIP drzewo podmiotu pokaże tylko osoby z KRS
i rekordy „niepowiązane”. Podmioty z już wpisanym NIP są pomijane; błąd jednego podmiotu nie zatrzymuje reszty.
"""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from news import krs
from news.political_models import RegisteredOrganisation
from news.public_records_models import PublicRecord


class Command(BaseCommand):
    help = 'Drzewo przepływu pieniędzy: NIP i REGON podmiotów z KRS oraz stan danych o zamówieniach i dotacjach.'

    def add_arguments(self, parser):
        parser.add_argument('--plan', action='store_true', help='Tylko policz, bez sieci i bez zapisu.')
        parser.add_argument('--identyfikatory', action='store_true', help='Pobierz NIP i REGON z API KRS dla podmiotów bez NIP.')
        parser.add_argument('--stan', action='store_true', help='Stan rekordów TED, BZP, FTS i Kohesio w bazie (bez sieci).')
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--pauza', type=float, default=0.5, help='Sekundy między zapytaniami do API KRS.')

    def handle(self, *args, plan, identyfikatory, stan, limit, pauza, **options):
        orgs = RegisteredOrganisation.objects.filter(archived=False)
        missing = orgs.filter(nip='').order_by('pk')
        self.stdout.write(f'podmioty z KRS: {orgs.count()}, z NIP: {orgs.exclude(nip="").count()}, bez NIP: {missing.count()}')
        if identyfikatory and not plan:
            done = failed = 0
            for org in missing[:limit]:
                extract = krs.fetch(org.krs_number, full=False)
                if extract is None or not (extract.nip or extract.regon):
                    failed += 1
                else:
                    RegisteredOrganisation.objects.filter(pk=org.pk).update(
                        **{k: v for k, v in (('nip', extract.nip), ('regon', extract.regon)) if v}, source_checked_at=timezone.now())
                    done += 1
                time.sleep(max(0.0, pauza))
            self.stdout.write(f'uzupełnione: {done}, bez identyfikatorów w odpisie albo bez odpowiedzi: {failed}')
        if stan or plan:
            counts = {label: PublicRecord.objects.filter(source=source, kind=kind).count() for label, source, kind in (
                ('ogłoszenia TED', 'ted', 'notice'), ('ogłoszenia BZP', 'bzp', 'notice'),
                ('wiersze FTS', 'fts', 'eu_grant'), ('projekty Kohesio', 'kohesio', 'eu_project'))}
            self.stdout.write('rekordy w bazie: ' + ', '.join(f'{k} {v}' for k, v in counts.items()))
            by_name = PublicRecord.objects.filter(kind__in=('eu_project', 'eu_grant'), data__has_key='organisation_id').count()
            self.stdout.write(f'dotacje dopasowane przez zbieracz po nazwie (w drzewie jako „niepowiązane”): {by_name}')
