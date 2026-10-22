"""Strategie wyboru zakładów. Każda dostaje tylko przeszłość (bez podglądania przyszłości).

Wspólna reguła: między dowolnymi dwoma zakładami jednej strategii najwyżej 2 wspólne liczby.
Zakład to posortowana krotka 6 różnych liczb 1-49.
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Callable, Iterable

LICZBY = range(1, 50)
MAX_WSPOLNYCH = 2
OKNO = 50          # ostatnie N losowań dla strategii `gorace` i `zimne`
# Z ilu najczęstszych / najrzadszych liczb losujemy zestawy. Przy 24 liczbach 33 zakłady z limitem
# 2 wspólnych dają się dobrać tylko z trudem (wolno), przy 27 - od razu.
PULA_GORZIM = 27


def maska(zaklad: Iterable[int]) -> int:
    m = 0
    for x in zaklad:
        m |= 1 << x
    return m


def poprawny(zaklad) -> bool:
    return len(zaklad) == 6 and len(set(zaklad)) == 6 and all(1 <= x <= 49 for x in zaklad)


def wspolne(a, b) -> int:
    return (maska(a) & maska(b)).bit_count()


def _dobierz(n: int, losuj_zestaw: Callable[[], tuple[int, ...]], dozwolony: Callable[[int, tuple], bool],
             proby: int = 20000) -> list[tuple[int, ...]]:
    """Zachłannie zbiera n zakładów spełniających limit nakładania i warunki strategii."""
    for _ in range(50):
        wybrane: list[tuple[int, ...]] = []
        maski: list[int] = []
        for _ in range(proby):
            z = losuj_zestaw()
            m = maska(z)
            if not dozwolony(m, z):
                continue
            if all((m & x).bit_count() <= MAX_WSPOLNYCH for x in maski):
                wybrane.append(z)
                maski.append(m)
                if len(wybrane) == n:
                    return wybrane
    raise RuntimeError("nie udało się dobrać zakładów z limitem nakładania")


def _z_puli(pula: list[int], rng: random.Random, wagi: list[float] | None = None):
    if wagi is None:
        return lambda: tuple(sorted(rng.sample(pula, 6)))

    def losuj():
        wybrane: set[int] = set()
        while len(wybrane) < 6:
            wybrane.add(rng.choices(pula, weights=wagi)[0])
        return tuple(sorted(wybrane))
    return losuj


# ---------- strategie ----------

def los(historia, n, rng, dawne_szostki=frozenset()):
    return _dobierz(n, _z_puli(list(LICZBY), rng), lambda m, z: True)


def historia_bez_szostek(historia, n, rng, dawne_szostki=frozenset()):
    """Pomysł właściciela: losowe zestawy, ale nigdy taki, który już kiedyś padł."""
    return _dobierz(n, _z_puli(list(LICZBY), rng), lambda m, z: m not in dawne_szostki)


def _czestosci(historia, rng) -> list[int]:
    licz = Counter(x for los_ in historia[-OKNO:] for x in los_)
    # remisy łamane losowo, żeby nie faworyzować małych liczb
    return sorted(LICZBY, key=lambda x: (-licz[x], rng.random()))


def gorace(historia, n, rng, dawne_szostki=frozenset()):
    pula = _czestosci(historia, rng)[:PULA_GORZIM]
    return _dobierz(n, _z_puli(pula, rng), lambda m, z: True)


def zimne(historia, n, rng, dawne_szostki=frozenset()):
    pula = _czestosci(historia, rng)[-PULA_GORZIM:]
    return _dobierz(n, _z_puli(pula, rng), lambda m, z: True)


# Liczby chętnie wybierane przez graczy (daty: do 31, miesiące: do 12; „szczęśliwe” 3, 7, 9, 11, 13) - ZRODLA.md.
_POPULARNE = {3, 7, 9, 11, 13}


def _waga_rzadkie(x: int) -> float:
    if x >= 32:
        return 3.0
    if x <= 12 or x in _POPULARNE:
        return 0.5
    return 1.0


def wzorek(z: tuple[int, ...]) -> bool:
    """Układy, które gracze zakreślają często: ciągi, stały odstęp, linia na kuponie 7x7, ta sama końcówka."""
    if any(b - a == 1 for a, b in zip(z, z[1:])):
        return True
    roznice = {b - a for a, b in zip(z, z[1:])}
    if len(roznice) == 1:
        return True
    wiersze = Counter((x - 1) // 7 for x in z)
    kolumny = Counter((x - 1) % 7 for x in z)
    if max(wiersze.values()) >= 3 or max(kolumny.values()) >= 3:
        return True
    if max(Counter(x % 10 for x in z).values()) >= 3:
        return True
    return False


def rzadko_grane(historia, n, rng, dawne_szostki=frozenset()):
    """Nie zwiększa szansy trafienia; zmniejsza ryzyko dzielenia nagrody z innymi graczami."""
    pula = list(LICZBY)
    wagi = [_waga_rzadkie(x) for x in pula]

    def dozwolony(m, z):
        return sum(1 for x in z if x >= 32) >= 3 and not wzorek(z) and m not in dawne_szostki
    return _dobierz(n, _z_puli(pula, rng, wagi), dozwolony)


STRATEGIE = {
    "historia": historia_bez_szostek,
    "gorace": gorace,
    "zimne": zimne,
    "rzadko_grane": rzadko_grane,
    "los": los,
}
