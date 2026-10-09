"""Agregaty pierwszego przyjęcia push przez dostawcę, bez danych odbiorców."""
from collections import defaultdict
from datetime import timedelta
import json
from math import ceil
from statistics import median

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from news.notification_models import NotificationPost


def summary(values):
    values = sorted(values)
    return {'liczba': len(values), 'mediana_s': round(median(values), 2) if values else None,
        'p95_s': round(values[ceil(len(values) * .95) - 1], 2) if values else None}


class Command(BaseCommand):
    help = 'Opóźnienie publikacja → pierwsze przyjęcie push: mediana, p95 i liczba, per źródło.'

    def add_arguments(self, parser):
        parser.add_argument('--dni', type=int, default=7)
        parser.add_argument('--json', action='store_true')

    @staticmethod
    def budget():
        try:
            from news.alerts_polling import budget_snapshot
            from news.political_polling import configuration
            config = configuration()
            return budget_snapshot(config) if config else None
        except Exception:
            return None

    def handle(self, *args, **options):
        if options['dni'] < 1:
            raise CommandError('--dni musi być dodatnie.')
        since = timezone.now() - timedelta(days=options['dni'])
        rows = NotificationPost.objects.filter(push_sent_at__gte=since, push_latency_seconds__isnull=False)
        sources = defaultdict(list)
        # PoliticalPost is the official X intake model. RSS/YouTube/Sejm have
        # separate stores and must not be misrepresented as connected alerts.
        for value in rows.values_list('push_latency_seconds', flat=True).iterator():
            sources['x'].append(value)
        pending = NotificationPost.objects.filter(notification__created_at__gte=since,
            push_sent_at__isnull=True).count()
        result = {'dni': options['dni'], 'jednostka': 'sekundy',
            'pomiar': 'pierwsze przyjęcie przez dostawcę push, jeden odbiorca i wpis',
            'razem': summary([v for values in sources.values() for v in values]),
            'zrodla': {source: summary(sources[source]) for source in ('x', 'youtube', 'rss', 'sejm')},
            'bez_potwierdzenia_push': pending,
            'niepodlaczone_do_alertow': ['youtube', 'rss', 'sejm']}
        result['koszt_x'] = self.budget()
        if options['json']:
            self.stdout.write(json.dumps(result, ensure_ascii=False))
            return
        self.stdout.write(f"Ostatnie {options['dni']} dni. Jednostka: sekundy. {result['pomiar']}.")
        for label, data in [('razem', result['razem']), *result['zrodla'].items()]:
            self.stdout.write(f"{label}: liczba={data['liczba']}, mediana={data['mediana_s']}, p95={data['p95_s']}")
        usage = result['koszt_x']
        if usage:
            self.stdout.write(f"Koszt X: {usage['spent_upper_usd']}/{usage['monthly_usd_limit']} USD w miesiącu, "
                f"żądania dziś {usage['daily_requests']}/{usage['daily_request_limit']}, tryb szybki: {usage['fast_mode']}, "
                f"zalecany odstęp: {usage['paced_interval_seconds']} s.")
        else:
            self.stdout.write('Koszt X: odpytywanie X nie jest skonfigurowane.')
        self.stdout.write(f'Bez potwierdzenia push: {pending}. YouTube, RSS i Sejm nie są podłączone do outboxu alertów osób.')
