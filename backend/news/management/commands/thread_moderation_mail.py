from django.core.management.base import BaseCommand
from news.thread_moderation import deliver_mail


class Command(BaseCommand):
    help = 'Ponów niewysłane powiadomienia o decyzjach moderacji spinek.'

    def handle(self, **options):
        deliver_mail()
