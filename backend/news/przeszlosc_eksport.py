"""Wspólny eksport przeszłość.today (P1-5): CSV bez cichego obcinania, kolumny dla dziennikarza i przypis do cytowania.

Zasady: każdy wiersz ma źródło, datę pobrania, pewność powiązania i identyfikator; gdy czegoś nie dało się wyeksportować
(limit techniczny), jest jawny wiersz „pominięto N”. Komórki zaczynające się od =, +, - lub @ dostają apostrof (ochrona przed
formułami w arkuszu). Wynik po samej nazwie nigdy nie wchodzi do eksportu bez etykiety pewności.
"""
import csv
import io

from django.utils import timezone

EXPORT_CAP = 20000   # twardy limit techniczny na kategorię; powyżej - wiersz „pominięto N”
COLUMNS = ['data', 'rodzaj', 'tresc', 'spin', 'link', 'zrodlo', 'data_pobrania', 'pewnosc_powiazania', 'identyfikator']
SITE = 'https://przeszlosc.today'


def safe(value):
    text = '' if value is None else str(value)
    return "'" + text if text[:1] in ('=', '+', '-', '@', '\t', '\r') else text


def row(date='', kind='', text='', spin='', link='', source='', certainty='', ident='', stamp=''):
    return [safe(date), safe(kind), safe(text), safe(spin), link or '', source, stamp, certainty, ident]


def omitted_row(count, what, stamp):
    return row(kind='pominięto', text=f'Pominięto {count} {what}: przekroczono techniczny limit eksportu ({EXPORT_CAP}). Pełna lista w źródle.',
               source='przeszłość.today', certainty='-', stamp=stamp)


def citation(title, kind, stamp, url=''):
    """Przypis gotowy do wklejenia: kto, co, skąd, kiedy pobrano."""
    return (f'przeszłość.today, {kind} „{title}”, dane z rejestrów publicznych (źródła i licencje przy każdym wierszu), '
            f'pobrano {stamp}' + (f', {url}' if url else '') + '.')


def csv_text(rows, footer, columns=COLUMNS):
    out = io.StringIO()
    out.write('﻿')
    w = csv.writer(out, delimiter=';')
    w.writerow(columns)
    for r in rows:
        w.writerow(r)
    w.writerow([])
    for line in footer:
        w.writerow([line])
    return out.getvalue()


def today():
    return timezone.localdate().isoformat()
