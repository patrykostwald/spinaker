# Pilot API Sejmu — głosowania kadencji 10

Stan: 15 września 2026. Dokument wyznacza pierwszy kontrolowany pilot. Nie jest
uruchomieniem importu ani zgodą dla innych kanałów.

## Decyzja zakresowa

Pilot obejmuje wyłącznie API Sejmu, kadencję 10 i głosowania. Początek to trzy
pierwsze posiedzenia objęte ustalonym zakresem. Wykorzystywane są tylko dwa
udokumentowane typy adresów: wyszukanie/lista głosowań i szczegół pojedynczego
głosowania. Każdy rzeczywisty adres przechodzi bramkę API oraz trwały limit
hosta.

Surowa odpowiedź szczegółu jest wewnętrznym `content`: służy do kontroli
spójności oraz wersjonowania korekt. Nie jest automatycznie przekazywana do
zewnętrznego AI ani publikowana w całości.

Pierwszy publiczny box pokazuje tylko: tytuł, datę, numer posiedzenia, liczby
za/przeciw/wstrzymane/nieobecne, źródło i link do oryginału. Indywidualne głosy
oraz dane klubowe pozostają poza pierwszym widokiem publicznym, dopóki redakcja
nie zatwierdzi odrębnego zakresu prezentacji.

## Tempo

- Dni 1–3: maksymalnie 24 requesty na dobę, jeden worker, bez współbieżności.
- Dni 4–7: do 48 requestów na dobę wyłącznie po trzech dniach bez zatrzymania.
- Dni 8–14: do 96 requestów na dobę wyłącznie po przeglądzie tygodniowym.
- Między zakończeniem jednego requestu a rozpoczęciem następnego jest co
  najmniej 3 sekundy. Rezerwacja hosta chroni też długie odpowiedzi.

Limit dzienny jest limitem operacyjnym pilota, niezależnym od technicznego
odstępu. Nie rośnie samoczynnie.

## Warunki zapisu rekordu

Rekord może stać się boxem dopiero po jednoczesnym spełnieniu:

1. aktualnej karty dostępu dla konkretnego adresu API;
2. rezerwacji audytowej zapisanej przed transportem;
3. końcowego, append-only śladu tej samej próby z kodem, rozmiarem i hashem;
4. walidacji tożsamości: kadencja, posiedzenie, numer głosowania i kompletność
   danych liczbowych;
5. braku aktywnego zatrzymania źródła.

Niepełna próba audytowa nigdy nie tworzy boxa. Trafia do diagnostyki, a dane z
pamięci procesu są odrzucane.

`FetchAttempt` opisuje wyłącznie transport: że odpowiedź została odebrana albo
że jej wynik pozostał nieznany. Nie jest on deklaracją, że odpowiedź została
już pomyślnie sparsowana i zapisana jako box. Walidacja oraz zapis boxa są
odrębnym krokiem; ich błąd nie zmienia historycznego faktu udanej odpowiedzi
API, lecz zatrzymuje publikację rekordu i kieruje go do diagnostyki.

## Automatyczne zatrzymanie

Cykl zatrzymuje się przy: 401/403, trzech 429 w ciągu godziny, każdym naruszeniu
odstępu, nieudanym zapisie śladu audytowego, niezgodności karty kanału,
przekierowaniu na inny host, błędzie tożsamości albo pięciu kolejnych
niekompletnych próbach audytu. Wznowienie wymaga zapisanej diagnozy; nie dzieje
się automatycznie.

## Kontrola redakcyjna

Dwie próbki po 20 rekordów: po dniu 5 i po dniu 12. Dla każdego sprawdzane są
identyfikator, data, numer posiedzenia, tytuł, liczby zbiorcze, link do źródła
i komplet pochodzenia. Wynik to `pass`, `pass_with_note` lub `fail`.

Po 14 dniach rozszerzenie wymaga: kompletnego audytu, zera naruszeń odstępu,
obsłużonej korekty rekordu, co najmniej 19/20 pozytywnych wyników ostatniej
próbki oraz odrębnej karty dostępu dla następnego źródła.
