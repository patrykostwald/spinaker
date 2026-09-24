"""Write a bounded list of sources whose published terms need an exact channel."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from news.models import ImportState, Source
from scraper.management.commands.source_resolution_matrix import outcome
from scraper.management.commands.source_review_queue import hostname


class Command(BaseCommand):
    help = ('Tworzy listę źródeł z obiecującymi warunkami, dla których trzeba potwierdzić konkretny RSS/API. '
            'Nie aktywuje źródeł, nie tworzy kart ani nie pobiera materiałów.')

    def add_arguments(self, parser):
        parser.add_argument('--output', default='reports/source-channel-confirmation-current.md')

    def handle(self, *args, **options):
        sources = list(Source.objects.order_by('pk'))
        states = dict(ImportState.objects.filter(name__startswith='source-check:').values_list('name', 'cursor'))
        active_hosts = {hostname(source.url) for source in sources if source.is_active and source.scrape_enabled
                        and source.catalog_stage == 'configured' and hostname(source.url)}
        rows = []
        for source in sources:
            state = states.get(f'source-check:{source.pk}', {}) or {}
            if outcome(source, state, active_hosts) != 'confirm_exact_channel':
                continue
            audit = state.get('rss') or {}
            discovery = state.get('legal_terms_discovery') or {}
            terms = [page.get('url', '') for page in discovery.get('terms_pages', []) if page.get('url')]
            rows.append({
                'id': source.pk, 'source': source.name, 'url': source.url or '',
                'rss_status': audit.get('status', 'unknown'), 'rss_url': audit.get('url', ''),
                'api_status': (state.get('official_api') or {}).get('status', 'not_found'),
                'terms_pages': terms,
                'next_step': 'Potwierdź jawnie wskazany RSS albo API w warunkach lub dokumentacji źródła.',
            })
        output = Path(options['output']); output.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            '# Kanały wymagające dokładnego potwierdzenia', '',
            'Lista przygotowawcza. Nie tworzy karty dostępu, nie aktywuje źródła i nie pobiera materiałów.', '',
            f'Źródła do potwierdzenia kanału: **{len(rows)}**.', '',
            '| ID | Źródło | RSS / API z audytu | Strona warunków | Następny krok |', '|---:|---|---|---|---|',
        ]
        for row in rows:
            label = row['source'].replace('|', '\\|')
            source = f'[{label}]({row["url"]})' if row['url'] else label
            channel = f"RSS: {row['rss_status']} {row['rss_url']}".strip()
            if row['api_status'] != 'not_found':
                channel += f"; API: {row['api_status']}"
            lines.append(f"| {row['id']} | {source} | {channel} | {'<br>'.join(row['terms_pages'])} | {row['next_step']} |")
        output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        output.with_suffix('.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'SOURCE_CHANNEL_CONFIRMATION_QUEUE: {len(rows)} sources; {output}'))
