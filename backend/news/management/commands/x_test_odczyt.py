"""Jeden odczyt X na żądanie, z pełnym wynikiem (właściciel 6.10: odczyty zawisały w stanie „zarezerwowany”).

python manage.py x_test_odczyt
Najpierw zwalnia zawieszone rezerwacje (oddaje dzienny limit), potem uruchamia jeden cykl odczytu tak samo jak zadanie
w tle i wypisuje wynik, czas oraz błąd (bez kluczy). Kosztuje najwyżej jedną stronę wpisów z X."""
import time
import traceback

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Zwalnia zawieszone rezerwacje X i wykonuje jeden odczyt z wypisanym wynikiem.'

    def handle(self, *args, **options):
        from news.models import ImportState
        from news.political_polling import political_poll_cycle, release_stale
        out = self.stdout.write
        out(f'Zwolnione zawieszone rezerwacje: {release_stale(minutes=3)}')
        state = ImportState.objects.filter(name='political-x-budget').first()
        out(f'Budżet po zwolnieniu: { {k: v for k, v in (state.cursor if state else {}).items() if k != "lease"} }')
        started = time.monotonic()
        try:
            result = political_poll_cycle()
            out(f'Wynik odczytu ({time.monotonic() - started:.1f} s): {result}')
        except BaseException as error:  # chcemy zobaczyć każdy błąd, także przerwanie
            out(f'Błąd po {time.monotonic() - started:.1f} s: {type(error).__name__}: {str(error)[:300]}')
            out(''.join(traceback.format_exc().splitlines(True)[-12:]))
        state = ImportState.objects.filter(name='political-x-budget').first()
        if state and state.last_error:
            out(f'Ostatni błąd X: {str(state.last_error)[:300]}')
