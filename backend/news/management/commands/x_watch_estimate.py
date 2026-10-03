"""Offline projection using stored posts; never calls X or reads credentials."""
from datetime import timedelta
from decimal import Decimal
import json

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from news.political_models import PoliticalAccount, PoliticalPost, PoliticalRead
from news.x_watch import monthly_cost
from news.political_polling import USER_PRICE


def estimate(now=None):
    now = now or timezone.now()
    since = now - timedelta(days=14)
    accounts = list(PoliticalAccount.objects.filter(enabled=True, confirmed_at__isnull=False,
        confirmed_by__is_active=True, confirmed_by__is_staff=True).select_related('confirmed_by'))
    accounts = [a for a in accounts if a.is_confirmed()]
    counts = dict(PoliticalPost.objects.filter(account_id__in=[a.pk for a in accounts],
        published_at__gte=since, published_at__lte=now).order_by().values('account_id').annotate(n=Count('pk'))
        .values_list('account_id', 'n'))
    posts = sum(counts.values())
    daily = Decimal(posts) / 14
    # Comparison convention shared with the report: one nonempty response per
    # post, hence one returned profile per post in the former poller.
    batched, old = monthly_cost(daily), monthly_cost(daily, daily)
    reads = PoliticalRead.objects.filter(started_at__gte=since, started_at__lte=now)
    return {'days': 14, 'accounts': len(accounts), 'stored_posts': posts,
        'posts_daily': str(daily), 'posts_per_account_daily': str(daily / len(accounts)) if accounts else '0',
        'batched_usd': str(batched), 'batched_pln': str(batched * 4),
        'former_usd': str(old), 'former_pln': str(old * 4),
        'former_assumption': 'one returned profile per post; several posts per response lower this cost',
        'profile_refresh_monthly_usd': str(Decimal(len(accounts)) * 30 / 7 * USER_PRICE),
        'recorded_requests': reads.count(), 'recorded_nonempty_pages': reads.filter(returned_posts__gt=0).count(),
        'coverage_note': 'Stored posts only; disabled polling, budgets and outages can undercount real activity.',
        'per_account': [{'handle': a.handle, 'posts': counts.get(a.pk, 0),
            'posts_daily': str(Decimal(counts.get(a.pk, 0)) / 14)} for a in accounts]}


class Command(BaseCommand):
    help = 'Estymacja kosztu X z lokalnych wpisów z ostatnich 14 dni; bez zapytań do X.'

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true')

    def handle(self, *args, **options):
        data = estimate()
        if options['json']:
            self.stdout.write(json.dumps(data, ensure_ascii=False, indent=2))
            return
        self.stdout.write(f"14 dni: {data['accounts']} kont, {data['stored_posts']} zapisanych wpisów; "
            f"{Decimal(data['posts_daily']):.2f} wpisów/dzień.")
        for mode, label in [('batched', 'Batched bez profili'), ('former', 'Poprzedni wariant z profilami')]:
            self.stdout.write(f"{label}: {Decimal(data[mode + '_usd']):.2f} USD / "
                f"{Decimal(data[mode + '_pln']):.2f} PLN miesięcznie (30 dni, USD/PLN=4).")
        self.stdout.write('Porównanie: 1 profil na wpis; kilka wpisów w odpowiedzi obniża dawny koszt. '
            'Odświeżanie profili co 7 dni liczone osobno: '
            f"{Decimal(data['profile_refresh_monthly_usd']):.2f} USD/miesiąc.")
        self.stdout.write('To aktywność widoczna w bazie. Przerwy, limity i wyłączony polling zaniżają wynik.')
