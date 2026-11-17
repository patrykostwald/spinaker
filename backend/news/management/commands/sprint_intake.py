"""Ręczne uruchomienie Sprintu tygodnia (bez sieci i bez modeli AI).

python manage.py sprint_intake            - pełny przegląd jak w poniedziałek (do 8 propozycji)
python manage.py sprint_intake --podglad  - tylko ranking kandydatów, bez zapisu"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Tworzy bilety Sprintu tygodnia z przyjętych i wysoko ocenionych pomysłów agentów.'

    def add_arguments(self, parser):
        parser.add_argument('--podglad', action='store_true')

    def handle(self, *args, **options):
        from news import sprint
        from news.agent_models import BuildTicket
        out = self.stdout.write
        if options['podglad']:
            for cand in sprint.candidates()[:sprint.MAX_PROPOSED]:
                out(f"{cand['rank']:>6} · {cand['effort']} · {cand['note'].agent} #{cand['note'].pk} · {cand['title']}")
            return
        result = sprint.intake(weekly=True)
        out(f"Nowe bilety: {len(result['created'])}, wygasłe propozycje: {result['expired']}.")
        for ticket in BuildTicket.objects.filter(pk__in=result['created']):
            out(f'#{ticket.pk} [{ticket.effort}, {ticket.executor}, ranking {ticket.rank}] {ticket.title}')
