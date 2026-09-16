from django.core.management.base import BaseCommand, CommandError

from news.mailbox import SourceMailboxDisabled, sync_inbound


class Command(BaseCommand):
    help = 'Odczytuje nagłówki odpowiedzi ze skrzynki źródeł; nigdy nie wysyła wiadomości.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 500:
            raise CommandError('limit musi mieścić się w zakresie 1..500')
        try:
            result = sync_inbound(limit=options['limit'])
        except SourceMailboxDisabled as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(str(result)))
