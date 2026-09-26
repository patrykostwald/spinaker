"""Potwierdza kanały YouTube źródeł znalezione przez discover_source_social_links i włącza pobieranie metadanych.

Dowodem jest link do kanału na stronie głównej źródła (evidence_url). Pobieramy wyłącznie metadane przez
oficjalne YouTube Data API: tytuł, datę, miniaturę z YouTube i link do filmu w YouTube. Bez --apply: podgląd.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news import youtube_collect
from news.models import Source
from news.political_models import OfficialVideoChannel


class Command(BaseCommand):
    help = 'Potwierdza kanały YouTube źródeł (z dowodem ze strony źródła). --exclude: id kanałów UC… do pominięcia.'

    def add_arguments(self, parser):
        parser.add_argument('--staff', required=True, help='Login członka zespołu, który potwierdza kanały.')
        parser.add_argument('--exclude', nargs='*', default=[], help='Identyfikatory kanałów, których nie potwierdzać.')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, staff, exclude, apply, **options):
        reviewer = get_user_model().objects.filter(username=staff, is_staff=True, is_active=True).first()
        if reviewer is None:
            raise CommandError('Nie ma aktywnego konta zespołu o takim loginie.')
        rows = (OfficialVideoChannel.objects.filter(status='pending_review', subject_content_type__model='source')
                .exclude(channel_id='').exclude(evidence_url='').order_by('display_name'))
        confirmed = 0
        for row in rows:
            if row.channel_id in exclude:
                self.stdout.write(f'POMINIĘTO  {row.display_name}  ({row.channel_id})')
                continue
            subject = Source.objects.filter(pk=row.subject_object_id).first()
            self.stdout.write(f'{"POTWIERDZONO" if apply else "POTWIERDZI"}  {row.display_name}  ({row.channel_id})  '
                              f'dowód: {row.evidence_url}  źródło: {subject.name if subject else "?"}')
            if apply:
                row.status, row.reviewed_by, row.reviewed_at, row.collection_enabled = 'confirmed', reviewer, timezone.now(), True
                row.full_clean()
                row.save()
                youtube_collect.channel_source(row)
            confirmed += 1
        self.stdout.write(f'{"Potwierdzono" if apply else "Do potwierdzenia"}: {confirmed}' + ('' if apply else ' — uruchom z --apply.'))
