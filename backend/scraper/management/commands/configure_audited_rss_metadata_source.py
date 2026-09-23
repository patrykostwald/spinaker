"""Turn one freshly audited RSS channel into a reviewed metadata-only source."""
from datetime import timedelta
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import ImportState, Source, SourceAccessInstruction
from scraper.source_probe import source_signature


class Command(BaseCommand):
    help = 'Włącza wyłącznie świeżo zweryfikowany RSS po zapisaniu warunków wykorzystania.'

    def add_arguments(self, parser):
        selector = parser.add_mutually_exclusive_group(required=True)
        selector.add_argument('--source-id', type=int)
        selector.add_argument('--source-host')
        parser.add_argument('--terms-url', required=True)
        parser.add_argument('--evidence-note', required=True)
        parser.add_argument('--reviewed-by', default='redakcja spin.clinic')
        parser.add_argument('--daily-cap', type=int, default=24)
        parser.add_argument('--valid-days', type=int, default=180)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if not 1 <= options['daily_cap'] <= 1000 or not 1 <= options['valid_days'] <= 730:
            raise CommandError('daily-cap musi wynosić 1..1000, a valid-days 1..730.')
        with transaction.atomic():
            if options.get('source_host'):
                host = options['source_host'].strip().lower().removeprefix('www.')
                matches = []
                for candidate in Source.objects.select_for_update().filter(is_active=False):
                    candidate_host = urlsplit(candidate.url).hostname or ''
                    if candidate_host.lower().removeprefix('www.') == host:
                        matches.append(candidate)
                if len(matches) != 1:
                    raise CommandError(
                        f'Host musi wskazywać dokładnie jedno nieaktywne źródło; znaleziono {len(matches)}.')
                source = matches[0]
            else:
                source = Source.objects.select_for_update().filter(pk=options['source_id']).first()
            if source is None:
                raise CommandError('Nie znaleziono źródła.')
            now = timezone.now()
            latest = SourceAccessInstruction.objects.filter(source=source).order_by('-version').first()
            if latest and latest.status == SourceAccessInstruction.Status.SUSPENDED:
                raise CommandError('Najnowsza karta jest wstrzymana; wymaga osobnej kontroli redakcyjnej.')
            # A successful first run deliberately changes rss_url and catalog_stage,
            # so the old candidate-audit signature must not make a repeated start
            # fail. A still-valid exact card is the durable proof for that no-op.
            existing = SourceAccessInstruction.objects.filter(
                source=source, status=SourceAccessInstruction.Status.APPROVED,
                channel=SourceAccessInstruction.Channel.RSS,
                allowed_scope=SourceAccessInstruction.Scope.METADATA,
                endpoint=source.rss_url, terms_url=options['terms_url'], valid_until__gt=now,
            ).order_by('-version').first()
            if existing and source.catalog_stage == 'configured' and source.is_active and source.scrape_enabled:
                self.stdout.write(self.style.SUCCESS(
                    f'GOTOWE: {source.pk} {source.name}; użyto istniejącej RSS karty v{existing.version}.'))
                return
            state = ImportState.objects.filter(name=f'source-check:{source.pk}').first()
            result = dict(state.cursor) if state else {}
            rss = result.get('rss') or {}
            fresh = state and state.last_success and state.last_success >= timezone.now() - timedelta(days=1)
            if not (fresh and result.get('signature') == source_signature(source)
                    and result.get('audit_status') == 'completed'
                    and rss.get('status') == 'working' and rss.get('url')
                    and rss.get('usable_entry_count')):
                raise CommandError('Brak świeżego, działającego audytu RSS dla tego źródła.')
            feed_url = rss['url']
            parsed = urlsplit(feed_url)
            if parsed.scheme != 'https' or not parsed.hostname:
                raise CommandError('Audyt nie zwrócił bezpiecznego adresu HTTPS RSS.')
            if not options['apply']:
                self.stdout.write(f'PLAN: {source.name}; RSS {feed_url}; wyłącznie metadane.')
                return
            card = SourceAccessInstruction.objects.filter(
                source=source, status=SourceAccessInstruction.Status.APPROVED,
                channel=SourceAccessInstruction.Channel.RSS,
                allowed_scope=SourceAccessInstruction.Scope.METADATA,
                endpoint=feed_url, terms_url=options['terms_url'], valid_until__gt=now,
            ).order_by('-version').first()
            if card is None:
                card = SourceAccessInstruction.objects.create(
                    source=source, version=(latest.version if latest else 0) + 1,
                    status=SourceAccessInstruction.Status.APPROVED,
                    channel=SourceAccessInstruction.Channel.RSS,
                    allowed_scope=SourceAccessInstruction.Scope.METADATA,
                    endpoint=feed_url, allowed_path_patterns=[parsed.path or '/'],
                    terms_url=options['terms_url'],
                    evidence={'audit_checked_at': result.get('checked_at'), 'rss_url': feed_url,
                              'terms_url': options['terms_url'], 'review_note': options['evidence_note'],
                              'scope': 'RSS title, URL, date and feed summary only; no article HTML, images, PDFs, video or full-text snapshot.'},
                    minimum_interval_seconds=3, daily_request_cap=options['daily_cap'],
                    reviewed_at=now, reviewed_by=options['reviewed_by'],
                    valid_until=now + timedelta(days=options['valid_days']),
                )
            source.rss_url = feed_url
            source.is_active = source.scrape_enabled = True
            source.catalog_stage = 'configured'
            source.full_clean()
            source.save()
        self.stdout.write(self.style.SUCCESS(f'GOTOWE: {source.pk} {source.name}; RSS karta v{card.version}.'))
