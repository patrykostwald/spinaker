# Pilot harvesterow Tier 1

Stan propozycji: 14 wrzesnia 2026. Dokument opisuje lokalny pilot, ale nie uruchamia go automatycznie.

## Zakres

- 5-10 zrodel Tier 1 wybranych recznie przez wlasciciela.
- Tylko lokalna baza SQLite (`backend/db.sqlite3`), bez zapisu do Supabase.
- Preferowane zrodla z potwierdzonym RSS lub mapa witryny; nie traktowac samego homepage jako dowodu archiwum.
- Zadania obejmuja metadane i link do oryginalu. Pelny tekst pozostaje wylaczony (`ARCHIVE_STORE_FULL_TEXT=false`).
- Nie uruchamiac X, NewsAPI, GDELT ani importu calego katalogu w tym pilocie.

## Twarde limity

- Maksymalnie 2 workery archiwum: `ARCHIVE_WORKERS=2`.
- Maksymalnie 20 zadan na zrodlo w jednej sesji: `--limit 20`.
- Jeden proces schedulera/importera; nie uruchamiac rownolegle `run_local_jobs`.
- Bramkowanie domeny pozostaje aktywne: co najmniej 3 sekundy oraz `Crawl-delay`/`Request-rate` z robots.txt.
- Timeout polaczenia: 5 sekund; odczytu: 30 sekund dla pobierania archiwum.
- Odpowiedz wieksza niz 5 MB jest odrzucana.
- Po 3 przejsciowych bledach hosta otwiera sie circuit breaker do maksymalnie 15 minut.
- 429 i 5xx zachowuja zadanie w kolejce z backoffem; `Retry-After` jest dolna granica opoznienia.
- Po 10% bledow przejsciowych lub 5 bledach tego samego hosta zatrzymac pilot i przejrzec robots/limity wydawcy.

## Start po zatwierdzeniu listy zrodel

W katalogu repozytorium, po ustawieniu lokalnego interpretera:

```powershell
$env:USE_SQLITE='true'
$env:ARCHIVE_STORE_FULL_TEXT='false'
$env:ARCHIVE_WORKERS='2'
Set-Location backend
.venv\Scripts\python.exe manage.py import_archives --source-id <ID_ZRODLA> --limit 20
```

Polecenie nalezy wykonac osobno dla kazdego z 5-10 zatwierdzonych ID. Nie podstawia kodu produkcyjnego Supabase i nie wysyla wiadomosci. Przed startem sprawdzic, ze zrodla maja `is_active=true`, `scrape_enabled=true`, `catalog_stage=configured` i jawnie potwierdzony kanal.

Pilot zatrzymuje sie przez `Ctrl+C`. Biezace zadanie moze dokonczyc zapis; zadania pozostale w kolejce pozostaja do wznowienia. Ponowne uruchomienie tego samego polecenia jest idempotentne po URL i nie powinno tworzyc drugiego `Article` ani `ArchiveJob`.

## Rejestr pomiaru

Dla kazdej sesji zapisac lokalnie, bez sekretow:

- czas startu i zakonczenia oraz liczbe przetworzonych zadan;
- rekordy/min oraz czas osobno dla kazdej domeny;
- HTTP 2xx/3xx/429/5xx, timeouty, bledy parsera, robots disallowed i circuit breaker;
- liczbe nowych artykulow, ponownych odczytow i duplikatow po URL/canonical URL;
- liczbe rekordow bez daty, z data niepewna oraz z data pochodzaca z RSS/JSON-LD;
- rozmiar odpowiedzi i rozmiar bazy przed/po;
- RAM/CPU procesu oraz transfer sieciowy z lokalnego monitora systemu;
- czy zatrzymanie i wznowienie zachowaly kolejke, lease, `attempts` i `available_at`.

Nie zapisywac tresci chronionej ani URL-i z sekretami do logow. Raport powinien zawierac identyfikator zrodla, typ bledu i czas, nie token ani pelna odpowiedz wydawcy.

## Kryteria zwiekszenia skali

Nie zwiekszac liczby zrodel ani workerow, dopoki wszystkie sa spelnione w dwoch osobnych sesjach:

- brak niekontrolowanego wzrostu bledow 429/5xx i brak naruszen robots;
- duplikaty po ponowieniu sa rowne zero, a canonical URL jest zgodny z dowodem strony;
- brak utraty kursora po kontrolowanym zatrzymaniu;
- mediana czasu domeny i rekordow/min sa stabilne;
- obciazenie komputera pozostaje ponizej 70% CPU i 70% RAM, z zapasem na portal;
- kazdy problem ma decyzje: ponowic, wylaczyc zrodlo albo uzyskac dodatkowe potwierdzenie dostepu.

Zwiekszanie skali wymaga osobnego checkpointu i zgody wlasciciela przed uruchomieniem kolejnej sesji.
