"""Stage one directly evidenced official YouTube channel for editorial review."""
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from news.models import Source
from news.political_models import OfficialVideoChannel, PublicFigure, PublicOffice


SUBJECT_MODELS = {
    'public-figure': PublicFigure,
    'public-office': PublicOffice,
    'source': Source,
}


class Command(BaseCommand):
    help = ('Dodaje do kolejki redakcyjnej bezpośrednio udowodniony kanał YouTube. '
            'Nie wyszukuje YouTube i nie pobiera filmów ani napisów.')

    def add_arguments(self, parser):
        parser.add_argument('--subject-type', choices=sorted(SUBJECT_MODELS), required=True)
        parser.add_argument('--subject-id', type=int, required=True)
        parser.add_argument('--channel-url', required=True)
        parser.add_argument('--evidence-url', required=True)
        parser.add_argument('--display-name', default='')
        parser.add_argument('--channel-id', default='')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        model = SUBJECT_MODELS[options['subject_type']]
        subject = model.objects.filter(pk=options['subject_id']).first()
        if subject is None:
            raise CommandError('Nie znaleziono wskazanego profilu, funkcji ani źródła.')
        content_type = ContentType.objects.get_for_model(model)
        # Build before touching the database so invalid links never create rows.
        existing = OfficialVideoChannel.objects.filter(
            subject_content_type=content_type, subject_object_id=subject.pk,
            channel_url=options['channel_url'],
        ).first()
        channel = existing or OfficialVideoChannel(
            subject_content_type=content_type, subject_object_id=subject.pk,
            channel_url=options['channel_url'],
        )
        channel.display_name = options['display_name']
        channel.channel_id = options['channel_id']
        channel.evidence_url = options['evidence_url']
        channel.status = 'pending_review'
        channel.collection_enabled = False
        channel.source_checked_at = timezone.now()
        try:
            channel.full_clean()
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc
        label = 'nowy' if existing is None else 'do aktualizacji'
        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                f'PODGLĄD: kanał {label}; status pending_review. Bez zapisu, bez API YouTube i bez pobierania materiałów.'
            ))
            return
        with transaction.atomic():
            channel.save()
        self.stdout.write(self.style.SUCCESS(
            f'ZAPISANO: kanał {label}; status pending_review. Nie użyto API YouTube i nie pobrano materiałów ani napisów.'
        ))
