"""Discover official source terms for later editorial review."""
import csv
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connections
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news.models import ImportState, Source, SourceReviewDecision
from scraper.source_probe import ProbeNetwork, source_signature
from scraper.source_terms_discovery import DISCOVERY_VERSION, inspect_source_terms


def is_fresh(source, cursor, max_age_days):
    result = (cursor or {}).get('legal_terms_discovery', {})
    checked = parse_datetime(result.get('checked_at') or '')
    return bool(
        result.get('version') == DISCOVERY_VERSION
        and result.get('signature') == source_signature(source)
        and checked and timezone.is_aware(checked)
        and checked >= timezone.now() - timedelta(days=max_age_days)
    )


def worker(source, network):
    close_old_connections()
    try:
        result = inspect_source_terms(source, network)
        result.update(checked_at=timezone.now().isoformat(), signature=source_signature(source))
        return source.pk, result
    finally:
        connections.close_all()


class Command(BaseCommand):
    help = ('Finds official reuse-condition pages for inactive contact candidates. '
            'Never approves access, enables a source, imports material, or sends messages.')

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=24)
        parser.add_argument('--workers', type=int, default=3)
        parser.add_argument('--max-age-days', type=int, default=30)
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--apply', action='store_true', help='Save evidence in the source audit state.')
        parser.add_argument('--output', default='reports/source-reuse-discovery-current.md')

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 48 or not 1 <= options['workers'] <= 6 or options['max_age_days'] < 1:
            raise CommandError('limit musi wynosić 1..48, workers 1..6, a max-age-days co najmniej 1.')
        sources = list(Source.objects.filter(
            catalog_stage='candidate', is_active=False, scrape_enabled=False,
            review_decision__decision=SourceReviewDecision.Decision.CONTACT_REQUIRED,
        ).order_by('pk'))
        states = dict(ImportState.objects.filter(
            name__in=[f'source-check:{source.pk}' for source in sources]
        ).values_list('name', 'cursor'))
        pending = [source for source in sources if options['force'] or not is_fresh(
            source, states.get(f'source-check:{source.pk}', {}), options['max_age_days'])]
        selected = pending[:options['limit']]
        if not selected:
            self._write_report(options['output'], sources, states)
            self.stdout.write(self.style.SUCCESS(
                f'SOURCE_TERMS_DISCOVERY: pending=0 checked={len(sources)}/{len(sources)}; {options["output"]}'
            ))
            return
        network = ProbeNetwork(delay=3)
        results = {}
        with ThreadPoolExecutor(max_workers=options['workers']) as executor:
            futures = [executor.submit(worker, source, network) for source in selected]
            for future in as_completed(futures):
                source_id, result = future.result()
                results[source_id] = result
                self.stdout.write(f'DISCOVERED {source_id}: {result["status"]}')
        if options['apply']:
            for source in selected:
                cursor = dict(states.get(f'source-check:{source.pk}', {}) or {})
                cursor['legal_terms_discovery'] = results[source.pk]
                ImportState.objects.update_or_create(
                    name=f'source-check:{source.pk}', defaults={'cursor': cursor, 'last_error': ''},
                )
                states[f'source-check:{source.pk}'] = cursor
        self._write_report(options['output'], sources, states, results)
        self.stdout.write(self.style.SUCCESS(
            f'SOURCE_TERMS_DISCOVERY: processed={len(selected)} pending={len(pending) - len(selected)} '
            f'apply={str(options["apply"]).lower()}; {options["output"]}'
        ))

    @staticmethod
    def _write_report(output_name, sources, states, new_results=None):
        new_results = new_results or {}
        rows = []
        for source in sources:
            result = new_results.get(source.pk) or (states.get(f'source-check:{source.pk}', {}) or {}).get('legal_terms_discovery', {})
            rows.append({
                'id': source.pk, 'source': source.name, 'url': source.url or '',
                'status': result.get('status', 'pending'),
                'terms_urls': ' | '.join(page.get('url', '') for page in result.get('terms_pages', []) if page.get('url')),
                'positive_markers': ', '.join(marker for page in result.get('terms_pages', []) for marker in page.get('positive_markers', [])),
                'restriction_markers': ', '.join(marker for page in result.get('terms_pages', []) for marker in page.get('restriction_markers', [])),
                'checked_at': result.get('checked_at', ''),
            })
        output = Path(output_name)
        output.parent.mkdir(parents=True, exist_ok=True)
        counts = Counter(row['status'] for row in rows)
        lines = [
            '# Official reuse terms discovery', '',
            'This report is evidence for editorial review only. It does not approve access, create a card, enable a source, import content, or send messages.', '',
            f'Contact candidates: **{len(rows)}**.', '', '| Result | Count |', '|---|---:|',
        ]
        lines += [f'| {status} | {count} |' for status, count in sorted(counts.items())]
        lines += ['', '| ID | Source | Result | Terms pages | Positive markers | Restriction markers |', '|---:|---|---|---|---|---|']
        for row in rows:
            label = row['source'].replace('|', '\\|')
            source = f'[{label}]({row["url"]})' if row['url'] else label
            lines.append(f'| {row["id"]} | {source} | {row["status"]} | {row["terms_urls"]} | {row["positive_markers"]} | {row["restriction_markers"]} |')
        output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        with output.with_suffix('.csv').open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ('id', 'source', 'url', 'status', 'terms_urls', 'positive_markers', 'restriction_markers', 'checked_at'))
            writer.writeheader(); writer.writerows(rows)
        output.with_suffix('.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
