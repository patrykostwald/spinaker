import secrets
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create a development-only admin and store its generated password outside versioned files.'

    def handle(self, *args, **options):
        if not settings.DEBUG or not settings.DATABASES['default']['ENGINE'].endswith('sqlite3'):
            raise CommandError('Only available in local DEBUG + SQLite mode.')
        users = get_user_model()
        if users.objects.filter(is_staff=True).exists():
            self.stdout.write('An editor already exists; no account or password was changed.')
            return
        if users.objects.filter(username='admin').exists():
            raise CommandError('Username admin already exists; create an editor manually.')
        directory = Path(settings.ROOT_DIR) / '.local'
        directory.mkdir(exist_ok=True)
        credentials = directory / 'admin-login.txt'
        password = secrets.token_urlsafe(24)
        # Exclusive creation avoids accidentally replacing a saved credential file.
        with credentials.open('x', encoding='utf-8') as handle:
            handle.write('Lokalny warsztat redakcji: http://localhost:3000/editor\nLogin: admin\nHasło: ' + password + '\n\nTylko lokalny podgląd. Nie używaj tego pliku w publicznym wdrożeniu.\n')
        try:
            users.objects.create_superuser(username='admin', email='', password=password)
        except Exception:
            credentials.unlink()
            raise
        self.stdout.write('Local editor created. Credentials: ' + str(credentials))
