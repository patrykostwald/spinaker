# Pętla poprawek: Śledczy i Budowniczy (przeszłość.today)

Cel: doprowadzić przeszłość.today do poziomu najlepszego narzędzia OSINT dla dziennikarzy. Rola Śledczego: docs/SLEDCZY_ROLA.md.

## Przebieg rundy
1. **Śledczy (recenzja).** Wykonuje 10 scenariuszy na działającej stronie (https://przeszlosc.today, tylko odczyt), ocenia 10 obszarów w skali 0-10, zapisuje raport z backlogiem P0/P1/P2: docs/SLEDCZY_RUNDA_<n>.md. W każdej rundzie odpowiada też na stałe pytanie: jakie jeszcze funkcjonalności dodać, żeby być najlepszym narzędziem OSINT na świecie (docs/SLEDCZY_FUNKCJE_<n>.md).
2. **Dyrygent (Kai/Claude).** Dzieli backlog na zadania dla Budowniczych (jedno zadanie = jeden worktree, osobne pliki), pilnuje prawa i zasad designu.
3. **Budowniczy (agent kodujący).** Wykonuje zadania P0 i P1, z testami, zrzutami 1440 i 390, pomiarem odstępów i bez wdrażania. Raport w zlecenia-codex\.
4. **Przegląd i wdrożenie.** Dyrygent przegląda zmiany, składa je, commituje. **Wdrożenie robi właściciel** (komendy w WDROZENIE-komendy.txt).
5. **Śledczy (weryfikacja).** Po wdrożeniu powtarza scenariusze, sprawdza kryteria odbioru każdej poprawki (zaliczone lub nie), ocenia ponownie.
6. Powrót do punktu 2, aż **każdy obszar ma co najmniej 8/10** i brak otwartych P0, albo do wyczerpania budżetu rund (maks. 6 rund bez nowej decyzji właściciela).

## Ograniczenia
- Wdrożenie jest po stronie właściciela, więc runda zamyka się wtedy, gdy zmiany trafią na produkcję. Zalecam zbierać zmiany z 1-2 dni w jedną paczkę.
- Śledczy ocenia to, co widzi na produkcji. Zmiany niewdrożone sprawdza tylko na podstawie kodu i testów.
- Ocena Śledczego to ocena modelu AI odgrywającego rolę, nie opinia prawdziwego dziennikarza. Dlatego dla kluczowych decyzji (model danych, język, prawo) dodajemy konsultację prawnika i, w miarę możliwości, test z prawdziwymi dziennikarzami (pilotaż).

## Rejestr rund
| Runda | Data | Średnia | Najniższy obszar | Otwarte P0 | Raport |
|---|---|---|---|---|---|
| 1 | 11.10.2026 | 4,4 | kompletność 3, zmiany w czasie 3 | 5 (P0-1..P0-5) | docs/SLEDCZY_RUNDA_1.md |
