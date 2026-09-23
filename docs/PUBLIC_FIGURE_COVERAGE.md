# Pokrycie rejestru osób publicznych

Ten dokument opisuje zakres rejestru profili publicznych. Jest listą prac
importowych, nie listą osób i nie dowodem tożsamości konta X.

## Zasada wspólna

Każda pozycja musi pochodzić z jednego, oficjalnego rosteru albo profilu
instytucji. Rekord zawiera stały klucz źródłowy, nazwę roli, URL dowodu i datę
sprawdzenia. Samo zgodne imię i nazwisko nigdy nie łączy dwóch rekordów.

## Objęte aktualnie

| Grupa | Zakres | Źródło | Stan |
| --- | --- | --- | --- |
| Sejm | Aktywni posłowie | API Sejmu | synchronizowane |
| Senat | Aktywni senatorowie | Oficjalny roster Senatu | synchronizowane |
| Parlament Europejski | Polscy europosłowie | Oficjalne dane PE | synchronizowane |
| Rada Ministrów | Premier, wicepremierzy, ministrowie | KPRM | synchronizowane |
| Administracja rządowa | Wojewodowie | MSWiA | synchronizowane |
| Najwyższe funkcje państwowe | Prezydent RP i Prezydium Senatu | KPRP, Senat | synchronizowane |
| Kancelaria Prezydenta RP | Kierownictwo KPRP | KPRP | synchronizowane |

## Kolejność następnych importerów

| Priorytet | Grupa | Wymagany dowód | Stan |
| ---: | --- | --- | --- |
| 1 | Marszałek i wicemarszałkowie Sejmu | Oficjalne API lub strona Sejmu | oczekuje na pełny, aktualny roster |
| 2 | Kierownictwo KPRM | Oficjalna strona KPRM | do zbudowania adaptera |
| 3 | Marszałkowie województw | Oficjalne BIP-y urzędów marszałkowskich | osobne rostery regionalne |
| 4 | Prezydenci miast i burmistrzowie największych miast | Oficjalne BIP-y miast | osobne rostery samorządowe |
| 5 | Liderzy, wiceliderzy i rzecznicy partii | Oficjalne strony władz partii | adapter dla każdej partii |
| 6 | Kierownictwa klubów parlamentarnych | Oficjalne strony klubów lub izb | adapter dla każdego klubu |
| 7 | Szefowie najważniejszych organów państwa | Oficjalne strony NBP, NIK, RPO, PKW, KRRiT, UOKiK, KNF i innych urzędów | adapter dla każdej instytucji |

## Granice

- Nie importujemy osób z rankingów, mediów, Wikipedii ani wyszukiwarki jako
  profili publicznych.
- Wikidata i podobne zbiory mogą dostarczać wyłącznie kandydaturę konta X.
- Relacja z fundacją, stowarzyszeniem lub spółką wymaga bezpośredniego,
  publicznego dowodu oraz linku do wpisu źródłowego; nie używamy PESEL, daty
  urodzenia ani dopasowania nazwisk.
- Konto X pojawia się na profilu dopiero po bezpośrednim oficjalnym dowodzie.
