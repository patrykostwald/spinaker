"""Record the reviewed API card for the first Sejm voting pilot.

The command is deliberately explicit: it never contacts either API and never
overrides a newer suspended/contact-required decision made by an editor.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from news.models import Source, SourceAccessInstruction
from scraper.official import API, official_source


OFFICIAL_APIS = (
    (
        'sejm',
        API + '/sejm/term10/votings',
        API + '/sejm.html',
        'Publiczna dokumentacja API Sejmu opisuje głosowania i stronicowanie; karta obejmuje wyłącznie ścieżkę głosowań kadencji 10.',
    ),
)


class Command(BaseCommand):
    help = 'Tworzy lokalną, wersjonowaną kartę dostępu dla pilotażu głosowań Sejmu.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
            help='Zapisuje karty; bez flagi pokazuje jedynie plan.')
        parser.add_argument('--valid-days', type=int, default=30)
        parser.add_argument('--evidence-url',
            help='Konkretny publiczny dokument lub regulamin sprawdzony dla tego dostępu.')
        parser.add_argument('--reviewed-by',
            help='Imię/nazwa osoby, która ręcznie sprawdziła zakres i dokument.')

    def handle(self, *args, **options):
        valid_days = options['valid_days']
        if not 1 <= valid_days <= 365:
            raise ValueError('valid-days musi być w zakresie 1–365.')
        now = timezone.now()
        if options['apply'] and (not options['evidence_url'] or not options['reviewed_by']):
            raise ValueError('--apply wymaga --evidence-url i --reviewed-by; komenda nie może sama tworzyć podstawy dostępu.')
        for provider, endpoint, terms_url, note in OFFICIAL_APIS:
            # Planning is an audit view, not a side effect.  In particular it
            # must not create a catalogue Source before an editor supplies the
            # reviewed evidence required by --apply.
            source = official_source(provider) if options['apply'] else Source.objects.filter(
                url=API + '/sejm').first()
            latest = (SourceAccessInstruction.objects.filter(
                source=source, channel=SourceAccessInstruction.Channel.API, endpoint=endpoint,
            ).order_by('-version').first() if source else None)
            if latest and latest.status != SourceAccessInstruction.Status.APPROVED:
                self.stdout.write(self.style.WARNING(
                    f'{provider}: pominięto — najnowsza karta ma status {latest.status}.'))
                continue
            if latest and latest.endpoint == endpoint and latest.valid_until and latest.valid_until > now:
                self.stdout.write(f'{provider}: aktualna karta v{latest.version} już istnieje.')
                continue
            version = (latest.version + 1) if latest else 1
            message = f'{provider}: karta API v{version}, zakres content, ważna {valid_days} dni.'
            if not options['apply']:
                self.stdout.write('PLAN ' + message)
                continue
            SourceAccessInstruction.objects.create(
                source=source,
                version=version,
                status=SourceAccessInstruction.Status.APPROVED,
                channel=SourceAccessInstruction.Channel.API,
                allowed_scope=SourceAccessInstruction.Scope.CONTENT,
                endpoint=endpoint,
                terms_url=terms_url,
                evidence={
                    'documentation_url': options['evidence_url'],
                    'basis': note,
                    'review_method': 'public-official-api-documentation',
                    'reviewed_on': now.date().isoformat(),
                },
                minimum_interval_seconds=3,
                reviewed_at=now,
                reviewed_by=options['reviewed_by'],
                valid_until=now + timedelta(days=valid_days),
            )
            self.stdout.write(self.style.SUCCESS('ZAPISANO ' + message))
