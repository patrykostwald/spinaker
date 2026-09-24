from django.core.management.base import BaseCommand

from scraper.fetch_reaper import DEFAULT_MAX_AGE_SECONDS, reap_incomplete_fetches


class Command(BaseCommand):
    help = 'Domyka stare rezerwacje audytowe jako nieukończone próby; nie pobiera danych.'

    def add_arguments(self, parser):
        parser.add_argument('--max-age-seconds', type=int, default=DEFAULT_MAX_AGE_SECONDS)

    def handle(self, *args, **options):
        age = options['max_age_seconds']
        if age < DEFAULT_MAX_AGE_SECONDS:
            raise ValueError(f'max-age-seconds musi wynosić co najmniej {DEFAULT_MAX_AGE_SECONDS}.')
        result = reap_incomplete_fetches(max_age_seconds=age)
        self.stdout.write(f"nieukończone={result['reaped']} wstrzymane_karty={result['suspended']}")
