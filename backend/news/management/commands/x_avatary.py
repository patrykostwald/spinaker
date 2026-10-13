"""Miniatury kont X (news/x_avatars.py). Bez harmonogramu - uruchamia właściciel albo beat po zgodzie.

python manage.py x_avatary odswiez --dry-run                 (ile kont, wywołań i USD - bez API)
python manage.py x_avatary odswiez [--limit 200] [--starsze-niz 30]
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Miniatury kont X: GET /2/users/by (100 kont na wywołanie) w budżecie odczytów X.'

    def add_arguments(self, parser):
        sub = parser.add_subparsers(dest='action', required=True)
        run = sub.add_parser('odswiez')
        run.add_argument('--limit', type=int, default=200)
        run.add_argument('--dry-run', action='store_true')
        run.add_argument('--starsze-niz', type=int, default=30, help='Odświeżaj konta sprawdzone dawniej niż N dni (min. 30).')

    def handle(self, *args, **opts):
        from news import x_avatars
        if not 1 <= opts['limit'] <= 1000:
            raise CommandError('--limit 1-1000.')
        try:
            result = x_avatars.refresh(limit=opts['limit'], older_than_days=max(30, opts['starsze_niz']), dry_run=opts['dry_run'])
        except x_avatars.AvatarError as error:
            raise CommandError(str(error)) from None
        self.stdout.write(json.dumps(result, ensure_ascii=False))
