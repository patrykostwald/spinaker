# Finansowanie MVP: BuyCoffee, Patronite i kolejne kroki

## Decyzja na start

Uruchom **BuyCoffee jako pierwszy kanał** i ustaw jeden jasny, publiczny cel:

> **Komputer dla redakcji i rozwój Bazy źródeł**  
> Wpłaty finansują sprzęt potrzebny do pracy nad portalem, weryfikację źródeł i rozwój narzędzi. Wsparcie nie daje wpływu na dobór materiałów, wyniki wyszukiwania ani nitki redakcyjne.

To jest najprostsze dla osoby, która chce wpłacić jednorazowo. Patronite warto uruchomić równolegle tylko wtedy, gdy możemy regularnie informować patronów, co powstało dzięki ich wsparciu. Nie obiecujemy patronom wcześniejszego dostępu do ocen, wpływu na redakcję ani reklamowego traktowania materiałów.

## 1. BuyCoffee: konfiguracja

1. Załóż profil projektu w [BuyCoffee](https://buycoffee.to/).
2. Wybierz nazwę zgodną z portalem, np. `spin.clinic`, i wstaw logo oraz krótki opis:

   > spin.clinic porządkuje materiały według źródeł i czasu. Budujemy publiczną Bazę, w której każdy materiał prowadzi do oryginału.

3. Ustaw cel „Komputer dla redakcji i rozwój Bazy źródeł”. Nie podawaj ceny sprzętu, dopóki nie wybierzesz konkretnej konfiguracji; potem opublikuj aktualną kwotę celu i krótkie rozliczenie postępu.
4. Przejdź weryfikację profilu i ustaw metodę wypłaty.
5. Skopiuj publiczny adres profilu, np. `https://buycoffee.to/twoj-profil`.
6. W lokalnym pliku `.env` ustaw:

   ```env
   BUYCOFFEE_URL=https://buycoffee.to/twoj-profil
   ```

7. Uruchom ponownie usługi. Strona `/wsparcie` pokaże wtedy prawdziwy link, gdy frontend korzysta z tej konfiguracji.
8. Zrób własną małą wpłatę testową i sprawdź, czy nazwa projektu, opis celu i wypłata są poprawne.

BuyCoffee podaje obecnie prowizję 10% od jednorazowej wpłaty i 5% od subskrypcji; przed uruchomieniem potwierdź to w aktualnym cenniku i regulaminie. Profil wymaga weryfikacji tożsamości. Źródła: [opłaty BuyCoffee](https://buycoffee.to/pl/blog/ile-naprawde-zostaje-z-wplaty), [zasady platformy](https://buycoffee.to/rules/guidelines).

## 2. Patronite: konfiguracja

1. Załóż profil autora/projektu na [Patronite](https://patronite.pl/).
2. Ustaw ten sam opis misji i zasadę niezależności redakcyjnej.
3. Zacznij od maksymalnie trzech prostych progów miesięcznych, np. 10 zł, 25 zł i 50 zł.
4. Korzyść powinna być informacyjna i nie redakcyjna: comiesięczny raport „co dodaliśmy do Bazy”, podziękowanie na stronie wsparcia za zgodą patrona albo spotkanie online o rozwoju projektu.
5. Nie oferuj wpływu na wnioski, kolejność materiałów, moderację ani wybór polityków.
6. Skopiuj publiczny adres profilu i ustaw w `.env`:

   ```env
   PATRONITE_URL=https://patronite.pl/twoj-profil
   ```

7. Przed publikacją sprawdź wymagania weryfikacyjne i regulamin Patronite. Źródła: [jak działa Patronite](https://patronite.pl/jak_to_dziala), [regulamin](https://patronite.pl/regulamin).

## Tekst na stronę wsparcia

> **Wesprzyj rozwój spin.clinic**  
> Budujemy Bazę materiałów z widocznym źródłem, datą i linkiem do oryginału. Twoja wpłata pomaga finansować sprzęt, rozwój portalu oraz weryfikację dostępu do źródeł. Wsparcie nie kupuje wpływu na redakcję, wyniki ani kontekst publikacji.

## Co jeszcze ma sens na etapie MVP

| Forma | Kiedy uruchomić | Zasada |
| --- | --- | --- |
| Jednorazowe wpłaty BuyCoffee | teraz | Jeden konkretny cel, publiczny postęp i proste rozliczenie. |
| Patronite miesięczny | po ustaleniu stałego rytmu aktualizacji | Maksymalnie trzy progi i raporty z rozwoju. |
| Otwarta zbiórka na konkretny koszt | po wyborze komputera lub opłaty za API X | Cel, kwota, termin i opis rezultatu po zakupie. |
| Granty i konkursy dla mediów obywatelskich / technologii społecznych | gdy mamy demo, politykę prywatności i budżet | Finansowanie opisujemy publicznie; darczyńca nie ingeruje w treść. |
| Partnerstwa edukacyjne | po pierwszych użytkownikach | Warsztat lub prezentacja narzędzia, zawsze z opisem partnera. |
| Sponsorowana nitka lub materiał | dopiero po stabilnym ruchu i zasadach reklamowych | Każdy element musi być wyraźnie oznaczony. Sponsor nie zmienia Bazy ani wyników. |

## Czego nie uruchamiać teraz

- płatnego dostępu do podstawowej Bazy i źródeł;
- reklam politycznych lub pieniędzy za przedstawienie określonej osoby albo tematu;
- wielu progów, gadżetów i benefitów, których nie damy rady regularnie obsłużyć;
- zbiórki bez publicznego celu i późniejszego krótkiego rozliczenia.

## Kolejność na najbliższe dwa tygodnie

1. BuyCoffee z celem na komputer i linkiem na `/wsparcie`.
2. Krótki post wyjaśniający, co już działa w MVP i na co idą wpłaty.
3. Po pierwszych wpłatach: prosty wskaźnik postępu oraz aktualizacja raz w tygodniu.
4. Patronite dopiero po przygotowaniu comiesięcznego raportu z prac.
5. Po uruchomieniu publicznego demo: lista właściwych grantów i partnerstw edukacyjnych.
