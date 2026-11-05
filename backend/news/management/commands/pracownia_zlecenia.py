"""Zlecenia z Pracowni OSINT dla wykonawców (Claude, Codex): pomysły Architekta, które nie są odrzucone, z kryteriami odbioru.

Użycie: manage.py pracownia_zlecenia [--wszystkie] [--uruchom]
--uruchom: najpierw krok Pracowni (role, którym minął termin). Polecenie tylko czyta i wypisuje; niczego nie wdraża."""
from django.core.management.base import BaseCommand

from news.agent_models import AgentNote


class Command(BaseCommand):
    help = 'Wypisuje zlecenia z planu Architekta przeszłość.today (do budowy po zgodzie właściciela).'

    def add_arguments(self, parser):
        parser.add_argument('--wszystkie', action='store_true', help='Także zlecenia już zrobione (status done).')
        parser.add_argument('--uruchom', action='store_true', help='Najpierw krok Pracowni OSINT (wymusza wszystkie role).')

    def handle(self, *args, **opts):
        out = self.stdout.write
        if opts['uruchom']:
            from news import pracownia_osint
            for agent, result in pracownia_osint.step(force=True).items():
                out(f'{agent}: {result}')
        rows = AgentNote.objects.filter(agent='architekt', kind='idea').exclude(status__in=['rejected', 'denied'])
        if not opts['wszystkie']:
            rows = rows.exclude(status='done')
        rows = sorted(rows, key=lambda n: (n.status != 'accepted', -n.score, -n.pk))
        if not rows:
            out('Brak zleceń. Architekt układa plan raz w tygodniu (albo: --uruchom).')
            return
        for n in rows:
            d = n.scores or {}
            out(f"\n#{n.pk} [{n.status}] {n.title} · {d.get('tier', '-')}, wysiłek {d.get('effort', '-')}, wartość {d.get('value', '-')}/10")
            out(f"Dlaczego: {d.get('why', '')}")
            for a in d.get('acceptance', []):
                out(f'  - odbiór: {a}')
            out(f"Zlecenie: {d.get('brief', '')}")
