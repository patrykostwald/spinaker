"""Ponownie kolejkuj wyłącznie odrzucenia dwóch poprawionych strażników."""
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from news.thread_review_models import ThreadReview


ALLOWED_REASON = re.compile(
    r'[\w.]+: (?:słowo z listy zarzutów\.|nazwa własna spoza danych \([^();\n]+\)\.)')


def eligible_reason(reason):
    return bool(reason) and all(ALLOWED_REASON.fullmatch(part.strip()) for part in reason.split(';'))


class Command(BaseCommand):
    help = 'Plan ponownej kontroli odrzuconych nitek; --apply zapisuje kolejkę, bez publikacji.'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--plan', action='store_true')
        mode.add_argument('--apply', action='store_true')
        parser.add_argument('--limit', type=int, default=20)

    @transaction.atomic
    def handle(self, *args, **options):
        from news.features import threads_enabled, threads_disabled_result
        if not threads_enabled():
            self.stdout.write(str(threads_disabled_result()))
            return
        limit = options['limit']
        if limit < 0:
            raise CommandError('--limit musi być nieujemny.')
        rows = ThreadReview.objects.filter(status='rejected').order_by('pk')
        if options['apply']:
            rows = rows.select_for_update()
        rejected = eligible = 0
        selected = []
        for row in rows.iterator():
            rejected += 1
            if eligible_reason(row.reason):
                eligible += 1
                if len(selected) < limit:
                    selected.append(row.pk)
        changed = 0
        if options['apply']:
            changed = ThreadReview.objects.filter(pk__in=selected, status='rejected').update(
                status='pending', step=0, reason='', next_attempt_at=None)
        self.stdout.write(
            f"Tryb: {'apply' if options['apply'] else 'plan'}. Odrzucone: {rejected}; "
            f'kwalifikujące: {eligible}; wybrane: {len(selected)}; wznowione: {changed}.')
