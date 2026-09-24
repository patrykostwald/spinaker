"""Record one editorial source decision without enabling access."""
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.models import Source, SourceReviewDecision


class Command(BaseCommand):
    help = 'Zapisuje decyzję dla jednego kandydata; nie tworzy karty dostępu i nie pobiera danych.'

    def add_arguments(self, parser):
        parser.add_argument('--source-host', required=True)
        parser.add_argument('--decision', choices=SourceReviewDecision.Decision.values, required=True)
        parser.add_argument('--reason', required=True)
        parser.add_argument('--evidence-url', action='append', default=[])
        parser.add_argument('--reviewed-by', default='redakcja spin.clinic')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        host = options['source_host'].strip().lower().removeprefix('www.')
        matches = [source for source in Source.objects.filter(
            catalog_stage='candidate', is_active=False, scrape_enabled=False,
        ) if (urlsplit(source.url or '').hostname or '').lower().removeprefix('www.') == host]
        if len(matches) != 1:
            raise CommandError(f'Host musi wskazywać dokładnie jednego nieaktywnego kandydata; znaleziono {len(matches)}.')
        source = matches[0]
        if not options['apply']:
            self.stdout.write(f'PLAN: {source.pk} {source.name}; {options["decision"]}.')
            return
        decision, _ = SourceReviewDecision.objects.update_or_create(
            source=source,
            defaults={
                'decision': options['decision'], 'reason': options['reason'],
                'evidence_urls': options['evidence_url'], 'audit_snapshot': {},
                'reviewed_by': options['reviewed_by'], 'reviewed_at': timezone.now(),
                'is_automated': False,
            },
        )
        decision.full_clean()
        decision.save()
        self.stdout.write(self.style.SUCCESS(f'ZAPISANO: {source.pk} {source.name}; {decision.decision}.'))
