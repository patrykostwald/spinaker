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
        parser.add_argument('--missing', action='store_true', help='tylko modele bez zapisanej odpowiedzi na tę wersję Karty')

    def handle(self, *args, **options):
        text, version, digest = charter()
        done = set(CouncilCharterAcceptance.objects.filter(charter_version=version, charter_hash=digest).values_list('model', flat=True))
        for row in roster():
            if row['status'] != 'dostępny' or (options['missing'] and row['model'] in done):
                continue
            if options['dry_run']:
                self.stdout.write(f"{row['provider']}:{row['model']} — Karta {version}, {digest}")
                continue
            answer, last_error = None, None
            # Modele z rozumowaniem zużywają część limitu przed odpowiedzią — stąd zapas tokenów i druga próba.
            for _attempt in range(2):
                try:
                    reply = ask((row['provider'], row['model']),
                                'Przeczytaj pełną Kartę. Czy przyjmujesz wszystkie zasady? '
                                'Odpowiedz wyłącznie obiektem JSON: accepts (bool), statement (jedno zdanie po polsku).',
                                text, SCHEMA, max_tokens=3000)
                    if type(reply.get('accepts')) is not bool or not isinstance(reply.get('statement'), str) or not reply['statement'].strip():
                        raise ClinicAIError('invalid_charter_response')
                    answer = {'accepts': reply['accepts'], 'statement': reply['statement'].strip()[:1000]}
                    break
                except ClinicAIError as error:
                    last_error = error
            if answer is None:
                self.stderr.write(f"{row['model']}: brak odpowiedzi ({getattr(last_error, 'code', last_error)})")
                continue
            CouncilCharterAcceptance.objects.create(model=row['model'], provider=row['provider'], company=row['company'],
                                                    charter_version=version, charter_hash=digest, response=answer)
            self.stdout.write(json.dumps({'model': row['model'], **answer}, ensure_ascii=False))
