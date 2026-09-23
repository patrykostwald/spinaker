"""Configure the reviewed KPRM news listing as a metadata-only pilot."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from news.models import Source, SourceAccessInstruction


SOURCE_URL = 'https://www.gov.pl/web/premier/rss'
LISTING_URL = 'https://www.gov.pl/web/premier/wydarzenia'
TERMS_URL = 'https://www.gov.pl/web/premier/ponowne-wykorzystywanie'
ROBOTS_URL = 'https://www.gov.pl/robots.txt'


def configure(source, reviewer, valid_days=180):
    latest = SourceAccessInstruction.objects.filter(source=source).order_by('-version').first()
    if latest and latest.status == SourceAccessInstruction.Status.SUSPENDED:
        raise CommandError('Najnowsza karta KPRM jest wstrzymana; nie można jej automatycznie odnowić.')
    now = timezone.now()
    common = {
        'status': SourceAccessInstruction.Status.APPROVED,
        'terms_url': TERMS_URL,
        'evidence': {
            'listing_url': LISTING_URL,
            'terms_url': TERMS_URL,
            'scope': 'KPRM news listing and its direct item metadata only; no full-text storage, PDFs, images, audio or video.',
            'attribution': 'Preserve KPRM source URL and acquisition time on every box.',
        },
        # Separate HTML and robots cards each receive half of the 24-request source cap.
        'minimum_interval_seconds': 3, 'daily_request_cap': 12,
        'reviewed_at': now, 'reviewed_by': reviewer, 'valid_until': now + timedelta(days=valid_days),
    }
    version = (latest.version if latest else 0) + 1
    card = SourceAccessInstruction.objects.create(
        source=source, version=version, channel=SourceAccessInstruction.Channel.HTML,
        allowed_scope=SourceAccessInstruction.Scope.METADATA,
        endpoint='https://www.gov.pl/web/premier', allowed_path_patterns=[], **common)
    SourceAccessInstruction.objects.create(
        source=source, version=version + 1, channel=SourceAccessInstruction.Channel.SITEMAP,
        allowed_scope=SourceAccessInstruction.Scope.METADATA,
        endpoint=ROBOTS_URL, allowed_path_patterns=['/robots.txt'], **common)
    source.url = SOURCE_URL
    source.is_active = True
    source.scrape_enabled = True
    source.catalog_stage = 'configured'
    source.save(update_fields=['url', 'is_active', 'scrape_enabled', 'catalog_stage', 'updated_at'])
    return card


class Command(BaseCommand):
    help = 'Zapisuje ograniczoną kartę KPRM: metadane aktualności z własnej sekcji premiera.'

    def add_arguments(self, parser):
        parser.add_argument('--reviewed-by', default='redakcja spin.clinic')
        parser.add_argument('--valid-days', type=int, default=180)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if not 1 <= options['valid_days'] <= 730:
            raise CommandError('valid-days musi wynosić 1..730.')
        source = Source.objects.filter(url=SOURCE_URL).first()
        if source is None:
            raise CommandError('Brakuje kandydatury KPRM w katalogu; nie tworzę źródła poza katalogiem.')
        if not options['apply']:
            self.stdout.write('PLAN: KPRM — metadane własnej sekcji, 24 żądania/dzień, bez zapisu pełnej treści.')
            return
        card = configure(source, options['reviewed_by'], options['valid_days'])
        self.stdout.write(self.style.SUCCESS(
            f'ZAPISANO KPRM: karta HTML v{card.version}, zakres metadane, 24 żądania/dzień.'))
