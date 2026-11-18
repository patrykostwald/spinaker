import sys
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, call

import pytest
from django.core.exceptions import ValidationError
from django.db import DatabaseError

from teraz.management.commands import teraz_emsc_ws as emsc_ws
from teraz.models import Zrodlo


def test_emsc_wersja_biblioteki_i_backoff_bledow_zapisu(monkeypatch):
    wymagania = Path(emsc_ws.__file__).parents[2] / "requirements-emsc.txt"
    assert wymagania.read_text().strip() == "websockets==15.0.1"
    for nazwa in ("websockets", "websockets.sync", "websockets.exceptions", "websockets.sync.client"):
        monkeypatch.setitem(sys.modules, nazwa, ModuleType(nazwa))
    wyjatki = sys.modules["websockets.exceptions"]
    wyjatki.InvalidStatus = type("InvalidStatus", (Exception,), {})
    wyjatki.WebSocketException = type("WebSocketException", (Exception,), {})
    sys.modules["websockets.sync.client"].connect = Mock()

    komenda = emsc_ws.Command()
    adapter = Mock()
    adapter.polacz.side_effect = lambda connect: nullcontext(Mock())
    adapter.zapisz_blad_strumienia.side_effect = [None, DatabaseError()]
    zrodlo = object()
    monkeypatch.setattr(emsc_ws, "AdapterEMSC", Mock(return_value=adapter))
    monkeypatch.setattr(komenda, "_zrodlo", Mock(return_value=zrodlo))
    czytaj = Mock(side_effect=[ValidationError("Nieważny komunikat."), DatabaseError(), KeyboardInterrupt()])
    monkeypatch.setattr(komenda, "_czytaj", czytaj)
    monkeypatch.setattr(emsc_ws, "monotonic", lambda: 0)
    zamknij = Mock()
    monkeypatch.setattr(emsc_ws, "close_old_connections", zamknij)
    sleep = Mock()
    monkeypatch.setattr(emsc_ws, "sleep", sleep)
    komenda.handle()
    assert sleep.call_args_list == [call(3), call(6)]
    assert adapter.zapisz_blad_strumienia.call_count == 2 and czytaj.call_count == 3
    zamknij.assert_called_once()


@pytest.mark.django_db
def test_emsc_limit_w_ruchomej_minucie_i_licznik_odrzutow(monkeypatch):
    zrodlo = Zrodlo.objects.get(slug="emsc")
    komenda = emsc_ws.Command()
    komenda._zrodlo = Mock(return_value=zrodlo)
    adapter = Mock(zrodlo=zrodlo)
    zegar = 0

    def wiadomosci(timeout):
        nonlocal zegar
        for zegar, numer in [(0, 1), (30, 2), (59, 3), (60, 4), (61, 5), (90, 6)]:
            yield numer
        raise KeyboardInterrupt

    iterator = wiadomosci(60)
    polaczenie = Mock()
    polaczenie.recv.side_effect = lambda timeout: next(iterator)
    monkeypatch.setattr(emsc_ws, "monotonic", lambda: zegar)
    monkeypatch.setattr(emsc_ws, "LIMIT_WIADOMOSCI_NA_MINUTE", 2)
    with pytest.raises(KeyboardInterrupt):
        komenda._czytaj(adapter, polaczenie)
    zrodlo.refresh_from_db()
    assert adapter.przyjmij.call_args_list == [call(1), call(2), call(4), call(6)]
    assert zrodlo.stan_adaptera["odrzucone_limit_wiadomosci"] == 2
