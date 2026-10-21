"""Wpisuje zgodę RCL (pismo RCL.DPK.053.168.2026 z 21.10.2026) jako źródło i kartę dostępu zbieracza legislacja.rcl.gov.pl."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Source, SourceAccessInstruction
from scraper import rcl_guard
from scraper.rcl_harvest import SOURCE_NAME, SOURCE_URL

TERMS_URL = 'https://bip.rcl.gov.pl/rcl/ponowne-wykorzystywanie/3122,dok.html'
LETTER = 'RCL.DPK.053.168.2026'
LETTER_DATE = '2026-10-21'
# 5 s odstępu w oknie 5 godzin to najwyżej 3600 zapytań; karta nie pozwala na więcej niż fizyczne maksimum nocy.
DAILY_CAP = 3600


def configure(reviewer):
    now = timezone.now()
    source, _ = Source.objects.get_or_create(
        url=SOURCE_URL,
        defaults={'name': SOURCE_NAME, 'source_type': 'institution',
                  'is_active': False, 'scrape_enabled': False, 'catalog_stage': 'candidate'})
    card = SourceAccessInstruction.objects.filter(
        source=source, status=SourceAccessInstruction.Status.APPROVED,
        channel=SourceAccessInstruction.Channel.HTML, endpoint=SOURCE_URL,
        terms_url=TERMS_URL, valid_until__gt=now, evidence__letter_signature=LETTER).order_by('-version').first()
    if card is None:
        latest = SourceAccessInstruction.objects.filter(source=source).order_by('-version').first()
        card = SourceAccessInstruction(
            source=source, version=(latest.version if latest else 0) + 1,
            status=SourceAccessInstruction.Status.APPROVED,
            channel=SourceAccessInstruction.Channel.HTML,
            allowed_scope=SourceAccessInstruction.Scope.METADATA,
            endpoint=SOURCE_URL, allowed_path_patterns=[], terms_url=TERMS_URL,
            evidence={
                'basis': f'Pismo RCL {LETTER} z {LETTER_DATE}: zgoda na automatyczne pobieranie stron serwisu pod warunkami.',
                'letter_signature': LETTER,
                'letter_date': LETTER_DATE,
                'request': 'deploy/poczta-wychodzaca/04-rcl-wniosek-dane.md',
                'conditions': [
                    'najwyżej 1 zapytanie na 5 sekund',
                    'tylko 01:00-06:00 czasu polskiego',
                    'User-Agent: ' + rcl_guard.RCL_USER_AGENT,
                    'po HTTP 429 lub 503 przerwanie do następnej nocy, bez ponawiania',
                    'przy publikacji: ' + rcl_guard.SOURCE_LINE + ', link do strony projektu i data pobrania',
                    'tylko z serwera zgłoszonego do RCL (148.113.242.109)',
                ],
                'scope': 'Metadane i linki do plików; pobieranie samych plików wyłącznie osobnym krokiem RCL_FILES_ENABLED, po potwierdzeniu zakresu.',
                'attribution': rcl_guard.SOURCE_LINE,
            },
            minimum_interval_seconds=rcl_guard.RCL_MIN_INTERVAL_SECONDS, daily_request_cap=DAILY_CAP,
            reviewed_at=now, reviewed_by=reviewer[:120], valid_until=now + timedelta(days=180))
        card.full_clean()
        card.save()
    source.name = SOURCE_NAME
    source.source_type = 'institution'
    source.is_active = source.scrape_enabled = True
    source.catalog_stage = 'configured'
    source.full_clean()
    source.save()
    return source, card


class Command(BaseCommand):
    help = 'Konfiguruje źródło RCL (karta dostępu z pisma 21.10.2026); sama karta niczego nie pobiera, potrzebne jest RCL_FETCH_ENABLED.'

    def add_arguments(self, parser):
        parser.add_argument('--reviewed-by', default='właściciel, zgoda RCL ' + LETTER)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if not options['apply']:
            self.stdout.write(f'PLAN: źródło {SOURCE_URL}, karta HTML (metadane), odstęp 5 s, limit {DAILY_CAP}/dobę, '
                              f'ważna 180 dni, dowód: pismo {LETTER} z {LETTER_DATE}. Bez --apply nie zmieniam bazy.')
            return
        source, card = configure(options['reviewed_by'])
        self.stdout.write(self.style.SUCCESS(
            f'GOTOWE: źródło {source.pk}, karta v{card.version}; zbieracz działa dopiero po RCL_FETCH_ENABLED=true na serwerze 148.113.242.109.'))
