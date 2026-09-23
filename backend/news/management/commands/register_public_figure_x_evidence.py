"""Queue a manually evidenced public-figure X link for editorial review."""
from urllib.parse import urlsplit

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError

from news.political_models import PublicFigure, SocialHandleEvidence


def https_url(value, label):
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise CommandError(f'{label} musi być bezpośrednim adresem HTTPS.')
    return value


class Command(BaseCommand):
    help = ('Dodaje wyłącznie ręcznie wskazany, publiczny dowód linku X dla istniejącej osoby publicznej; '
            'nie pyta API X i nie włącza pobierania.')

    def add_arguments(self, parser):
        parser.add_argument('--figure-id', type=int, required=True)
        parser.add_argument('--handle', required=True)
        parser.add_argument('--evidence-url', required=True)
        parser.add_argument('--x-url', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        figure = PublicFigure.objects.filter(pk=options['figure_id'], archived=False).first()
        if figure is None:
            raise CommandError('Nie znaleziono aktywnej osoby publicznej o tym figure-id.')
        evidence_url = https_url(options['evidence_url'], 'evidence-url')
        x_url = https_url(options['x_url'], 'x-url')
        if (urlsplit(x_url).hostname or '').lower() not in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'}:
            raise CommandError('x-url musi prowadzić bezpośrednio do x.com lub twitter.com.')
        item = SocialHandleEvidence(
            subject_content_type=ContentType.objects.get_for_model(PublicFigure), subject_object_id=figure.pk,
            handle=options['handle'].lstrip('@'), evidence_url=evidence_url, extracted_url=x_url,
        )
        item.full_clean()
        if not options['apply']:
            self.stdout.write(f'PODGLĄD: @{item.handle} dla {figure.canonical_name}; bez zapisu i bez zapytania do X.')
            return
        item.save()
        self.stdout.write(self.style.SUCCESS(
            f'Dodano dowód @{item.handle} dla {figure.canonical_name} do kolejki redakcyjnej. Nie wykonano zapytania do X.'
        ))
