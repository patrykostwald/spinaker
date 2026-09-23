"""Create a read-only, human-review queue from completed source probes."""
import json
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand

from news.models import ImportState, Source, SourceType


def review_bucket(source, result):
    if result.get('audit_status') == 'failed':
        return '01_blad_techniczny'
    if source.source_type == SourceType.INSTITUTION and (result.get('rss') or {}).get('status') == 'working':
        return '02_instytucja_rss_do_warunkow'
    if source.source_type == SourceType.INSTITUTION:
        return '03_instytucja_bez_potwierdzonego_kanalu'
    return '04_wydawca_lub_organizacja_wymaga_zgody'


class Command(BaseCommand):
    help = 'Tworzy tylko-odczytowy raport kolejki decyzji dla nieaktywnych kandydatów.'

    def add_arguments(self, parser):
        root = Path(__file__).resolve().parents[4]
        parser.add_argument('--output', default=str(root / 'reports' / 'source-review-queue-current.md'))

    def handle(self, *args, **options):
        sources = list(Source.objects.filter(
            catalog_stage='candidate', is_active=False, scrape_enabled=False,
        ).order_by('pk'))
        states = dict(ImportState.objects.filter(
            name__in=[f'source-check:{source.pk}' for source in sources]
        ).values_list('name', 'cursor'))
        grouped = defaultdict(list)
        for source in sources:
            result = states.get(f'source-check:{source.pk}', {}) or {}
            grouped[review_bucket(source, result)].append((source, result))

        labels = {
            '01_blad_techniczny': 'Błędy techniczne — nie aktywować',
            '02_instytucja_rss_do_warunkow': 'Instytucje z działającym RSS — sprawdzić warunki i kartę dostępu',
            '03_instytucja_bez_potwierdzonego_kanalu': 'Instytucje bez potwierdzonego kanału — nie zgadywać endpointu',
            '04_wydawca_lub_organizacja_wymaga_zgody': 'Wydawcy i organizacje — wymagają warunków lub zgody',
        }
        lines = [
            '# Kolejka przeglądu źródeł', '',
            'Raport jest tylko podsumowaniem zapisanych audytów. Nie tworzy karty dostępu, nie aktywuje źródła i nie pobiera materiałów.',
            '', f'Kandydaci: **{len(sources)}**.',
        ]
        payload = []
        for bucket in labels:
            entries = grouped[bucket]
            lines += ['', f'## {labels[bucket]} ({len(entries)})', '']
            if not entries:
                lines.append('Brak pozycji.')
                continue
            lines += ['| ID | Źródło | Audyt | RSS | Następny ruch |', '|---:|---|---|---|---|']
            for source, result in entries:
                rss = result.get('rss') or {}
                audit_status = result.get('audit_status', 'brak audytu')
                if bucket == '01_blad_techniczny':
                    action = 'Sprawdzić ręcznie domenę, certyfikat lub przekierowanie; nie obchodzić błędu.'
                elif bucket == '02_instytucja_rss_do_warunkow':
                    action = 'Potwierdzić warunki dla dokładnego kanału, potem przygotować wąską kartę metadanych.'
                elif bucket == '03_instytucja_bez_potwierdzonego_kanalu':
                    action = 'Ustalić jawny API/RSS/listę i warunki; nie zgadywać adresu.'
                else:
                    action = 'Sprawdzić regulamin i zgodę na automatyczne metadane; bez niej pozostawić nieaktywne.'
                name = source.name.replace('|', '\\|')
                url = source.url or ''
                name = f'[{name}]({url})' if url else name
                lines.append(f'| {source.pk} | {name} | {audit_status} | {rss.get("status", "brak")} | {action} |')
                payload.append({'id': source.pk, 'name': source.name, 'url': url, 'bucket': bucket,
                                'audit_status': audit_status, 'rss_status': rss.get('status', 'brak')})
        output = Path(options['output'])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        output.with_suffix('.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'RAPORT_KOLEJKI: {len(sources)} kandydatów; {output}'))
