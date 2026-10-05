import json

from django.core.management.base import BaseCommand

from news.public_record_people import link_people


class Command(BaseCommand):
    help = 'Dopina dokumenty Sejmu (interpelacje, zapytania, wystąpienia) do osób po oficjalnym id posła. Bez sieci, idempotentne.'

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(link_people(), ensure_ascii=False))
