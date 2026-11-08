"""Koszt Gemini w rozbiciu na zadania z ostatnich dni (z zapisanego zużycia). Wpisy sprzed 1.10.2026 nie zawierają
tokenów „myślenia”, więc realny koszt był wyższy — porównaj z kwotą w Google AI Studio."""
from collections import defaultdict
from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from news import clinic_ai
from news.clinic_models import ClinicInterview, CouncilCall, SpinDiagnosis


class Command(BaseCommand):
    help = 'Koszt Gemini w rozbiciu na zadania (sprawdzanie faktów, wywiad dnia, role Konsylium).'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7)

    def handle(self, days, **options):
        since = timezone.now() - timedelta(days=days)
        rows = defaultdict(lambda: defaultdict(float))
        for day, usage in SpinDiagnosis.objects.filter(diagnosed_at__gte=since).values_list('diagnosed_at__date', 'usage'):
            usage = usage or {}
            if 'gemini' in str(usage.get('check_model') or '').lower():
                row = rows[day]
                row['fakty'] += 1
                row['zapytania'] += int(usage.get('web_search_requests') or 0)
                row['fakty_usd'] += clinic_ai.cost_usd({**usage, 'model': 'gemini'})
        for day, usage in ClinicInterview.objects.filter(created_at__gte=since).values_list('created_at__date', 'usage'):
            usage = usage or {}
            for key in ('gemini', 'claude'):
                part = usage.get(key) or {}
                if 'gemini' in str(part.get('model') or '').lower():
                    rows[day]['wywiad_usd'] += clinic_ai.cost_usd({**part, 'model': 'gemini'})
        for day, outcome in CouncilCall.objects.filter(created_at__gte=since, provider='gemini').values_list('created_at__date', 'outcome'):
            rows[day]['konsylium'] += 1
        self.stdout.write('dzień        diagnozy z faktami  zapytania Google  fakty USD  wywiad USD  wywołania Konsylium')
        total = defaultdict(float)
        for day in sorted(rows):
            row = rows[day]
            for key, value in row.items():
                total[key] += value
            self.stdout.write(f"{day}  {int(row['fakty']):>18}  {int(row['zapytania']):>16}  {row['fakty_usd']:>9.2f}  "
                              f"{row['wywiad_usd']:>10.2f}  {int(row['konsylium']):>19}")
        self.stdout.write(f"RAZEM       {int(total['fakty']):>18}  {int(total['zapytania']):>16}  {total['fakty_usd']:>9.2f}  "
                          f"{total['wywiad_usd']:>10.2f}  {int(total['konsylium']):>19}")
        # Pełny licznik (od 1.10.2026): każde wywołanie Gemini w chwili odpowiedzi, także nieudane diagnozy.
        self.stdout.write('')
        self.stdout.write('PEŁNY LICZNIK (od wgrania 1.10): dzień, zadanie, wywołania, zapytania Google, tokeny myślenia, USD')
        today = timezone.localdate()
        overall = 0.0
        for offset in range(days, -1, -1):
            day = (today - timedelta(days=offset)).isoformat()
            for task in list(clinic_ai.GEMINI_THINKING):
                row = cache.get(clinic_ai.GEMINI_SPEND_KEY.format(day=day, task=task))
                if row:
                    overall += row['usd']
                    self.stdout.write(f"{day}  {task:<10}  {row['calls']:>5}  {row['searches']:>5}  {row['thinking']:>9}  {row['usd']:>7.2f}")
        self.stdout.write(f"RAZEM z pełnego licznika: {overall:.2f} USD (ok. {overall * 3.7:.2f} zł)")
