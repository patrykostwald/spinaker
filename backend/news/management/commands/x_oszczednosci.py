"""Wyliczenie oszczędności na X i (z --zastosuj) ustawienie czytania według wartości konta.

python manage.py x_oszczednosci             - tylko raport z ostatnich 7 dni
python manage.py x_oszczednosci --zastosuj  - raport i nowe interwały kont"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Count, Q, Sum
from django.utils import timezone


class Command(BaseCommand):
    help = 'Koszty X z 7 dni: ile wpisów kupujemy, ile idzie do diagnozy i ile oszczędza czytanie według wartości konta.'

    def add_arguments(self, parser):
        parser.add_argument('--zastosuj', action='store_true')

    def handle(self, *args, **options):
        from news.political_models import PoliticalAccount, PoliticalPost, PoliticalRead
        from news.political_polling import POST_PRICE
        from news import x_value
        since = timezone.now() - timedelta(days=7)
        reads = PoliticalRead.objects.filter(started_at__gte=since)
        returned = reads.aggregate(n=Sum('returned_posts'))['n'] or 0
        requests = reads.count()
        empty = reads.filter(returned_posts=0).count()
        posts = PoliticalPost.objects.filter(fetched_at__gte=since)
        diagnosed = posts.filter(spin_diagnosis__isnull=False).count()
        cost = Decimal(returned) * POST_PRICE
        self.stdout.write(f'Ostatnie 7 dni: {requests} zapytań do X ({empty} pustych), {returned} kupionych wpisów = {cost:.2f} USD.')
        self.stdout.write(f'Do diagnozy trafiło {diagnosed} wpisów ({(100 * diagnosed / returned) if returned else 0:.1f}% kupionych).')
        rows = (PoliticalAccount.objects.filter(enabled=True)
                .annotate(n=Count('posts', filter=Q(posts__fetched_at__gte=since)),
                          d=Count('posts__spin_diagnosis', filter=Q(posts__fetched_at__gte=since))).order_by('-n'))
        dead = [r for r in rows if r.n and not r.d]
        self.stdout.write(f'Konta z wpisami, ale bez żadnej diagnozy: {len(dead)}, razem {sum(r.n for r in dead)} wpisów '
                          f'({Decimal(sum(r.n for r in dead)) * POST_PRICE:.2f} USD tygodniowo).')
        for r in dead[:10]:
            self.stdout.write(f'  @{r.handle}: {r.n} wpisów, 0 diagnoz')
        plan = x_value.plan()
        self.stdout.write('Plan czytania: ' + ', '.join(f'{m} min: {sum(1 for v, _ in plan.values() if v == m)} kont'
                                                         for m in (x_value.FAST, x_value.NORMAL, x_value.SLOW)))
        from news.models import ImportState
        state = ImportState.objects.filter(name='political-x-budget').first()
        budget = {k: v for k, v in ((state.cursor or {}) if state else {}).items() if k not in ('lease',)}
        self.stdout.write(f'Stan budżetu X: {budget}')
        if state and state.last_error:
            self.stdout.write(f'Ostatni błąd X: {state.last_error}')
        for read in PoliticalRead.objects.order_by('-started_at')[:5]:
            self.stdout.write(f'  odczyt {read.started_at:%d.%m %H:%M}: {read.status}, http {read.http_status}, wpisów {read.returned_posts}')
        if options['zastosuj']:
            self.stdout.write(f'Zastosowano: {x_value.apply()}')
        else:
            self.stdout.write('Bez zmian. Dodaj --zastosuj, żeby ustawić interwały.')
