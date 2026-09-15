"""Human-readable, read-only status for the narrow Sejm vote pilot."""

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from news.models import (FetchAttempt, OfficialRecord, Source,
    SourceAccessInstruction, SourceDailyFetchBudget)
from scraper.official import API


class Command(BaseCommand):
    help = 'Pokazuje stan pilota głosowań Sejmu bez wykonywania pobrań.'

    def handle(self, *args, **options):
        source = Source.objects.filter(url=API + '/sejm').first()
        if not source:
            self.stdout.write('PILOT: brak skonfigurowanego źródła Sejmu.')
            return
        card = SourceAccessInstruction.objects.filter(
            source=source, channel=SourceAccessInstruction.Channel.API,
            endpoint=API + '/sejm/term10/votings',
        ).order_by('-version').first()
        if not card:
            self.stdout.write('PILOT: brak karty dostępu.')
            return
        today = timezone.localdate()
        used = SourceDailyFetchBudget.objects.filter(
            instruction=card, day=today).values_list('used', flat=True).first() or 0
        attempts = FetchAttempt.objects.filter(source=source, instruction=card)
        outcomes = dict(attempts.values('outcome').annotate(total=Count('id')).values_list('outcome', 'total'))
        last = attempts.order_by('-attempted_at', '-id').first()
        records = OfficialRecord.objects.filter(provider='sejm', fetch_attempt__instruction=card).count()

        self.stdout.write(f'PILOT: karta v{card.version} — {card.status}.')
        self.stdout.write(f'DZIŚ: {used}/{card.daily_request_cap} zarezerwowanych żądań.')
        self.stdout.write(f'REKORDY: {records}.')
        self.stdout.write('PRÓBY: ' + (', '.join(f'{key}={value}' for key, value in sorted(outcomes.items())) or 'brak.'))
        if last:
            detail = f'{last.outcome}; HTTP {last.http_status}' if last.http_status else f'{last.outcome}; {last.error_code or "bez kodu"}'
            self.stdout.write(f'OSTATNIA: {last.attempted_at.isoformat()} — {detail}.')
