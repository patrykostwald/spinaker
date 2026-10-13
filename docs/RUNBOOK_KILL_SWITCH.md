# Runbook: wyłącz w 5 minut (funkcje v3 i cisza wyborcza)

Dotyczy: ciąg przyczyn („Dr Spin wyjaśnia”), siła spinu dnia, „Wcześniej i teraz”, stary blok „Zmiana zdania”, lista głosowań,
graf powiązań. Przełączniki w bazie (`SiteFlag`) działają bez restartu, najpóźniej po 30 s (zapis czyści pamięć od razu).
Każda zmiana trafia do dziennika `SiteFlagChange` (kto, kiedy, z czego na co).

## Klucze
`CAUSAL_CHAIN_ENABLED`, `PRZEKAZ_SPIN_STRENGTH_ENABLED`, `POSITION_PAIRS_ENABLED`, `POSITION_CHANGES_LEGACY_ENABLED`,
`PRZESZLOSC_VOTES_LIST_ENABLED`, `PRZESZLOSC_NETWORK_ENABLED`, `ELECTION_SILENCE`.
Wiersz w bazie wygrywa z wartością z `.env.production`; usunięcie wiersza przywraca wartość z env.

## Wyłączenie funkcji (afera, błąd, żądanie prawnika)
1. Admin Django: „Przełączniki v3” → Dodaj (albo edytuj): klucz, wartość odznaczona, notatka (powód). Zapisz.
   Albo z serwera (bez restartu):
   ```
   ssh ubuntu@148.113.242.109
   cd /srv/spin-clinic && docker compose --env-file .env.production -f deploy/docker-compose.production.yml exec backend \
     python manage.py przelacznik ustaw POSITION_PAIRS_ENABLED off --kto <login> --uwaga "powód"
   ```
2. Sprawdź: `python manage.py przelacznik lista` (kolumna `teraz=False`) i odśwież stronę (pary mają `no-store`;
   `/api/clinic/` ma cache 60 s z kluczem zależnym od flag, nowy stan od razu).
3. Pojedynczy element zamiast całej funkcji: `pary_stanowisk wycofaj <id> --kto <login> --uwaga "publiczny powód"` albo
   `lancuch_przekazu odrzuc <id> --kto <login> --uwaga "publiczny powód"` (wpis w rejestrze korekt).
4. Zapisz w dzienniku decyzji: co, kto, dlaczego; oświadczenie z szablonu w ciągu 2 h (bez oceny osób).

## Cisza wyborcza
- Ustaw okno z wyprzedzeniem (kalendarz wyborów, także uzupełniających i referendów):
  `python manage.py przelacznik ustaw ELECTION_SILENCE on --od 2027-10-09T00:00:00+02:00 --do 2027-10-10T21:00:00+02:00 --kto <login>`
- Alternatywnie w env: `ELECTION_SILENCE_FROM` / `ELECTION_SILENCE_UNTIL` (ISO 8601) - wymaga restartu, więc preferuj bazę.
- W ciszy: łańcuchy i pary znikają z API, zatwierdzanie wstrzymane (API 423), powiadomienia o parach nie wychodzą,
  stary blok „Zmiana zdania” i linia social wyłączone, `/api/clinic/` bez cache.

## Przywrócenie
`python manage.py przelacznik usun <KLUCZ> --kto <login>` (wraca wartość z env) albo edycja w adminie. Przed ponownym
włączeniem funkcji: przegląd przyczyny i zapis w dzienniku.

## Kto
Właściciel decyduje o przełącznikach funkcji; dyżurny może wyłączyć w trybie pilnym i od razu informuje właściciela.
