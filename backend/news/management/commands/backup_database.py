from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Create and integrity-check a local SQLite backup without deleting previous copies.'
    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if not db['ENGINE'].endswith('sqlite3'):
            raise CommandError('Production PostgreSQL requires pg_dump and independent off-server backup storage; see docs/DEPLOYMENT.md.')
        folder = settings.ROOT_DIR / '.local' / 'backups'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / ('portal-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
        with sqlite3.connect(db['NAME']) as source, sqlite3.connect(path) as target:
            source.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise CommandError('Backup integrity check failed.')
        self.stdout.write('Verified local database backup: ' + str(path))
