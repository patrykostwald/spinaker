"""Co wymyśliły pętle agentów (właściciel 6.10: „pętle researchu nic nie wynalazły”). Tylko odczyt, bez sekretów.

python manage.py pomysly_agentow            - pomysły i ustalenia z 14 dni, od najwyżej ocenionych
python manage.py pomysly_agentow --dni 30 --wszystkie
Wynik można wkleić Claude: na tej podstawie wybieramy, co budujemy w kolejnym sprincie."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Pomysły, ustalenia i propozycje agentów (Wynalazca, Architekt, Strateg, Zwiadowca, Kartograf...) z ostatnich dni.'

    def add_arguments(self, parser):
        parser.add_argument('--dni', type=int, default=14)
        parser.add_argument('--wszystkie', action='store_true', help='także odrzucone i zrobione')
        parser.add_argument('--limit', type=int, default=60)

    def handle(self, *args, **options):
        from news.agent_models import AgentNote
        since = timezone.now() - timedelta(days=options['dni'])
        rows = AgentNote.objects.filter(created_at__gte=since)
        if not options['wszystkie']:
            rows = rows.exclude(status__in=('rejected', 'denied', 'done'))
        out = self.stdout.write
        total = rows.count()
        out(f'Notatki agentów z {options["dni"]} dni: {total}')
        by_agent = {}
        for agent, kind in rows.values_list('agent', 'kind'):
            by_agent.setdefault(agent, {}).setdefault(kind, 0)
            by_agent[agent][kind] += 1
        for agent, kinds in sorted(by_agent.items()):
            out(f'  {agent}: ' + ', '.join(f'{k} {v}' for k, v in sorted(kinds.items())))
        out('')
        for note in rows.order_by('-score', '-created_at')[:options['limit']]:
            body = ' '.join(str(note.body).split())[:260]
            out(f'[{note.agent}/{note.kind}/{note.status}] {note.score}/100 · {note.created_at:%d.%m} · {note.title}')
            if body:
                out(f'    {body}')
