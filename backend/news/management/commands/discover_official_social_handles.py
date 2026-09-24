"""Stage explicitly linked X accounts from approved official roster pages."""
from django.core.management.base import BaseCommand, CommandError

from news.political_models import ParliamentaryRosterEntry
from news.social_handle_discovery import SocialDiscoveryError, discover_for_entry


class Command(BaseCommand):
    help = 'Wykrywa tylko jawnie podlinkowane konta X na profilach oficjalnych; nie dotyka API X ani kandydatur.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True, choices=['sejm', 'senat', 'ep'])
        parser.add_argument('--limit', type=int, default=25)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        if options['limit'] < 1 or options['limit'] > 100:
            raise CommandError('--limit musi być liczbą od 1 do 100.')
        entries = ParliamentaryRosterEntry.objects.filter(source=options['source'], active=True).order_by('pk')[:options['limit']]
        checked = found = failed = 0
        for entry in entries:
            checked += 1
            try:
                result = discover_for_entry(entry, persist=not options['dry_run'])
            except SocialDiscoveryError as exc:
                failed += 1
                self.stderr.write(f'{entry.pk} {entry.full_name}: {exc}')
                continue
            found += len(result)
        mode = 'Podgląd, bez zapisu' if options['dry_run'] else 'Zapisano wyłącznie dowody do przeglądu'
        self.stdout.write(self.style.SUCCESS(f'{mode}: sprawdzono {checked}; znaleziono {found} jawnych linków X; pominięto {failed}. Nie użyto API X i nie utworzono kandydatur.'))
