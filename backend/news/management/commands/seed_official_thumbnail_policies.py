"""Persist conservative thumbnail decisions for reviewed official sources."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Source, SourceThumbnailPolicy


GOV_TERMS = 'https://www.gov.pl/web/mswia/aktualnosci'
SENAT_TERMS = 'https://www.senat.gov.pl/ponowne-wykorzystywanie-informacji-sektora-publicznego/'
UOKIK_TERMS = 'https://uokik.gov.pl/bip/wnioskowanie-o-dostep-do-informacji-sektora-publicznego-w-celu-jej-ponownego-wykorzystywania'


def specification(source):
    host = (source.url or '').lower()
    if 'senat.gov.pl' in host:
        return SENAT_TERMS, {
            'decision': 'review_required',
            'reason': 'Senate reuse terms exclude PAP photographs. No image is eligible until its own author and rights are checked.',
            'excluded': ['PAP', 'unattributed photographs', 'third-party photographs'],
        }
    if 'gov.pl' in host:
        return GOV_TERMS, {
            'decision': 'review_required',
            'reason': 'gov.pl separates text licensing from audiovisual material including photographs; do not derive thumbnails from the general text licence.',
            'excluded': ['images', 'video', 'audio', 'unattributed third-party assets'],
        }
    if 'uokik.gov.pl' in host:
        return UOKIK_TERMS, {
            'decision': 'review_required',
            'reason': 'UOKiK reuse permission supports attributed information; it does not establish a blanket image licence.',
            'excluded': ['images', 'third-party assets'],
        }
    return None


class Command(BaseCommand):
    help = 'Zapisuje konserwatywne zasady miniaturek dla zatwierdzonych źródeł urzędowych.'

    def add_arguments(self, parser):
        parser.add_argument('--reviewed-by', default='redakcja spin.clinic')
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        rows = []
        for source in Source.objects.filter(is_active=True, scrape_enabled=True).order_by('pk'):
            item = specification(source)
            if item:
                rows.append((source, *item))
        if not options['apply']:
            self.stdout.write(f'PLAN: zapiszę {len(rows)} polityk miniaturek; żadna nie dopuszcza jeszcze pobierania obrazu.')
            return
        now = timezone.now()
        for source, terms_url, evidence in rows:
            SourceThumbnailPolicy.objects.update_or_create(
                source=source,
                defaults={
                    'status': SourceThumbnailPolicy.Status.REVIEW_REQUIRED,
                    'terms_url': terms_url,
                    'license_url': '',
                    'attribution_template': '',
                    'evidence': evidence,
                    'reviewed_at': now,
                    'reviewed_by': options['reviewed_by'],
                },
            )
        self.stdout.write(self.style.SUCCESS(f'ZAPISANO: {len(rows)} polityk miniaturek.'))
