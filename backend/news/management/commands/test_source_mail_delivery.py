from django.core.management.base import BaseCommand, CommandError

from news.mailbox import SourceMailboxDisabled, send_delivery_test


class Command(BaseCommand):
    help = 'Sends one explicit delivery-control message for the source mailbox.'

    def add_arguments(self, parser):
        parser.add_argument('--to', required=True)

    def handle(self, *args, **options):
        try:
            send_delivery_test(options['to'])
        except SourceMailboxDisabled as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS('delivery_test_sent'))
