"""Jednorazowe sprzątanie pętli agentów po audycie 5.10 (bez AI, bez sieci).

python manage.py porzadki_petli             - tylko pokazuje, co zmieni
python manage.py porzadki_petli --wykonaj   - zmienia:
  1. powtórzone otwarte wpisy Opiekuna (ta sama rola, pętla i rodzaj błędu): zostaje najnowszy, starsze - odrzucone,
     ich kolejka Seby zamknięta (żeby nie zjadały dziennego limitu Seby);
  2. oceny Seby zablokowane błędem „Nieznana firma autora” wracają do kolejki (seba.author() ma już domyślną firmę)."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


def cleanup(apply=False):
    from news import opiekunowie
    from news.agent_models import AgentNote, SebaReview
    stale = []
    for key, notes in opiekunowie.duplicate_groups().items():
        stale += [n.pk for n in notes[1:]]  # notes[0] to najnowszy wpis tej grupy
    blocked = SebaReview.objects.filter(status='queued', last_error__startswith='Nieznana firma autora')
    out = {'opiekun_duplikaty': len(stale), 'seba_odblokowane': blocked.count()}
    if apply:
        now = timezone.now()
        with transaction.atomic():
            AgentNote.objects.filter(pk__in=stale).update(status='rejected', decided_at=now)
            SebaReview.objects.filter(note_id__in=stale, status='queued').update(status='rejected', last_error='Duplikat wpisu Opiekuna.')
            blocked.update(due_at=now, last_error='', lease_until=None, lease_token='')
    return out


class Command(BaseCommand):
    help = 'Sprząta powtórzone wpisy Opiekuna i odblokowuje kolejkę Seby (audyt pętli 5.10).'

    def add_arguments(self, parser):
        parser.add_argument('--wykonaj', action='store_true', help='zapisz zmiany (bez tego tylko podgląd)')

    def handle(self, *args, **options):
        out = cleanup(options['wykonaj'])
        mode = 'Zmienione' if options['wykonaj'] else 'Do zmiany (podgląd, dodaj --wykonaj)'
        self.stdout.write(f"{mode}: duplikaty Opiekuna {out['opiekun_duplikaty']}, oceny Seby z powrotem w kolejce {out['seba_odblokowane']}")
