# Kolejność źródeł po pilotażu głosowań Sejmu

Stan: 15 września 2026. To kolejka audytu, nie lista automatycznie
zatwierdzonych pobrań.

## Etap 1

1. Głosowania Sejmu — publiczne API, jeden wąski pilot `term10/votings`.

Przejście wymaga: pełnego audytu prób, braku naruszeń odstępu hosta, ręcznej
próbki poprawności i obsłużonej korekty rekordu. Sam upływ czasu nie wystarcza.

## Kandydaci do audytu po udanym pilocie

1. Senat RP
2. Kancelaria Prezesa Rady Ministrów
3. Ministerstwo Finansów
4. Ministerstwo Sprawiedliwości
5. Rzecznik Praw Obywatelskich
6. Narodowy Bank Polski

Kolejność jest oparta na wartości kontekstowej i przewidywalności danych,
nie jest deklaracją dostępności kanału.

## Reguła dowodowa

`robots.txt`, publiczna strona i brak widocznego zakazu są wyłącznie sygnałami
technicznymi. Nie tworzą samodzielnej podstawy automatycznego pobrania.
Przed kartą dostępu audyt musi zapisać pozytywny dowód dla konkretnego kanału
i endpointu: dokumentację publicznego API, licencję/warunki ponownego użycia,
wyraźnie udostępniony kanał RSS albo pisemną zgodę.

Każdy nowy kanał przechodzi własny mały pilot. Karta dla API nie uprawnia do
RSS, sitemap ani HTML tego samego podmiotu.
