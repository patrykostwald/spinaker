"""Zaległe diagnozy: wpisy od wskazanej daty, które nie doczekały się diagnozy (kolejka, oznaczone przez strażnika,
przejściowe błędy Konsylium). Najwyżej ocenione przez strażnika najpierw; w ramach dziennego budżetu."""
from datetime import datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from news.clinic import BUDGET_RESERVE_USD, budget_left, diagnose, figures_by_account
from news.clinic_models import SpinDiagnosis

TRANSIENT = ('council_too_few_members', '_daily_limit', 'timeout', 'connection', 'http_429', 'http_5')


class Command(BaseCommand):
    help = 'Diagnozuje zaległe wpisy od podanej daty (np. --since 2026-09-29 --limit 12).'

    def add_arguments(self, parser):
        parser.add_argument('--since', required=True, help='Data publikacji wpisu od (RRRR-MM-DD, czas Warszawy).')
        parser.add_argument('--limit', type=int, default=10)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, since, limit, dry_run, **options):
        try:
            start = timezone.make_aware(datetime.combine(datetime.strptime(since, '%Y-%m-%d').date(), time.min))
        except ValueError as error:
            raise CommandError('Data w formacie RRRR-MM-DD.') from error
        transient = Q()
        for code in TRANSIENT:
            transient |= Q(error__icontains=code)
        rows = list(SpinDiagnosis.objects.filter(post__published_at__gte=start, screen_score__isnull=False)
                    .filter(Q(status__in=['queued', 'flagged']) | (Q(status='failed') & transient))
                    .select_related('post__account').order_by('-screen_score', '-post__published_at')[:limit])
        self.stdout.write(f'Do diagnozy: {len(rows)} (budżet dziś: {budget_left():.2f} USD)')
        if dry_run:
            for row in rows:
                self.stdout.write(f'  #{row.pk} {row.status} ocena {row.screen_score} · {row.post.published_at:%d.%m %H:%M} · {row.post.text[:70]!r}')
            return
        figures = figures_by_account({row.post.account_id for row in rows})
        done = {}
        for row in rows:
            if budget_left() < BUDGET_RESERVE_USD:
                self.stdout.write('Stop: dzienny budżet wyczerpany.')
                break
            diagnose(row, figures.get(row.post.account_id))
            done[row.status] = done.get(row.status, 0) + 1
            self.stdout.write(f'  #{row.pk} → {row.status}' + (f' ({row.error[:60]})' if row.error else ''))
        self.stdout.write(f'Gotowe: {done}')
