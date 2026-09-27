"""Agent „Występuje w podmiotach”: wyszukanie (Gemini + Google) i weryfikacja w oficjalnym KRS.

Przykłady:
  python manage.py krs_agent --figure 164        # jedna osoba (id profilu)
  python manage.py krs_agent --limit 5           # pięć kolejnych osób z kolejki
"""
from django.core.management.base import BaseCommand, CommandError

from news import krs_agent
from news.political_models import PublicFigure


class Command(BaseCommand):
    help = 'Szuka fundacji, stowarzyszeń i spółek osób publicznych i potwierdza je w KRS.'

    def add_arguments(self, parser):
        parser.add_argument('--figure', type=int)
        parser.add_argument('--limit', type=int, default=5)

    def handle(self, *args, figure, limit, **options):
        if not krs_agent.clinic_ai._gemini_ready():
            raise CommandError('Brak GEMINI_API_KEY — agent korzysta z wyszukiwarki Gemini.')
        people = [PublicFigure.objects.get(pk=figure)] if figure else list(krs_agent.queue(limit))
        for person in people:
            if krs_agent.budget_left() <= 0:
                self.stdout.write('Dzienny limit KRS_DAILY_BUDGET_USD wyczerpany — reszta jutro.')
                break
            result = krs_agent.check_figure(person)
            self.stdout.write(f"{person.canonical_name}: kandydaci {result.get('candidates', 0)}, potwierdzone {result.get('confirmed', 0)}"
                              + (f" — błąd {result['error']}" if result.get('error') else ''))
            for relation in person.organisation_relations.filter(verification_status='confirmed').select_related('organisation'):
                org = relation.organisation
                self.stdout.write(f"   · {org.name} ({org.get_kind_display()}, KRS {org.krs_number}, {org.get_sector_display()}) — "
                                  f"{relation.public_role}, {relation.get_relation_status_display().lower()} [{relation.get_verification_method_display()}]")
        self.stdout.write(f'Pozostało w dzisiejszym limicie: {max(0, krs_agent.budget_left()):.2f} USD')
