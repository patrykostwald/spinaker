from django.core.management.base import BaseCommand
from news.thread_review import run_queue, backfill_queue


class Command(BaseCommand):
    help = 'Sprawdź kolejkę spinek wyłącznie darmowymi modelami w istniejących limitach.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=5)
        parser.add_argument('--retry-rejected', action='store_true',
                            help='Odrzucone spinki wracają do kontroli od pierwszego kroku (np. po poprawce kontrolerów).')

    def handle(self, **options):
        from news.features import threads_enabled, threads_disabled_result
        if not threads_enabled():
            self.stdout.write(str(threads_disabled_result()))
            return
        if options['retry_rejected']:
            from news.thread_review_models import ThreadReview
            rows = ThreadReview.objects.filter(status='rejected')
            for review in rows:
                review.status, review.step, review.next_attempt_at = 'pending', 0, None
                review.working_texts = review.payload.get('texts', review.working_texts)
                review.revision += 1
                review.save(update_fields=['status', 'step', 'next_attempt_at', 'working_texts', 'revision', 'updated_at'])
                from news.thread_review import _apply, visible_statuses
                _apply(review, review.status in visible_statuses())
            self.stdout.write(f'Do ponownej kontroli: {rows.model.objects.filter(status="pending").count()}')
        backfill_queue(limit=max(0, options['limit']))
        self.stdout.write(str(run_queue(limit=max(0, options['limit']))))
