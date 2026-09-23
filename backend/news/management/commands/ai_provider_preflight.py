"""Read NIM/Groq configuration without contacting either provider."""
import json
import os

from django.core.management.base import BaseCommand
from django.utils import timezone


def present(name):
    return 'present' if os.environ.get(name, '').strip() else 'missing'


def enabled(name):
    return os.environ.get(name, '').strip().lower() == 'true'


class Command(BaseCommand):
    help = 'Read-only NIM/Groq preflight. It never sends a request or reveals secrets.'

    def handle(self, *args, **options):
        nim_fields = ['NIM_ENABLED', 'NIM_API_KEY', 'NIM_EMBEDDING_MODEL', 'NIM_EMBEDDING_URL',
                      'NIM_RERANK_MODEL', 'NIM_RERANK_URL']
        groq_fields = ['GROQ_EDITORIAL_ENABLED', 'GROQ_API_KEY', 'GROQ_EDITORIAL_MODEL', 'GROQ_EDITORIAL_URL']
        nim_ready = all(present(field) == 'present' for field in nim_fields[1:])
        groq_ready = all(present(field) == 'present' for field in groq_fields[1:])
        payload = {
            'checked_at': timezone.now().isoformat(),
            'nim': {
                'configuration': {field: present(field) for field in nim_fields},
                'enabled': enabled('NIM_ENABLED'),
                'ready_for_controlled_pilot': nim_ready,
            },
            'groq': {
                'configuration': {field: present(field) for field in groq_fields},
                'enabled': enabled('GROQ_EDITORIAL_ENABLED'),
                'ready_for_controlled_pilot': groq_ready,
            },
            'provider_access_tested': False,
            'network_calls_made': 0,
            'note': ('Klucze i modele mogą być gotowe, gdy przełączniki pozostają wyłączone. '
                     'Ten raport nie sprawdza salda, limitu ani dostępu dostawcy.'),
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
