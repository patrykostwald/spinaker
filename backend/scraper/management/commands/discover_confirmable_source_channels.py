"""Find exact RSS/Atom channels for the small confirmation queue."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connections
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news.models import ImportState, Source
from scraper.management.commands.source_resolution_matrix import outcome
from scraper.management.commands.source_review_queue import hostname
from scraper.source_channel_discovery import CHANNEL_DISCOVERY_VERSION, inspect_explicit_channel
from scraper.source_probe import ProbeNetwork, source_signature


def worker(source, state, network):
    close_old_connections()
    try:
        try:
            result = inspect_explicit_channel(source, state, network)
        except Exception as exc:
            result = {'version': CHANNEL_DISCOVERY_VERSION, 'status': 'unavailable',
                      'pages_checked': [], 'channels': [], 'error': type(exc).__name__}
        result.update(checked_at=timezone.now().isoformat(), signature=source_signature(source))
        return source.pk, result
    finally:
        connections.close_all()


def is_fresh(source, state):
    result = (state or {}).get('legal_channel_discovery') or {}
    checked = parse_datetime(result.get('checked_at') or '')
    return bool(result.get('version') == CHANNEL_DISCOVERY_VERSION
                and result.get('signature') == source_signature(source)
                and checked and timezone.is_aware(checked)
                and checked >= timezone.now() - timedelta(days=1))


class Command(BaseCommand):
    help = ('Sprawdza wyłącznie jawnie podlinkowane RSS/Atom dla kolejki potwierdzenia kanału. '
            'Nie aktywuje źródeł ani nie tworzy kart dostępu.')

    def add_arguments(self, parser):
        parser.add_argument('--workers', type=int, default=2)
        parser.add_argument('--limit', type=int, default=2)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        sources = list(Source.objects.order_by('pk'))
        states = dict(ImportState.objects.filter(name__startswith='source-check:').values_list('name', 'cursor'))
        active_hosts = {hostname(source.url) for source in sources if source.is_active and source.scrape_enabled
                        and source.catalog_stage == 'configured' and hostname(source.url)}
        candidates = [source for source in sources if outcome(
            source, states.get(f'source-check:{source.pk}', {}), active_hosts) == 'confirm_exact_channel']
        selected = [source for source in candidates if not is_fresh(
            source, states.get(f'source-check:{source.pk}', {}))][:max(1, min(options['limit'], 4))]
        if not selected:
            self.stdout.write(self.style.SUCCESS(
                f'CONFIRMABLE_SOURCE_CHANNELS: pending=0 checked={len(candidates)}/{len(candidates)}; no source was activated.'
            ))
            return
        network = ProbeNetwork(delay=3)
        results = {}
        with ThreadPoolExecutor(max_workers=max(1, min(options['workers'], 3))) as executor:
            futures = [executor.submit(worker, source, states.get(f'source-check:{source.pk}', {}), network)
                       for source in selected]
            for future in as_completed(futures):
                source_id, result = future.result(); results[source_id] = result
                self.stdout.write(f'CHANNEL {source_id}: {result["status"]}')
        if options['apply']:
            for source in selected:
                cursor = dict(states.get(f'source-check:{source.pk}', {}) or {})
                cursor['legal_channel_discovery'] = results[source.pk]
                ImportState.objects.update_or_create(name=f'source-check:{source.pk}',
                    defaults={'cursor': cursor, 'last_error': ''})
        working = sum(result['status'] == 'working_channel_requires_editorial_card_review' for result in results.values())
        self.stdout.write(self.style.SUCCESS(
            f'CONFIRMABLE_SOURCE_CHANNELS: processed={len(selected)} pending={len(candidates) - len(selected)} '
            f'working={working}; no source was activated.'
        ))
