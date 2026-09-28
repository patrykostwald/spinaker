"""Wątki silnych spinów z konta spin.clinic na X.

  python manage.py x_publish --dry-run   # pokaż, co zostałoby opublikowane (nic nie wysyła)
  python manage.py x_publish             # publikuje (wymaga X_POST_ENABLED=true i kluczy z uprawnieniem zapisu)
"""
from django.core.management.base import BaseCommand

from news.x_publish import run


class Command(BaseCommand):
    help = 'Publikuje wątki silnych spinów z konta spin.clinic (albo pokazuje je w trybie --dry-run).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, dry_run, **options):
        result = run(dry_run=dry_run)
        if dry_run:
            for item in result['results']:
                self.stdout.write(f"— diagnoza {item['id']}:")
                for text in item['posts']:
                    self.stdout.write(f'   {text}\n')
                if item.get('author_reply'):
                    self.stdout.write(f"   [komentarz pod wpisem polityka] {item['author_reply']}\n")
            if not result['results']:
                self.stdout.write('Brak spinów od progu X_POST_MIN_INTENSITY z ostatniej doby.')
        else:
            self.stdout.write(str(result))
