"""Configure the audited official BZP API as a bounded metadata-only source."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Source, SourceAccessInstruction
from scraper.bzp_backfill import SEARCH_URL, SOURCE_URL

TERMS_URL = 'https://ezamowienia.gov.pl/pl/regulamin/'
DOCS_URL = 'https://edu.ezamowienia.gov.pl/pl/integracja/'
DAILY_CAP = 480


def configure(reviewer):
    source, _ = Source.objects.get_or_create(
        url=SOURCE_URL,
        defaults={'name': 'Biuletyn Zamówień Publicznych', 'source_type': 'institution',
                  'is_active': False, 'scrape_enabled': False, 'catalog_stage': 'candidate'},
    )
    now = timezone.now()
    card = SourceAccessInstruction.objects.filter(
        source=source, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.API,
        allowed_scope=SourceAccessInstruction.Scope.METADATA,
        endpoint=SEARCH_URL, terms_url=TERMS_URL, valid_until__gt=now,
    ).order_by('-version').first()
    if card is None:
        latest = SourceAccessInstruction.objects.filter(source=source).order_by('-version').first()
        card = SourceAccessInstruction.objects.create(
            source=source, version=(latest.version if latest else 0) + 1,
            status=SourceAccessInstruction.Status.APPROVED,
            channel=SourceAccessInstruction.Channel.API,
            allowed_scope=SourceAccessInstruction.Scope.METADATA,
            endpoint=SEARCH_URL, allowed_path_patterns=['/mo-board/api/v1/Board/Search'],
            terms_url=TERMS_URL,
            evidence={
                'documentation_url': DOCS_URL,
                'scope': 'BZP notice number, title, publication date and direct record link only; no notice full text, files, images or participant data.',
                'rate_limit': 'One request at least every three minutes; 480 requests per day maximum.',
                'attribution': 'Keep the official BZP record link and acquisition time on every box.',
            },
            minimum_interval_seconds=180, daily_request_cap=DAILY_CAP,
            reviewed_at=now, reviewed_by=reviewer, valid_until=now + timedelta(days=180),
        )
    source.name = 'Biuletyn Zamówień Publicznych'
    source.source_type = 'institution'
    source.is_active = source.scrape_enabled = True
    source.catalog_stage = 'configured'
    source.full_clean()
    source.save()
    return source, card


class Command(BaseCommand):
    help = 'Konfiguruje BZP jako oficjalne źródło metadanych ogłoszeń, domyślnie bez uruchamiania adaptera.'

    def add_arguments(self, parser):
        parser.add_argument('--reviewed-by', default='redakcja spin.clinic')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if not options['apply']:
            self.stdout.write('PLAN: BZP API; tytuł, numer, data i link, maksymalnie 480 żądań/dobę. Bez --apply nie zmieniam bazy.')
            return
        source, card = configure(options['reviewed_by'])
        self.stdout.write(self.style.SUCCESS(
            f'GOTOWE: {source.pk} {source.name}; API karta v{card.version}; adapter wymaga BZP_API_ENABLED=true.'))
