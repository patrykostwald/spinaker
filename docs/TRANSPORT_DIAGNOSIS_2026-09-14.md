# Diagnoza transportu archiwizacji — 14 września 2026

## Zakres

Przegląd lokalnego kodu `backend/scraper/utils.py` i
`backend/scraper/archive.py`. Nie wykonywano pobrań zewnętrznych ani nie
zmieniano konfiguracji źródeł.

## Znaleziona przyczyna

`fetch_feed()` najpierw poprawnie rozwiązuje nazwę domeny i odrzuca adresy
niepubliczne, ale następnie tworzy połączenie bezpośrednio do pierwszego
zwróconego adresu IP:

```python
address = addresses[0][4][0]
pool = urllib3.HTTPSConnectionPool(address, ..., server_hostname=hostname)
```

To jest bezpieczne wobec klasycznego DNS rebinding, lecz omija zwykłą ścieżkę
połączenia po nazwie hosta. Niektóre CDN-y, load balancery i lokalne proxy
sieciowe akceptują żądanie wyłącznie po normalnym połączeniu z domeną. Efektem
mogą być `NewConnectionError` oraz masowe ponowienia, mimo że URL i adapter
źródła są poprawne. `archive.process()` uznaje je za przejściowe
`requests.ConnectionError`, więc zadania wracają do retry aż do limitu prób.

Nie ma dowodu, że każde takie niepowodzenie ma tę samą przyczynę; trzeba
potwierdzić ją pojedynczym, mierzalnym testem po poprawce.

## Najmniejsza bezpieczna poprawka

1. Zachować przed każdym żądaniem walidację URL i DNS: nazwa hosta musi
   rozwiązać się wyłącznie do publicznych adresów.
2. Po walidacji łączyć się **po nazwie hosta**, nie po wybranym IP. Użyć
   `urllib3.PoolManager` albo `requests.Session` z URL-em domeny.
3. Nie włączać automatycznych redirectów. Dla każdego `Location` powtórzyć
   walidację URL, DNS i limit czterech redirectów, a dopiero potem wykonać
   następne żądanie.
4. Zachować obecne limity: 5 s na połączenie, 30 s odczytu, 5 MB po
   dekompresji, `retries=False`, jawny User-Agent.
5. Zmienić klasyfikację błędu transportu: po trzech kolejnych
   `NewConnectionError` dla hosta otworzyć istniejący circuit breaker i
   odłożyć źródło do diagnozy; nie pozwolić mu zużywać całego globalnego
   cyklu retry.

To przywraca kompatybilność z hostingiem i firmowymi proxy. Oznacza
kontrolowane okno DNS TOCTOU między walidacją a połączeniem, dlatego ten
wariant jest właściwy wyłącznie dla allowlisty zweryfikowanych źródeł i musi
pozostać połączony z walidacją każdego przekierowania. Dla dowolnych URL-i od
użytkownika należy utrzymać silniejszy, przypięty do IP transport lub osobny
izolowany fetcher.

## Testy regresyjne przed uruchomieniem

- prywatny adres DNS nadal kończy się błędem przed próbą połączenia;
- redirect do prywatnego adresu nadal kończy się błędem;
- publiczny URL tworzy pool dla `source.example`, nie dla `8.8.8.8`;
- `Host` nie jest ręcznie nadpisywany na adres IP;
- trzy awarie `NewConnectionError` otwierają circuit breaker hosta;
- jeden udany fetch zeruje licznik awarii;
- test archiwum potwierdza, że wadliwe źródło zostaje odroczone, a zdrowe
  źródło nadal tworzy box.

## Kolejność wdrożenia

1. Dodać testy do `backend/scraper/tests.py` i
   `backend/scraper/test_archive_metrics.py`.
2. Zmienić wyłącznie `fetch_feed()` oraz ewentualnie mapowanie
   `NewConnectionError` w `archive.py`.
3. Uruchomić testy transportu i archiwum.
4. Wykonać jeden test na jednym zatwierdzonym źródle, porównać liczbę
   utworzonych boxów i retry.
5. Dopiero przy dodatnim przyroście zwiększać równoległość źródeł.

## Czego poprawka nie robi

Nie dodaje źródeł, nie pobiera pełnych tekstów, nie zmienia podstaw dostępu,
nie omija `robots.txt` ani nie aktywuje procesu masowego. Jej celem jest
wyłącznie naprawa transportu zatwierdzonych źródeł, tak aby dane były
pozyskiwane mierzalnie i bez bezproduktywnych retry.
