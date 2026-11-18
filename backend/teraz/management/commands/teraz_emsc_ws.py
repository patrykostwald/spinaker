from collections import deque
from time import monotonic, sleep

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, close_old_connections, transaction
from django.utils import timezone
from scraper.access_gate import AccessDenied

from ...models import Zrodlo
from ...transport import BladPobrania
from ...zbieranie import BladFormatu, TYTUL_WYZWANIA, WYZWANIE_BOTA
from ...zrodla.emsc import AdapterEMSC

MAKSYMALNY_ODSTEP = 300
ODSTEP_CZUWANIA = 60
LIMIT_WIADOMOSCI_NA_MINUTE = 120


class Command(BaseCommand):
    help = "Odbiera oficjalny strumień EMSC i zapisuje wstrząsy w Polsce i okolicach."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.przyjete = deque()
        self.odrzucone = 0

    def handle(self, *args, **options):
        try:
            from websockets.exceptions import InvalidStatus, WebSocketException
            from websockets.sync.client import connect
        except ImportError as exc:
            raise CommandError("EMSC wymaga biblioteki z teraz/requirements-emsc.txt.") from exc

        odstep = 3
        while True:
            adapter = None
            rozpoczecie = monotonic()
            try:
                adapter = AdapterEMSC(self._zrodlo())
                with adapter.polacz(connect) as polaczenie:
                    self._czytaj(adapter, polaczenie)
            except KeyboardInterrupt:
                return
            except InvalidStatus as exc:
                odpowiedz = exc.response
                tresc = bytes(odpowiedz.body or b"")[:65536]
                wyzwanie = (odpowiedz.status_code == 403 or odpowiedz.headers.get("cf-mitigated") == "challenge"
                            or WYZWANIE_BOTA.search(tresc) or TYTUL_WYZWANIA.search(tresc))
                blad = BladPobrania("Odmowa dostępu EMSC.", status_http=403 if wyzwanie else odpowiedz.status_code)
                self._zapisz_blad(adapter, blad)
                if wyzwanie:
                    raise CommandError("EMSC odmówił dostępu. Zatrzymano strumień.") from None
            except (AccessDenied, BladFormatu) as exc:
                self._zapisz_blad(adapter, exc)
                raise CommandError("EMSC: sprawdź kartę dostępu lub format strumienia w stanie źródła.") from None
            except BladPobrania as exc:
                self._zapisz_blad(adapter, exc)
                if exc.status_http == 403:
                    raise CommandError("EMSC zwrócił wyzwanie bota. Zatrzymano strumień.") from None
            except (OSError, WebSocketException) as exc:
                self._zapisz_blad(adapter, exc)
            except (ValidationError, DatabaseError) as exc:
                if adapter is not None:
                    self._zapisz_blad(adapter, exc)
                self.stderr.write(f"EMSC: przerwano zapis ({type(exc).__name__}).")
            if monotonic() - rozpoczecie >= ODSTEP_CZUWANIA:
                odstep = 3
            sleep(odstep)
            odstep = min(2 * odstep, MAKSYMALNY_ODSTEP)

    def _zapisz_blad(self, adapter, exc):
        try:
            adapter.zapisz_blad_strumienia(exc)
        except DatabaseError:
            close_old_connections()
            self.stderr.write("EMSC: nie udało się zapisać błędu w stanie źródła.")

    def _zrodlo(self):
        close_old_connections()
        zrodlo = Zrodlo.objects.select_related("zrodlo_dostepu").filter(slug="emsc", blokada_dostepu=False).exclude(
            tryb=Zrodlo.Tryb.WYLACZONY,
        ).first()
        if zrodlo is None:
            raise CommandError("EMSC jest wyłączony, wstrzymany lub brakuje źródła.")
        return zrodlo

    def _czytaj(self, adapter, polaczenie):
        try:
            self._odbieraj(adapter, polaczenie)
        finally:
            try:
                self._zapisz_odrzucone(adapter.zrodlo.pk)
            except DatabaseError:
                close_old_connections()

    def _odbieraj(self, adapter, polaczenie):
        nastepne_sprawdzenie = monotonic()
        while True:
            if monotonic() >= nastepne_sprawdzenie:
                zrodlo = self._zrodlo()
                if not adapter._dostepne(zrodlo):
                    raise AccessDenied("zmieniono_zrodlo")
                adapter.zrodlo = zrodlo
                adapter.karta_dostepu(zrodlo.adres)
                self._zapisz_odrzucone(zrodlo.pk)
                teraz = timezone.now()
                Zrodlo.objects.filter(pk=zrodlo.pk, blokada_dostepu=False).exclude(
                    tryb=Zrodlo.Tryb.WYLACZONY,
                ).update(ostatni_sukces_at=teraz, ostatni_blad="", kolejne_bledy=0)
                nastepne_sprawdzenie = monotonic() + ODSTEP_CZUWANIA
            try:
                wiadomosc = polaczenie.recv(timeout=ODSTEP_CZUWANIA)
            except TimeoutError:
                continue
            teraz = monotonic()
            while self.przyjete and self.przyjete[0] <= teraz - 60:
                self.przyjete.popleft()
            if len(self.przyjete) >= LIMIT_WIADOMOSCI_NA_MINUTE:
                self.odrzucone += 1
                continue
            self.przyjete.append(teraz)
            adapter.przyjmij(wiadomosc)

    def _zapisz_odrzucone(self, pk):
        if not self.odrzucone:
            return
        with transaction.atomic():
            zrodlo = Zrodlo.objects.select_for_update().get(pk=pk)
            stan = zrodlo.stan_adaptera
            stan["odrzucone_limit_wiadomosci"] = stan.get("odrzucone_limit_wiadomosci", 0) + self.odrzucone
            zrodlo.save(update_fields=["stan_adaptera"])
        self.odrzucone = 0
