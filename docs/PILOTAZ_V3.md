# Pilotaż v3: pary „Wcześniej i teraz” i ciąg przyczyn (krok po kroku)

Cel: przed włączeniem `POSITION_PAIRS_ENABLED` i `CAUSAL_CHAIN_ENABLED` sprawdzić na danych produkcji, czy kandydaci i łańcuchy
są trafne (recenzja Fable, sekcja 5). Pilotaż niczego nie publikuje: flagi zostają wyłączone, arkusze są wewnętrzne.

## Kto
- Uruchamia: właściciel (komendy na serwerze, poniżej).
- Przegląda: redaktor dyżurny z uprawnieniem `news.can_decide_positionpair` / `news.can_decide_causalchain`, z listą kontrolną
  (oba źródła przeczytane w całości; ta sama sprawa i projekt; ironia, warunek, cudzy cytat; przedmiot głosowania; zmiana faktów
  między A i B; dla łańcucha: każdy fakt ma źródło, krok spin nie wskazuje osoby).
- Decyduje o włączeniu flagi: właściciel, po raporcie i odpowiedziach prawnika (pytania 1-5 i 11).

## Koszt (wywołania darmowych modeli)
- `pilotaz par` bez `--generuj`: 0 nowych wywołań (kandydaci z istniejącej pętli „Zmiana zdania”).
- `pilotaz par --generuj --temat ...`: do 6 wywołań na osobę i temat, łącznie limit `--max-wywolan` (domyślnie 60).
- `pilotaz lancuch --generuj --dni 20`: 4 wywołania na przekaz (1 generowanie + 3 role przeglądu), 2 obozy x 20 dni = do 160
  (limit `--max-wywolan`). Darmowe modele z okna agentów; diagnozy mają pierwszeństwo (tryb Dyrygenta).

## Krok po kroku (serwer)
```
ssh ubuntu@148.113.242.109
cd /srv/spin-clinic
alias dj='docker compose --env-file .env.production -f deploy/docker-compose.production.yml exec backend python manage.py'
dj migrate                                        # 0161-0166, flagi zostają wyłączone
dj pilotaz par --n 50 --dry-run                   # próba: sam arkusz z istniejących kandydatów
dj pilotaz par --n 50                             # kandydaci z pętli (bez modeli), równy podział obozów
dj pilotaz par --n 50 --generuj --temat "podatek od nieruchomości" --temat "CPK"   # opcjonalnie generator
dj pilotaz lancuch --dni 20 --generuj             # łańcuchy z 20 dni archiwum (do 160 wywołań)
```
Arkusze: `backend/tmp/pilotaz/<data>/pilotaz-par-*.csv|md`, `pilotaz-lancuch-*.csv` (skopiuj z kontenera `docker compose cp`).

## Przegląd
W CSV (separator `;`) uzupełnij dla każdego wiersza: `decyzja` (tak/nie), `powod` (`ok`, `inna_sprawa`, `kontekst`, `cytat`,
`glos`, `nazwisko`, `fakt_bez_zrodla`, `jezyk`, `inne`), `czas_s` (sekundy przeglądu). Pary: co najmniej 50 wierszy;
łańcuchy: co najmniej 20 (dni x obozy).

## Raport i próg
```
dj pilotaz raport --plik /app/tmp/pilotaz/<data>/pilotaz-par-<...>.csv --rodzaj par
dj pilotaz raport --plik /app/tmp/pilotaz/<data>/pilotaz-lancuch-<...>.csv --rodzaj lancuch
```
- Pary: przyjęte, gdy odrzucenia z powodu `inna_sprawa` albo `kontekst` < 10% przeglądniętych i przeglądniętych >= 50.
- Łańcuchy: przyjęte, gdy odrzucenia merytoryczne (wszystkie poza `ok` i `jezyk`) < 20% i przeglądniętych >= 20.
- Symetria: raport pokazuje odsetek odrzuceń w każdym obozie i bilans (udział kont i diagnoz); różnica odsetków > 15 pkt proc.
  = przegląd metody przed włączeniem (recenzja Fable, R5).
Raport MD obok CSV (`*.raport.md`) dołącz do dziennika decyzji.

## Kiedy włączyć flagę
Wszystkie warunki: raport przyjęty; poprawki recenzji Fable wdrożone (są w gałęzi); odpowiedzi prawnika; tekst noty i klauzuli
art. 14 po przeglądzie prawnika; dyżur i SLA zgłoszeń zapisane; runbook `RUNBOOK_KILL_SWITCH.md` przećwiczony.
Włączenie: `dj przelacznik ustaw POSITION_PAIRS_ENABLED on --kto <login> --uwaga "pilotaż przyjęty <data>"` (bez restartu).
Zatwierdzanie par z pilotażu: `dj pary_stanowisk zatwierdz <id> --kto <login> --kontekst "..." [--potwierdzam-przedmiot]`
(cztery oczy: inna osoba niż dodająca kandydata).

## Powody w wyniku generatora (od 13.10, po pierwszym pilotażu)
Pierwszy przebieg na produkcji (12 wywołań, 3 tematy) dał 0 par i puste `reasons`: odpowiedzi „to samo stanowisko”,
„nie na temat” albo niska pewność, a także odpowiedzi nieprawidłowe (w logu `inception_invalid_json`; wtedy pytanie szło
do zapasowego modelu Konsylium) były pomijane bez śladu. Teraz każde pytanie bez pary ma wpis w `log.from_topic.reasons`,
a podsumowanie w `reasons_summary`:
- `brak_pary` - model ocenił „to samo stanowisko” albo „nie na temat”, albo pewność < 75 (`detail`: relacja i pewność);
- `invalid_json` - odpowiedź nieczytelna także po ponownej próbie (krótsze pytanie u innego dostawcy z puli darmowej);
- `odrzucone_walidatorem` - model wskazał zmianę, ale walidator pary odrzucił (`code`, `detail`: np. cytat spoza materiału);
- `brak_materialu` - osoba albo temat nie mają pary materiałów z odstępem >= 14 dni;
- `limit` - wyczerpany limit wywołań albo brak wolnego modelu (`detail`: „model niedostępny: ...”).
Z `--verbose` przy powodzie jest `raw`: skrót surowej odpowiedzi (200 znaków, bez adresów e-mail i telefonów).

Budżet: `--na-osobe 2` (domyślnie) - w pierwszym przebiegu najwyżej 2 wywołania na osobę i temat, osoby na zmianę
z każdego obozu (kolejność losowa z ziarnem dnia i tematu, następnego dnia inne osoby); drugi przebieg tylko, gdy zostanie
budżet. Każda nieczytelna odpowiedź zużywa 2 wywołania (próba i ponowna próba).

Ponowne uruchomienie (po wdrożeniu poprawek):
```
dj pilotaz par --n 50 --generuj --max-wywolan 40 --na-osobe 2 --verbose --temat paliw --temat sankcje --temat bezpieczeństwo
```
Czytaj `reasons_summary`: przewaga `brak_pary` = modele nie widzą zmian w tych tematach (zmień tematy albo osoby);
przewaga `invalid_json` = problem dostawcy (sprawdź `inception_invalid_json` w logu i `python manage.py przelacznik lista`);
`odrzucone_walidatorem` = modele cytują niedosłownie (poprawa promptu); `brak_materialu` = za mało danych w temacie.
