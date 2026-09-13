"""Resumable bounded source audit; never enables a source or imports its materials."""
import csv
import json
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections, connections
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news.models import ImportState, Source
from scraper.source_probe import (PROBE_VERSION, ProbeNetwork, begin_source_audit, empty_result,
    probe_source, save_source_audit, source_signature)


def is_fresh(source, result, max_age_hours):
    checked = parse_datetime(result.get('checked_at') or '')
    return bool(result.get('probe_version') == PROBE_VERSION
        and result.get('signature') == source_signature(source)
        and result.get('audit_status') in ('completed', 'skipped')
        and checked and timezone.is_aware(checked)
        and checked >= timezone.now() - timedelta(hours=max_age_hours))


def csv_safe(value):
    text = str(value if value is not None else '')
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


def write_reports(prefix, sources, results):
    """All catalog rows appear even while the resumable audit is still in progress."""
    prefix = Path(prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for source in sources:
        row = results.get(source.pk) or empty_result(source)
        if source.pk not in results:
            row['audit_status'] = 'pending'
        rows.append(row)
    summary = {
        'total': len(rows), 'audit_status': dict(Counter(r['audit_status'] for r in rows)),
        'rss_status': dict(Counter(r['rss']['status'] for r in rows)),
        'archive_status': dict(Counter(r['archive']['status'] for r in rows)),
        'observed_page_urls_sum_not_deduplicated_between_sources': sum(r['archive']['page_urls_observed'] for r in rows)}
    report = {'generated_at': timezone.now().isoformat(), 'summary': summary, 'sources': rows,
        'method': 'Bez pobierania pełnych archiwów. Skonfigurowany RSS i ujawnione linki wydawcy; robots i do dwóch zadeklarowanych map XML; do trzech rozłożonych próbek map podrzędnych. Status HTML to kandydatura, nie działający importer. last_success oznacza zakończenie kontroli, nie sukces importu. Liczby URL map nie dowodzą liczby artykułów ani kompletności historii.'}
    json_path = prefix.with_suffix('.json')
    tmp = json_path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(json_path)
    csv_path = prefix.with_suffix('.csv')
    tmp = csv_path.with_suffix('.csv.tmp')
    with tmp.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['id', 'nazwa', 'adres', 'etap_katalogu', 'status_audytu', 'sprawdzono',
            'rss_status', 'rss_url', 'rss_wpisy', 'rss_użyteczne', 'archiwum_status', 'mapy_xml',
            'mapy_podrzędne', 'mapy_próbki', 'zaobserwowane_url', 'status_liczenia',
            'listy_html_kandydaci', 'oficjalne_api_status', 'ujawnione_wp_api', 'błędy', 'zalecenie'])
        for row in rows:
            archive, rss = row['archive'], row['rss']
            writer.writerow([csv_safe(value) for value in [row['source_id'], row['name'], row['source_url'],
                row['catalog_stage'], row['audit_status'], row['checked_at'], rss['status'], rss['url'],
                rss['entry_count'], rss['usable_entry_count'], archive['status'], '\n'.join(archive['sitemap_urls']),
                archive['child_sitemap_count'], archive['sampled_child_count'], archive['page_urls_observed'],
                archive['volume_estimate']['status'], '\n'.join(archive['listing_urls']),
                row.get('official_api', {}).get('status', ''),
                '\n'.join(item['url'] for item in row['evidence'] if item['kind'] == 'publisher_api_link'),
                json.dumps(row['errors'], ensure_ascii=False), row['recommendation']]])
    tmp.replace(csv_path)
    lines = ['# Audyt dostępności źródeł', '', f"Stan: {report['generated_at']}", '', report['method'], '',
        'Nie zmieniono aktywności źródeł ani częstotliwości. Wykluczone i źródła bez adresu są jawnie pominięte. '
        'Brak potwierdzenia w tej ograniczonej kontroli nie dowodzi braku materiałów w internecie.', '',
        'Statystyki: `' + json.dumps(summary, ensure_ascii=False) + '`', '',
        '| ID | Źródło | RSS | Archiwum | Zaobserwowane URL map | Wniosek / stan |',
        '|---|---|---|---|---:|---|']
    for row in rows:
        escape = lambda value: str(value or '').replace('|', '\\|').replace('\n', ' ')
        label = escape(row['name'])
        if row['source_url']:
            label = f"[{label}]({row['source_url']})"
        lines.append('| ' + ' | '.join(map(str, [row['source_id'], label, row['rss']['status'],
            row['archive']['status'], row['archive']['page_urls_observed'],
            escape(row['recommendation'] or row['audit_status'])])) + ' |')
    lines += ['', 'Pełne dowody HTTP, odnośniki, próbki dat i metodę liczenia każdej mapy zawiera plik JSON. '
        'CSV zawiera wszystkie źródła bez skracania listy. Ekstrapolacje próbek w JSON są tylko arytmetyką; nie należy ich sumować jako potwierdzonej wielkości archiwum.', '']
    md_path = prefix.with_suffix('.md')
    tmp = md_path.with_suffix('.md.tmp')
    tmp.write_text('\n'.join(lines), encoding='utf-8')
    tmp.replace(md_path)
    return summary


def worker(source, network):
    close_old_connections()
    try:
        return probe_source(source, network)
    except Exception as exc:
        result = empty_result(source)
        result.update(audit_status='failed', fatal_error=type(exc).__name__, checked_at=timezone.now().isoformat())
        return result
    finally:
        connections.close_all()


class Command(BaseCommand):
    help = 'Sprawdza źródła bez importowania materiałów i zapisuje wznawialne dowody oraz pełny raport.'

    def add_arguments(self, parser):
        parser.add_argument('--workers', type=int, default=6)
        parser.add_argument('--force', action='store_true')
        parser.add_argument('--max-age-hours', type=int, default=24)
        parser.add_argument('--source-id', action='append', type=int)
        parser.add_argument('--output-prefix', default=str(Path(__file__).resolve().parents[4] / 'reports' / 'source-access-audit-2026-09-09'))

    def handle(self, *args, **options):
        if not 1 <= options['workers'] <= 6 or options['max_age_hours'] < 0:
            raise CommandError('workers musi wynosić 1–6, a max-age-hours co najmniej 0.')
        query = Source.objects.order_by('id')
        if options['source_id']:
            query = query.filter(pk__in=options['source_id'])
        sources = list(query)
        states = dict(ImportState.objects.filter(name__in=[f'source-check:{s.pk}' for s in sources]).values_list('name', 'cursor'))
        results, pending = {}, []
        for source in sources:
            previous = states.get(f'source-check:{source.pk}', {})
            if not options['force'] and is_fresh(source, previous, options['max_age_hours']):
                results[source.pk] = previous
            else:
                pending.append(source)
        write_reports(options['output_prefix'], sources, results)
        self.stdout.write(f'Katalog {len(sources)}; zachowane aktualne audyty {len(results)}; do sprawdzenia {len(pending)}.', ending='\n')
        network = ProbeNetwork()
        active = {}
        with ThreadPoolExecutor(max_workers=options['workers']) as pool:
            while pending or active:
                hosts = {host for _, host in active.values()}
                while len(active) < options['workers']:
                    index = next((i for i, source in enumerate(pending)
                        if (urlsplit(source.url or source.rss_url).hostname or f'no-url-{source.pk}') not in hosts), None)
                    if index is None:
                        break
                    source = pending.pop(index)
                    host = urlsplit(source.url or source.rss_url).hostname or f'no-url-{source.pk}'
                    begin_source_audit(source)
                    active[pool.submit(worker, source, network)] = (source, host)
                    hosts.add(host)
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    source, _ = active.pop(future)
                    result = future.result()
                    save_source_audit(source, result)
                    results[source.pk] = result
                    write_reports(options['output_prefix'], sources, results)
                    self.stdout.write(f"[{len(results)}/{len(sources)}] {source.pk} {source.name}: "
                        f"RSS {result['rss']['status']}; archiwum {result['archive']['status']}; "
                        f"{result['archive']['page_urls_observed']} URL zaobserwowanych; {result['audit_status']}")
                    self.stdout.flush()
        self.stdout.write(json.dumps(write_reports(options['output_prefix'], sources, results), ensure_ascii=False))
