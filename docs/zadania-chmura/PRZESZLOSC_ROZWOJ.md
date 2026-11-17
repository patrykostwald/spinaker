# Zadanie: przeszłość.today - wznowienie rozwoju, sprint „dane i przepływy” (gałąź `cloud/przeszlosc-rozwoj`)

Przeczytaj `docs/zadania-chmura/WSPOLNE.md`.

## Problem (właściciel, 23.10)
„Na przeszłość.today nie ma wszędzie zaciągniętych danych, czy to z KRS, czy z innych rzeczy. Nie ma też ciągle przepływów
pieniędzy ani dodatkowych funkcji, a przecież był plan rozwoju.” Rozwój stanął ok. 14.10 - trzeba go wznowić i dowieźć.

## Materiały
`docs/SLEDCZY_*.md` (rola recenzenta-dziennikarza śledczego, rundy ocen, backlog funkcji P0/P1/P2), `docs/PRZESZLOSC_*.md`
(źródła danych, licencja KW), kod przeszłości w `backend/` (szukaj „przeszlosc”, KRS, BZP, TED, NIW, oświadczenia) i
`frontend/`. Pozycjonowanie: narzędzie do badania przeszłości dla dziennikarzy; w becie wszystkie funkcje dla wszystkich,
bez cen na stronie.

## Co zrobić
1. **Inwentarz** (`docs/PRZESZLOSC_STAN_2026-10-23.md`): które źródła są zbudowane, które działają w harmonogramie, które są
   tylko w kodzie; które sekcje profilu osoby i podmiotu mogą być puste i dlaczego; co z backlogu Śledczego zrobione, co nie.
2. **Pokrycie KRS**: każda osoba publiczna i każdy podmiot w bazie powiązany z KRS przez oficjalne API api-krs.ms.gov.pl
   (odpis aktualny i pełny, legalne, z limitem i ponawianiem), nocne uzupełnianie braków z kolejką, komenda raportu pokrycia.
   Powiązanie osoba-spółka tylko po twardych identyfikatorach lub z potwierdzeniem (imiennicy!), jak w `weryfikator_tozsamosci`.
3. **Przepływy pieniędzy v1**: widok na profilu osoby i podmiotu: skąd do kogo płyną pieniądze publiczne (zamówienia BZP/TED,
   dotacje NIW i inne zbudowane źródła, umowy z rejestru, jeśli są), z datami, kwotami, źródłem każdej pozycji; prosty wykres
   przepływu (drzewo/sankey) i tabela; API + front; zasady designu z `CLAUDE.md` (boksy, 1440 i 390 px).
4. **Następne funkcje z backlogu P0/P1** Śledczego, ile się zmieści (np. alerty, wspólne mianowniki, raport PDF) - wybierz te,
   które dają dziennikarzowi najwięcej przy danych, które już mamy.
5. **Runda Śledczego** po zmianach: oceń 10 obszarów 0-10 tak jak w `SLEDCZY_RUNDA_*`, zapisz `docs/SLEDCZY_RUNDA_3.md`
   i nowy backlog, żeby następna sesja mogła kontynuować.

Celuj w ok. 3 godziny. Ważniejsze, żeby dane były prawdziwe i pełne, niż żeby było dużo funkcji.

## Dopisek właściciela 23.10: filtry głosowań
W sekcji Głosowania (profil osoby i widok ogólny) jasny filtr rodzaju głosowania: posiedzenia Sejmu (plenarne), poszczególne
komisje sejmowe (wybór komisji), Senat, Parlament Europejski i inne, które mamy lub możemy legalnie mieć. Do tego filtry
daty/kadencji, wyniku i zgodności z klubem. Najpierw sprawdź dostępność danych:
- Sejm plenarne: api.sejm.gov.pl (głosowania imienne) - już częściowo w bazie.
- Komisje: api.sejm.gov.pl ma komisje i posiedzenia; czy są imienne głosowania komisji [DP] - jeśli nie ma imiennych, pokaż
  wyniki komisji (przyjęto/odrzucono, z druku/sprawozdania) bez przypisywania głosów osobom; nie zgaduj.
- Senat: oficjalne wyniki głosowań senat.gov.pl (szanuj robots, limit); Parlament Europejski: oficjalne dane głosowań imiennych
  (otwarte dane PE).
Filtr pokazuje tylko rodzaje, dla których mamy dane, z liczbą pozycji przy każdym; puste rodzaje opisane „brak danych w źródle”.
Design wg CLAUDE.md (jedna linia filtrów, cele 44 px, 1440 i 390 px).
