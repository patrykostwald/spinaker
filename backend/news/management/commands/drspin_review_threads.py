from django.core.management.base import BaseCommand
from news.thread_review import run_queue, backfill_queue


class Command(BaseCommand):
    help = 'Sprawdź kolejkę spinek wyłącznie darmowymi modelami w istniejących limitach.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=5)

    def handle(self, **options):
        backfill_queue(limit=max(0, options['limit']))
        self.stdout.write(str(run_queue(limit=max(0, options['limit']))))
