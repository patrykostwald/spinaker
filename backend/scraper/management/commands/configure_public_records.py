"""Explicit owner-reviewed source cards. Planning and applying perform no I/O."""
from datetime import timedelta
import os
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import Source, SourceAccessInstruction
from scraper.public_records import SOURCES, API, SEJM, MSWIA, LOBBY, PKW, KRS_API, TED_SEARCH, TR_EXPORT
from scraper import nowe_zrodla as nz

# Zbiory organizacji pozarządowych i społeczności (nie urzędów): typ katalogu 'portal'.
PORTALS = {'meta_ads', 'howtheyvote', 'wikidata', 'integrity_watch', 'mileage'}


def cards(source):
    """(catalogue URL, channel, endpoint, scope, paths). No broad host approval."""
    sejm = API + '/sejm'
    web = 'https://www.sejm.gov.pl'
    if source == 'votes':
        return [(sejm, 'api', SEJM + '/votings', 'content', [
            '/sejm/term10/votings/search', '/sejm/term10/votings/{int}/{int}'])]
    if source == 'statements':
        return [(sejm, 'api', SEJM + '/proceedings', 'content', [
            '/sejm/term10/proceedings', '/sejm/term10/proceedings/{int}/{token}/transcripts',
            '/sejm/term10/proceedings/{int}/{token}/transcripts/{int}'])]
    if source in {'interpellations', 'questions'}:
        resource = 'interpellations' if source == 'interpellations' else 'writtenQuestions'
        return [(sejm, 'api', SEJM + '/' + resource, 'metadata', ['/sejm/term10/' + resource])]
    if source == 'assets':
        return [(sejm, 'api', SEJM + '/MP', 'metadata', ['/sejm/term10/MP']),
                (web, 'html', web + '/sejm10.nsf/posel.xsp', 'metadata', []),
                (web, 'html', web + '/Sejm10.nsf/posel.xsp', 'metadata', [])]
    if source == 'consultations':
        # Filenames can contain dots/spaces, which the access gate's {token}
        # placeholder intentionally cannot represent. Restrict to prints subtree.
        return [(sejm, 'api', SEJM + '/prints', 'content', [])]
    if source == 'lobby_mswia':
        root = 'https://www.gov.pl/web/mswia'
        return [(root, 'html', MSWIA, 'metadata', []),
                (root, 'html', 'https://www.gov.pl/attachment', 'content', ['/attachment/{token}'])]
    if source == 'lobby_sejm':
        return [(web, 'html', LOBBY, 'metadata', []),
                (web, 'html', web + '/sejm10.nsf/lobbing_osoby_tab.xsp', 'metadata', [])]
    if source == 'pkw':
        return [('https://pkw.gov.pl', 'html', PKW.rstrip('/'), 'metadata', []),
                ('https://pkw.gov.pl', 'html', 'https://pkw.gov.pl/uploaded_files', 'metadata', [])]
    if source == 'processes':
        return [(sejm, 'api', SEJM + '/processes', 'metadata', [
            '/sejm/term10/processes', '/sejm/term10/processes/{token}'])]
    if source == 'committees':
        return [(sejm, 'api', SEJM + '/committees', 'metadata', [
            '/sejm/term10/committees', '/sejm/term10/committees/{token}/sittings'])]
    if source == 'krs_changes':
        return [('https://api-krs.ms.gov.pl', 'api', KRS_API, 'metadata', [
            '/api/krs/Biuletyn/{token}', '/api/krs/OdpisAktualny/{token}'])]
    if source == 'ted':
        return [('https://api.ted.europa.eu', 'api', TED_SEARCH, 'metadata', [])]
    if source == 'eu_transparency':
        return [('https://ec.europa.eu/transparencyregister', 'export', TR_EXPORT.rsplit('/', 1)[0], 'metadata', [])]
    if source == 'videos':
        # Lista transmisji i zapis przebiegu posiedzenia komisji (tekst urzędowy; nagrań nie pobieramy).
        return [(sejm, 'api', SEJM + '/videos', 'metadata', ['/sejm/term10/videos']),
                (sejm, 'api', SEJM + '/committees', 'content', ['/sejm/term10/committees/{token}/sittings/{int}/html'])]
    if source == 'howtheyvote':
        return [('https://howtheyvote.eu', 'api', nz.HTV, 'metadata', ['/api/votes', '/api/votes/{int}'])]
    if source == 'wikidata':
        return [('https://query.wikidata.org', 'api', nz.WIKIDATA, 'metadata', ['/sparql'])]
    if source == 'kohesio':
        return [('https://cohesiondata.ec.europa.eu', 'api', nz.KOHESIO, 'metadata', [])]
    if source == 'fts':
        root = 'https://ec.europa.eu/budget/financial-transparency-system'
        return [(root, 'export', root + '/download', 'metadata', [])]
    if source == 'integrity_watch':
        root = 'https://www.integritywatch.eu'
        return [(root, 'export', nz.IW + 'meps/dpi_legislature_10', 'metadata', []),
                (root, 'export', nz.IW + 'mepmeetings/legislature_10', 'metadata', [])]
    if source == 'mileage':
        return [('https://jakglosuja.pl', 'api', nz.JAKGLOSUJA.rstrip('/'), 'metadata',
                 ['/api/eksport/kilometrowki', '/api/eksport/sprawozdania']),
                ('https://orka.sejm.gov.pl', 'export', 'https://orka.sejm.gov.pl/rozlicz10.nsf', 'metadata', [])]
    if source == 'meta_ads':
        version = os.environ.get('META_AD_LIBRARY_API_VERSION', '')
        if not re.fullmatch(r'v\d+\.0', version):
            raise CommandError('Ustaw META_AD_LIBRARY_API_VERSION na wersję potwierdzoną w aplikacji Meta.')
        return [('https://graph.facebook.com', 'api', f'https://graph.facebook.com/{version}/ads_archive', 'content', [])]
    raise CommandError('Nieznane źródło.')


class Command(BaseCommand):
    help = 'Plan lub zapis wąskich kart dostępu zbieracza; bez HTTP i bez włączania flag.'

    def add_arguments(self, parser):
        parser.add_argument('--source', choices=tuple(SOURCES), required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--reviewed-by')
        parser.add_argument('--evidence-url')
        parser.add_argument('--terms-url')
        parser.add_argument('--daily-cap', type=int, default=100)
        parser.add_argument('--valid-days', type=int, default=30)

    @transaction.atomic
    def handle(self, *args, **options):
        if not 1 <= options['daily_cap'] <= 10000 or not 1 <= options['valid_days'] <= 365:
            raise CommandError('daily-cap: 1–10000; valid-days: 1–365.')
        from scraper.public_record_parsers import public_url
        if options['apply']:
            if not all(options[k] for k in ('reviewed_by', 'evidence_url', 'terms_url')):
                raise CommandError('--apply wymaga --reviewed-by, --evidence-url i --terms-url.')
            for key in ('evidence_url', 'terms_url'):
                try:
                    public_url(options[key])
                except ValueError as exc:
                    raise CommandError('Wymagany publiczny URL HTTPS.') from exc
        spec = SOURCES[options['source']]
        for root, channel, endpoint, scope, paths in cards(options['source']):
            self.stdout.write(f'{channel} {endpoint}; {scope}; {options["daily_cap"]}/dobę; odstęp 3 s')
            if not options['apply']:
                continue
            provider, _ = Source.objects.get_or_create(url=root, defaults={
                'name': spec.title, 'source_type': 'portal' if options['source'] in PORTALS else 'institution',
                'is_active': False, 'scrape_enabled': False})
            provider = Source.objects.select_for_update().get(pk=provider.pk)
            if provider.catalog_stage == 'excluded':
                raise CommandError('Źródło wykluczone; wymaga osobnej zmiany decyzji w katalogu.')
            newest_endpoint = provider.access_instructions.filter(channel=channel, endpoint=endpoint).order_by('-version').first()
            if newest_endpoint and newest_endpoint.status in {'suspended', 'contact_required', 'rejected'}:
                raise CommandError('Nie nadpisuję wstrzymanej/odrzuconej karty dostępu.')
            latest = provider.access_instructions.order_by('-version').first()
            now = timezone.now()
            SourceAccessInstruction.objects.create(source=provider, version=(latest.version if latest else 0) + 1,
                status='approved', channel=channel, endpoint=endpoint, allowed_scope=scope,
                allowed_path_patterns=paths, terms_url=options['terms_url'],
                evidence={'documentation_url': options['evidence_url'], 'collector': options['source'],
                          'scope': 'Private public-record analysis only; no OCR, AI or public redistribution.'},
                reviewed_by=options['reviewed_by'], reviewed_at=now,
                valid_until=now + timedelta(days=options['valid_days']),
                daily_request_cap=options['daily_cap'], minimum_interval_seconds=3)
            provider.is_active = provider.scrape_enabled = True
            provider.catalog_stage = 'configured'
            provider.save(update_fields=['is_active', 'scrape_enabled', 'catalog_stage'])
        self.stdout.write('Flaga zbieracza pozostaje do ustawienia w środowisku: ' + spec.flag(options['source']))
