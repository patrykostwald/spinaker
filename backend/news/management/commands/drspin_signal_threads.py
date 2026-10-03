from django.core.management.base import BaseCommand
from news.signal_threads import build_lobbying, build_new_narratives


class Command(BaseCommand):
    help = 'Ułóż sygnały z danych lokalnych i dodaj do kolejki kontroli (bez AI i HTTP).'

    def handle(self, **options):
        self.stdout.write(str({'lobbying': build_lobbying(), 'narratives': build_new_narratives()}))
