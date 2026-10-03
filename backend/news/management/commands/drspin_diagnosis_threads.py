from datetime import date, datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.clinic_models import SpinDiagnosis
from news.diagnosis_threads import sync_diagnosis_thread


class Command(BaseCommand):
    help = 'Uzupełnij spinki wszystkich opublikowanych diagnoz, bez wywołań AI.'

    def add_arguments(self, parser):
        parser.add_argument('--since', help='Data publikacji od RRRR-MM-DD (włącznie).')

    def handle(self, *args, **options):
        rows = SpinDiagnosis.objects.all()
        if options['since']:
            try:
                since = timezone.make_aware(datetime.combine(date.fromisoformat(options['since']), time.min))
            except ValueError as exc:
                raise CommandError('Podaj --since w formacie RRRR-MM-DD.') from exc
            from django.db.models.functions import Coalesce
            rows = rows.annotate(publication=Coalesce('reviewed_at', 'diagnosed_at', 'created_at')).filter(publication__gte=since)
        count = 0
        for pk in rows.order_by('pk').values_list('pk', flat=True).iterator():
            if sync_diagnosis_thread(pk):
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Zsynchronizowano {count} spinek diagnoz.'))
