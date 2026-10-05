"""Zlecenia ze Sprintu tygodnia dla Claude i Codexa (audyt pętli 5.3).

python manage.py sprint_zlecenia                         - zatwierdzone bilety jako gotowe zlecenia do wklejenia
python manage.py sprint_zlecenia --wszystkie             - także propozycje czekające na decyzję
python manage.py sprint_zlecenia --biore 12              - bilet w budowie
python manage.py sprint_zlecenia --zrobione 12 --commit abc1234
                                                         - zamyka bilet; notatka agenta dostaje status done"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Zatwierdzone bilety Sprintu tygodnia jako zlecenia; --zrobione <id> --commit <sha> zamyka bilet.'

    def add_arguments(self, parser):
        parser.add_argument('--zrobione', type=int)
        parser.add_argument('--commit', default='')
        parser.add_argument('--biore', type=int)
        parser.add_argument('--wszystkie', action='store_true')

    def handle(self, *args, **options):
        from news import sprint
        from news.agent_models import BuildTicket
        out = self.stdout.write
        if options['zrobione']:
            if not options['commit'].strip():
                raise CommandError('Podaj --commit <sha>.')
            ticket = BuildTicket.objects.filter(pk=options['zrobione']).first()
            if not ticket:
                raise CommandError(f"Brak biletu #{options['zrobione']}.")
            if ticket.status in ('done', 'dropped'):
                raise CommandError(f'Bilet #{ticket.pk} jest już zamknięty ({ticket.status}).')
            sprint.close(ticket, options['commit'].strip())
            out(f'Bilet #{ticket.pk} zrobiony ({ticket.commit}). Notatka źródłowa: '
                f"{'#' + str(ticket.note_id) + ' ' + ticket.note.status if ticket.note else 'brak'}.")
            return
        if options['biore']:
            ticket = BuildTicket.objects.filter(pk=options['biore'], status='approved').first()
            if not ticket:
                raise CommandError(f"Brak zatwierdzonego biletu #{options['biore']}.")
            ticket.status = 'in_progress'
            ticket.save(update_fields=['status'])
            out(f'Bilet #{ticket.pk} w budowie.')
            return
        statuses = ('approved', 'in_progress') + (('proposed',) if options['wszystkie'] else ())
        rows = list(BuildTicket.objects.select_related('note').filter(status__in=statuses).order_by('due_date', '-rank', 'pk'))
        if not rows:
            out('Brak zatwierdzonych biletów. Decyzje: panel Agenci, karta „Sprint tygodnia”.')
            return
        for ticket in rows:
            label = '' if ticket.status == 'approved' else f' [{ticket.status}]'
            out(sprint.brief(ticket) + label)
            out('')
