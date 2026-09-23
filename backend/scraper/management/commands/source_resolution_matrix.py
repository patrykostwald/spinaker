"""Evidence-first, read-only operating view of every source in the catalogue."""

import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand

from news.models import ImportState, Source
from scraper.access_gate import has_current_approved_instruction
from scraper.management.commands.source_review_queue import hostname


def outcome(source, cursor, active_hosts):
    if source.is_active and source.scrape_enabled and source.catalog_stage == 'configured':
        return ('active_harvester' if has_current_approved_instruction(source) else 'active_card_problem')
    if source.catalog_stage != 'candidate' or source.is_active or source.scrape_enabled:
        return 'outside_mvp_queue'
    if hostname(source.url) in active_hosts:
        return 'covered_by_active_host'
    discovery = (cursor or {}).get('legal_terms_discovery') or {}
    classified = (cursor or {}).get('legal_terms_classification') or {}
    if not discovery.get('checked_at'):
        return 'terms_scan_pending'
    status = classified.get('status')
    return {
        'proposed_metadata_card_requires_editorial_approval': 'editorial_card_review',
        'clear_denial_keep_inactive': 'contact_or_keep_inactive',
        'permission_wording_but_no_confirmed_channel': 'confirm_exact_channel',
        'wording_requires_editorial_review': 'editorial_terms_review',
        'no_readable_terms_page': 'contact_required',
        'unavailable': 'retry_or_contact_required',
    }.get(status, 'terms_classification_pending')


NEXT_STEP = {
    'active_harvester': 'Pobieranie działa przez zatwierdzoną kartę.',
    'active_card_problem': 'Wstrzymać i naprawić kartę dostępu.',
    'covered_by_active_host': 'Nie tworzyć duplikatu; dane pobiera już aktywny rekord tego hosta.',
    'terms_scan_pending': 'Uruchomić pełne wyszukiwanie warunków użycia.',
    'editorial_card_review': 'Redakcyjnie sprawdzić dokładny kanał i treść warunków przed utworzeniem karty.',
    'contact_or_keep_inactive': 'Warunki zawierają zakaz lub wymóg zgody; pozostawić wyłączone albo dodać do kontaktu.',
    'confirm_exact_channel': 'Warunki są obiecujące, ale trzeba ustalić konkretny RSS/API; nie zgadywać adresu.',
    'editorial_terms_review': 'Wymaga odczytu warunków przez redakcję; bez automatycznej aktywacji.',
    'contact_required': 'Brak czytelnych warunków; przygotować do późniejszego kontaktu.',
    'retry_or_contact_required': 'Strona warunków była niedostępna; ponowić kontrolę, potem przygotować kontakt.',
    'terms_classification_pending': 'Uruchomić klasyfikację znalezionych warunków.',
    'outside_mvp_queue': 'Poza aktywną kolejką MVP.',
}


class Command(BaseCommand):
    help = 'Tworzy tylko-odczytową macierz: aktywne źródło, dowód do karty, sprawdzenie kanału lub kontakt.'

    def add_arguments(self, parser):
        parser.add_argument('--output', default='reports/source-resolution-matrix-current.md')

    def handle(self, *args, **options):
        sources = list(Source.objects.order_by('pk'))
        states = dict(ImportState.objects.filter(name__startswith='source-check:').values_list('name', 'cursor'))
        active_hosts = {hostname(source.url) for source in sources if source.is_active and source.scrape_enabled
                        and source.catalog_stage == 'configured' and hostname(source.url)}
        rows = []
        for source in sources:
            result = outcome(source, states.get(f'source-check:{source.pk}', {}), active_hosts)
            rows.append({'id': source.pk, 'source': source.name, 'url': source.url or '',
                         'outcome': result, 'next_step': NEXT_STEP[result]})
        counts = Counter(row['outcome'] for row in rows)
        output = Path(options['output']); output.parent.mkdir(parents=True, exist_ok=True)
        lines = ['# Macierz rozstrzygnięć źródeł', '',
                 'Raport tylko odczytu. Nie aktywuje źródeł, nie tworzy kart, nie pobiera treści i nie wysyła wiadomości.', '',
                 '| Stan | Liczba |', '|---|---:|']
        lines += [f'| {key} | {counts[key]} |' for key in sorted(counts)]
        lines += ['', '| ID | Źródło | Stan | Następny krok |', '|---:|---|---|---|']
        for row in rows:
            label = row['source'].replace('|', '\\|')
            source = f'[{label}]({row["url"]})' if row['url'] else label
            lines.append(f'| {row["id"]} | {source} | {row["outcome"]} | {row["next_step"]} |')
        output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        output.with_suffix('.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        summary = ' '.join(f'{key}={counts[key]}' for key in sorted(counts))
        self.stdout.write(self.style.SUCCESS(f'SOURCE_RESOLUTION_MATRIX: {summary}; {output}'))
