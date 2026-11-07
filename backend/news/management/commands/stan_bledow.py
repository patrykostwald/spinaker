"""Wszystkie problemy naraz, krótko (właściciel 5.10: „przejrzyj wszystkie błędy i napraw”).

Użycie: manage.py stan_bledow
Wypisuje listę „Wymaga uwagi” z panelu dowodzenia i agentów z błędem albo uwagą (z podsumowaniem pulsu).
Tylko odczyt; komunikaty są już sklasyfikowane (bez kluczy i treści wyjątków), więc wynik można wkleić Claude."""
import re

from django.core.management.base import BaseCommand
from django.utils import timezone

SECRET = re.compile(r'(sk-[A-Za-z0-9_-]{8,}|Bearer\s+\S+|[A-Za-z0-9_-]{32,})')


def clean(text):
    return SECRET.sub('[ukryte]', str(text or ''))[:220]


class Command(BaseCommand):
    help = 'Wypisuje wszystkie problemy z panelu i mapy agentów (tylko odczyt, bez sekretów).'

    def handle(self, *args, **opts):
        from news.admin_status import actions, snapshot
        from news.agent_registry import snapshot as agents
        out = self.stdout.write
        now = timezone.now()
        data = snapshot(now)
        rows = data.get('actions') or actions(data.get('sections', []), [])
        out(f'== Wymaga uwagi ({len(rows)}) ==')
        for row in rows:
            out(f"[{row['status']}] {row.get('section', '')} · {row['title']}: {clean(row.get('detail'))}")
        out('')
        bad = [r for r in agents(now) if r['enabled'] and r['result'] in ('error', 'warn')]
        bad.sort(key=lambda r: (r['result'] != 'error', r['name']))
        out(f'== Agenci z błędem lub uwagą ({len(bad)}) ==')
        for r in bad:
            last = r['last_run'].astimezone().strftime('%d.%m %H:%M') if r.get('last_run') else 'brak'
            out(f"[{r['result']}] {r['name']} ({r['schedule']}, ostatnio {last}): {clean(r['summary'])}")
        off = [r['name'] for r in agents(now) if not r['enabled'] and not r['collector']]
        out('')
        out(f"== Wyłączeni agenci ({len(off)}) == {', '.join(off)}")
