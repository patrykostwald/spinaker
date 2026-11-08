"""Dlaczego nie ma nowych diagnoz (właściciel 6.10). Tylko odczyt, bez sekretów - wynik można wkleić Claude.

python manage.py diagnozy_dzis
Pokazuje: ostatnią opublikowaną diagnozę, wpisy z dziś według statusu, najczęstsze błędy (rodzaj), kolejkę
oraz stan czytania X (dziś przeczytane, ostatnie odczyty i ostatni błąd X)."""
from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Dlaczego nie ma nowych diagnoz: statusy z dziś, błędy, kolejka i czytanie X (tylko odczyt).'

    def handle(self, *args, **options):
        from news.clinic_models import SpinDiagnosis
        from news.council_health import error_kind
        from news.models import ImportState
        from news.political_models import PoliticalRead
        out = self.stdout.write
        now = timezone.now()
        day = now - timedelta(hours=24)
        last = SpinDiagnosis.objects.filter(diagnosed_at__isnull=False).exclude(status='failed').order_by('-diagnosed_at').first()
        out(f'Ostatnia udana diagnoza: {last.diagnosed_at:%d.%m %H:%M} (status {last.status})' if last else 'Brak udanych diagnoz.')
        recent = SpinDiagnosis.objects.filter(created_at__gte=day)
        out('Wpisy z 24 h według statusu: ' + ', '.join(f'{k}: {v}' for k, v in Counter(recent.values_list('status', flat=True)).most_common()))
        failed = SpinDiagnosis.objects.filter(status='failed', created_at__gte=day).values_list('error', flat=True)
        kinds = Counter(error_kind(e) for e in failed)
        out('Błędy diagnoz z 24 h (rodzaj): ' + (', '.join(f'{k}: {v}' for k, v in kinds.most_common()) or 'brak'))
        for e in list(dict.fromkeys(str(x)[:160] for x in failed))[:5]:
            out(f'  przykład: {e}')
        queued = SpinDiagnosis.objects.filter(status__in=('queued', 'flagged')).count()
        out(f'W kolejce do diagnozy: {queued}')
        from news.political_models import PoliticalPost
        from news import clinic
        newest = PoliticalPost.objects.order_by('-published_at').values_list('published_at', flat=True).first()
        fresh = PoliticalPost.objects.filter(published_at__gte=day).count()
        out(f'Najnowszy wpis polityka w bazie: {newest:%d.%m %H:%M}' if newest else 'Brak wpisów w bazie.')
        out(f'Wpisy z ostatnich 24 h (tylko takie idą do diagnozy): {fresh}')
        fresh_queue = SpinDiagnosis.objects.filter(status__in=('queued', 'flagged'), post__published_at__gte=day).count()
        out(f'W kolejce ze świeżych wpisów: {fresh_queue}')
        try:
            out(f'Budżet: zostało {clinic.budget_left():.2f} USD, rezerwa {clinic.diagnosis_reserve():.2f}; '
                f'diagnoz dziś {clinic.diagnoses_today()}, poważnych błędów dziś {clinic.failures_today()}')
        except Exception as error:  # odczyt pomocniczy, nie może zatrzymać raportu
            out(f'Budżet: nie udało się odczytać ({type(error).__name__})')
        reads = PoliticalRead.objects.filter(started_at__gte=day)
        out(f'X: odczyty z 24 h: {reads.count()}, wpisów: {sum(n or 0 for n in reads.values_list("returned_posts", flat=True))}')
        for r in PoliticalRead.objects.order_by('-started_at')[:5]:
            out(f'  odczyt {r.started_at:%d.%m %H:%M}: {r.status}, http {r.http_status}, wpisów {r.returned_posts}')
        state = ImportState.objects.filter(name='political-x-budget').first()
        if state and state.last_error:
            out(f'Ostatni błąd X: {str(state.last_error)[:300]}')
