"""Classify discovered reuse-condition wording without authorising access."""
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connections
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news.models import ImportState
from scraper.source_terms_queue import terms_discovery_candidates
from scraper.source_probe import ProbeError, ProbeNetwork, source_signature
from scraper.source_terms_discovery import classify_terms_page


CLASSIFIER_VERSION = 1


def channels_for(cursor, source):
    rss = (cursor or {}).get('rss', {}) or {}
    api = (cursor or {}).get('official_api', {}) or {}
    return bool((rss.get('status') == 'working' and rss.get('url')) or api.get('status') == 'working')


def is_fresh(source, cursor, max_age_days):
    result = (cursor or {}).get('legal_terms_classification', {})
    checked = parse_datetime(result.get('checked_at') or '')
    return bool(result.get('version') == CLASSIFIER_VERSION and result.get('signature') == source_signature(source)
        and checked and timezone.is_aware(checked) and checked >= timezone.now() - timedelta(days=max_age_days))


def worker(source, cursor, network):
    close_old_connections()
    try:
        discovered = (cursor or {}).get('legal_terms_discovery', {})
        pages = [page['url'] for page in discovered.get('terms_pages', []) if page.get('status') == 'ok' and page.get('url')]
        if not pages:
            result = {'version': CLASSIFIER_VERSION, 'status': 'no_readable_terms_page', 'pages': []}
        else:
            result = {'version': CLASSIFIER_VERSION, 'status': 'wording_requires_editorial_review', 'pages': []}
            for url in pages[:3]:
                try:
                    raw, final_url, _ = network.fetch(url)
                    item = {'url': final_url, **classify_terms_page(raw, channels_for(cursor, source))}
                except Exception as exc:
                    error = str(exc) if isinstance(exc, ProbeError) else type(exc).__name__
                    item = {'url': url, 'status': 'unavailable', 'error': error}
                result['pages'].append(item)
            statuses = [item['status'] for item in result['pages']]
            if 'clear_denial_keep_inactive' in statuses:
                result['status'] = 'clear_denial_keep_inactive'
            elif 'proposed_metadata_card_requires_editorial_approval' in statuses:
                result['status'] = 'proposed_metadata_card_requires_editorial_approval'
            elif 'permission_wording_but_no_confirmed_channel' in statuses:
                result['status'] = 'permission_wording_but_no_confirmed_channel'
            elif all(status == 'unavailable' for status in statuses):
                result['status'] = 'unavailable'
        result.update(checked_at=timezone.now().isoformat(), signature=source_signature(source))
        return source.pk, result
    finally:
        connections.close_all()


class Command(BaseCommand):
    help = ('Classifies already discovered reuse terms. It only proposes outcomes; it never creates cards, '
            'enables sources, imports content, or sends messages.')

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=16)
        parser.add_argument('--workers', type=int, default=3)
        parser.add_argument('--max-age-days', type=int, default=30)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--output', default='reports/source-reuse-classification-current.md')

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 32 or not 1 <= options['workers'] <= 6 or options['max_age_days'] < 1:
            raise CommandError('limit musi wynosić 1..32, workers 1..6, a max-age-days co najmniej 1.')
        sources, states = terms_discovery_candidates()
        sources = [source for source in sources if (states.get(f'source-check:{source.pk}', {}) or {}).get('legal_terms_discovery', {}).get('terms_pages')]
        pending = [source for source in sources if options['force'] or not is_fresh(source, states.get(f'source-check:{source.pk}', {}), options['max_age_days'])]
        selected = pending[:options['limit']]
        if not selected:
            self._write_report(options['output'], sources, states)
            self.stdout.write(self.style.SUCCESS(f'SOURCE_TERMS_CLASSIFICATION: pending=0 checked={len(sources)}/{len(sources)}; {options["output"]}'))
            return
        results, network = {}, ProbeNetwork(delay=3)
        with ThreadPoolExecutor(max_workers=options['workers']) as executor:
            futures = [executor.submit(worker, source, states.get(f'source-check:{source.pk}', {}), network) for source in selected]
            for future in as_completed(futures):
                source_id, result = future.result(); results[source_id] = result
                self.stdout.write(f'CLASSIFIED {source_id}: {result["status"]}')
        if options['apply']:
            for source in selected:
                cursor = dict(states.get(f'source-check:{source.pk}', {}) or {})
                cursor['legal_terms_classification'] = results[source.pk]
                ImportState.objects.update_or_create(name=f'source-check:{source.pk}', defaults={'cursor': cursor, 'last_error': ''})
                states[f'source-check:{source.pk}'] = cursor
        self._write_report(options['output'], sources, states, results)
        self.stdout.write(self.style.SUCCESS(f'SOURCE_TERMS_CLASSIFICATION: processed={len(selected)} pending={len(pending)-len(selected)} apply={str(options["apply"]).lower()}; {options["output"]}'))

    @staticmethod
    def _write_report(output_name, sources, states, new_results=None):
        new_results = new_results or {}
        rows = []
        for source in sources:
            result = new_results.get(source.pk) or (states.get(f'source-check:{source.pk}', {}) or {}).get('legal_terms_classification', {})
            rows.append({'id': source.pk, 'source': source.name, 'url': source.url or '', 'status': result.get('status', 'pending'),
                'pages': ' | '.join(page.get('url', '') for page in result.get('pages', [])),
                'permission': ', '.join(marker for page in result.get('pages', []) for marker in page.get('permission_markers', [])),
                'denial': ', '.join(marker for page in result.get('pages', []) for marker in page.get('denial_markers', []))})
        counts = Counter(row['status'] for row in rows)
        output = Path(output_name); output.parent.mkdir(parents=True, exist_ok=True)
        lines = ['# Source reuse terms classification', '', 'This report only proposes an editorial decision. It does not create an access card, enable a source, import content, or send messages.', '', f'Classified terms sources: **{len(rows)}**.', '', '| Result | Count |', '|---|---:|']
        lines += [f'| {name} | {count} |' for name, count in sorted(counts.items())]
        lines += ['', '| ID | Source | Result | Terms page | Permission wording | Denial wording |', '|---:|---|---|---|---|---|']
        for row in rows:
            label = row['source'].replace('|', '\\|'); source = f'[{label}]({row["url"]})' if row['url'] else label
            lines.append(f'| {row["id"]} | {source} | {row["status"]} | {row["pages"]} | {row["permission"]} | {row["denial"]} |')
        output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        output.with_suffix('.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
