"""Check explicit feeds for institutions whose initial probe found no channel."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connections
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news.models import ImportState, Source, SourceReviewDecision
from scraper.management.commands.source_review_queue import review_bucket
from scraper.source_channel_discovery import CHANNEL_DISCOVERY_VERSION, inspect_explicit_channel
from scraper.source_probe import ProbeNetwork, source_signature


def fresh(source, cursor):
    result = (cursor or {}).get('legal_channel_discovery') or {}
    checked_at = parse_datetime(result.get('checked_at') or '')
    return bool(result.get('version') == CHANNEL_DISCOVERY_VERSION
                and result.get('signature') == source_signature(source)
                and checked_at and timezone.is_aware(checked_at)
                and checked_at >= timezone.now() - timedelta(days=7))


def inspect(source, state):
    close_old_connections()
    try:
        try:
            result = inspect_explicit_channel(source, state, ProbeNetwork(delay=3))
        except Exception as exc:
            result = {'version': CHANNEL_DISCOVERY_VERSION, 'status': 'unavailable',
                      'pages_checked': [], 'channels': [], 'error': type(exc).__name__}
        result.update(checked_at=timezone.now().isoformat(), signature=source_signature(source))
        return source.pk, result
    finally:
        connections.close_all()


class Command(BaseCommand):
    help = ('Sprawdza tylko jawne RSS/Atom na stronach instytucji bez kanału w pierwszym audycie. '
            'Nie zgaduje endpointów, nie tworzy kart, nie aktywuje źródeł i nie pobiera materiałów.')

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=12)
        parser.add_argument('--workers', type=int, default=2)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--finalize-contact', action='store_true',
            help='Po kontroli zapisuje brak pełnej podstawy pobierania jako kontakt_required.')

    def handle(self, *args, **options):
        sources = list(Source.objects.filter(catalog_stage='candidate', is_active=False,
            scrape_enabled=False).order_by('pk'))
        states = dict(ImportState.objects.filter(name__in=[f'source-check:{source.pk}' for source in sources])
                      .values_list('name', 'cursor'))
        candidates = [source for source in sources if review_bucket(
            source, states.get(f'source-check:{source.pk}', {}) or {}) == '03_instytucja_bez_potwierdzonego_kanalu'
                      and (not getattr(source, 'review_decision', None)
                           or source.review_decision.decision != SourceReviewDecision.Decision.CONTACT_REQUIRED)]
        def needs_check(source):
            decision = getattr(source, 'review_decision', None)
            return (not fresh(source, states.get(f'source-check:{source.pk}', {}))
                    or (options['finalize_contact'] and decision
                        and decision.decision == SourceReviewDecision.Decision.CHANNEL_DISCOVERY))
        selected = [source for source in candidates if needs_check(source)][:max(1, min(options['limit'], 24))]
        if not selected:
            self.stdout.write(self.style.SUCCESS(
                f'INSTITUTION_CHANNEL_DISCOVERY: pending=0 checked={len(candidates)}/{len(candidates)}; no source was activated.'
            ))
            return
        results = {}
        with ThreadPoolExecutor(max_workers=max(1, min(options['workers'], 3))) as executor:
            futures = [executor.submit(inspect, source, states.get(f'source-check:{source.pk}', {})) for source in selected]
            for future in as_completed(futures):
                source_id, result = future.result()
                results[source_id] = result
                self.stdout.write(f'CHANNEL {source_id}: {result["status"]}')
        if options['finalize_contact'] and not options['apply']:
            self.stderr.write('finalize-contact wymaga apply.')
            return
        if options['apply']:
            for source in selected:
                cursor = dict(states.get(f'source-check:{source.pk}', {}) or {})
                cursor['legal_channel_discovery'] = results[source.pk]
                ImportState.objects.update_or_create(name=f'source-check:{source.pk}', defaults={
                    'cursor': cursor, 'last_error': '',
                })
                if options['finalize_contact']:
                    result = results[source.pk]
                    if result['status'] == 'working_channel_requires_editorial_card_review':
                        reason = ('Znaleziono jawny kanał, ale nie ma jeszcze zapisanej podstawy ponownego '
                                  'wykorzystania ani zatwierdzonej karty dostępu dla tego kanału.')
                    else:
                        reason = ('Kontrola strony i jawnych odsyłaczy nie potwierdziła działającego kanału '
                                  'RSS/API z podstawą pobierania metadanych.')
                    SourceReviewDecision.objects.update_or_create(source=source, defaults={
                        'decision': SourceReviewDecision.Decision.CONTACT_REQUIRED,
                        'reason': reason,
                        'evidence_urls': [source.url],
                        'audit_snapshot': result,
                        'reviewed_by': 'automated-institution-channel-check',
                        'is_automated': True,
                    })
        counts = {}
        for result in results.values():
            counts[result['status']] = counts.get(result['status'], 0) + 1
        summary = ' '.join(f'{key}={value}' for key, value in sorted(counts.items()))
        self.stdout.write(self.style.SUCCESS(
            f'INSTITUTION_CHANNEL_DISCOVERY: processed={len(selected)} pending={len(candidates) - len(selected)} '
            f'{summary}; finalized_contact={int(options["finalize_contact"])}; no source was activated.'
        ))
