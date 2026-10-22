from datetime import date

from django.core.management.base import BaseCommand, CommandError

from news.clinic_models import ClinicDailyMessage
from news.message_stats import calculate_stats, post_rows


class Command(BaseCommand):
    help = 'Przelicz statystyki zapisanych źródeł przekazów, bez AI. Brakujące przypisania pozostają nieznane.'

    def add_arguments(self, parser):
        parser.add_argument('--since', required=True, help='Pierwszy dzień, RRRR-MM-DD (włącznie).')

    def handle(self, *args, **options):
        try:
            since = date.fromisoformat(options['since'])
        except ValueError as error:
            raise CommandError('Podaj datę w formacie RRRR-MM-DD.') from error
        count = 0
        for message in ClinicDailyMessage.objects.filter(day__gte=since).iterator(chunk_size=100):
            rows = post_rows(list(message.posts.select_related('account').all()))
            message.stats = calculate_stats(rows, message.points, message.tone)
            message.save(update_fields=['stats'])
            count += 1
        self.stdout.write(f'Przeliczono przekazy: {count}. Bez wywołań AI.')
