from time import sleep
from uuid import uuid4

from django.core.cache import caches
from django.core.management.base import BaseCommand, CommandError

from ...models import Zrodlo
from ...zrodla.rcb import ArchiwumRCB


class Command(BaseCommand):
    help = "Pobiera archiwum RCB z zapisanym postępem i odstępem co najmniej 5 sekund."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, help="Maksymalna liczba obsłużonych odpowiedzi w tym uruchomieniu.")

    def handle(self, *args, limit=None, **options):
        if limit is not None and limit < 1:
            raise CommandError("--limit musi być dodatni.")
        licznik = 0
        # Odstęp obejmuje również granicę dwóch uruchomień i ostatnie pobranie harmonogramu.
        sleep(5)
        while limit is None or licznik < limit:
            zrodlo = Zrodlo.objects.select_related("zrodlo_dostepu").filter(slug="rcb").first()
            if zrodlo is None or zrodlo.tryb == Zrodlo.Tryb.WYLACZONY or zrodlo.blokada_dostepu:
                raise CommandError("RCB jest wyłączone, wstrzymane lub brakuje źródła.")
            archiwum = zrodlo.stan_adaptera.get("archiwum", {})
            # archiwum zakończone starszą wersją parsera nie jest „pobrane”: ArchiwumRCB zaczyna je od nowa (R38c, P2)
            if archiwum.get("zakonczone") and archiwum.get("wersja_parsera") == ArchiwumRCB.wersja_parsera:
                self.stdout.write("Archiwum RCB pobrane.")
                return
            cache = caches["teraz"]
            klucz = f"zbieranie:zrodlo:{zrodlo.pk}"
            znacznik = uuid4().hex
            if not cache.add(klucz, znacznik, timeout=50):
                sleep(5)
                continue
            try:
                bledy_kolejki = zrodlo.stan_adaptera.get("bledy_kolejki", 0)
                pobranie = ArchiwumRCB(zrodlo).zbierz()
                zrodlo.refresh_from_db()
                pominieta_karta = zrodlo.stan_adaptera.get("bledy_kolejki", 0) > bledy_kolejki
                if pobranie and zrodlo.ostatni_blad and (not pominieta_karta or pobranie.status_http == 429):
                    raise CommandError(zrodlo.ostatni_blad)
                if pobranie:
                    licznik += 1
            finally:
                if cache.get(klucz) == znacznik:
                    cache.delete(klucz)
            if limit is None or licznik < limit:
                sleep(5)
        self.stdout.write(f"Zapisano postęp archiwum RCB. Odpowiedzi w tym uruchomieniu: {licznik}.")
