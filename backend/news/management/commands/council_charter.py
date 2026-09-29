"""Przyjęcie pełnej Karty przez skonfigurowane modele."""
import json

from django.core.management.base import BaseCommand

from news.clinic_ai import ClinicAIError
from news.clinic_council import ask
from news.clinic_models import CouncilCharterAcceptance
from news.council_charter import charter, roster

SCHEMA = {'type': 'object', 'properties': {'accepts': {'type': 'boolean'}, 'statement': {'type': 'string'}},
          'required': ['accepts', 'statement']}


class Command(BaseCommand):
    help = 'Pyta modele o przyjęcie Karty; --dry-run pokazuje plan bez API i zapisów.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        text, version, digest = charter()
        for row in roster():
            if row['status'] != 'dostępny':
                continue
            if options['dry_run']:
                self.stdout.write(f"{row['provider']}:{row['model']} — Karta {version}, {digest}")
                continue
            try:
                answer = ask((row['provider'], row['model']),
                             'Przeczytaj pełną Kartę. Czy przyjmujesz wszystkie zasady? '
                             'Zwróć JSON: accepts (bool), statement (jedno zdanie po polsku).',
                             text, SCHEMA, max_tokens=500)
                if type(answer.get('accepts')) is not bool or not isinstance(answer.get('statement'), str) or not answer['statement'].strip():
                    raise ClinicAIError('invalid_charter_response')
                answer = {'accepts': answer['accepts'], 'statement': answer['statement'].strip()[:1000]}
            except ClinicAIError as error:
                self.stderr.write(f"{row['model']}: brak odpowiedzi ({error.code})")
                continue
            CouncilCharterAcceptance.objects.create(model=row['model'], provider=row['provider'], company=row['company'],
                                                    charter_version=version, charter_hash=digest, response=answer)
            self.stdout.write(json.dumps({'model': row['model'], **answer}, ensure_ascii=False))
