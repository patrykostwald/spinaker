from django.core.management.base import BaseCommand, CommandError
from scraper.official import import_voting, import_voting_search, import_voting_period, import_eli_year, import_print, import_prints


class Command(BaseCommand):
    help = 'Import official Sejm / ELI records, without generating editorial threads.'

    def add_arguments(self, parser):
        parser.add_argument('--term', type=int, default=10)
        parser.add_argument('--title')
        parser.add_argument('--sitting', type=int)
        parser.add_argument('--vote', type=int)
        parser.add_argument('--print-number')
        parser.add_argument('--journal', choices=['DU', 'MP'])
        parser.add_argument('--year', type=int)
        parser.add_argument('--from-date')
        parser.add_argument('--to-date')
        parser.add_argument('--all-prints', action='store_true')

    def handle(self, *args, **opts):
        try:
            if opts['all_prints']:
                count = import_prints(opts['term'])
            elif opts['from_date'] and opts['to_date']:
                from datetime import date
                start, end = date.fromisoformat(opts['from_date']), date.fromisoformat(opts['to_date'])
                if start > end:
                    raise CommandError('Date range reversed.')
                count = import_voting_period(opts['term'], start.isoformat(), end.isoformat())
            elif opts['title']:
                count = import_voting_search(opts['term'], opts['title'])
            elif opts['sitting'] and opts['vote']:
                count = import_voting(opts['term'], opts['sitting'], opts['vote'])
            elif opts['print_number']:
                count = import_print(opts['term'], opts['print_number'])
            elif opts['journal'] and opts['year']:
                count = import_eli_year(opts['journal'], opts['year'])
            else:
                raise CommandError('Choose --title, --sitting/--vote, --print-number, or --journal/--year.')
        except (KeyError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f'New official records: {int(count)}'))
