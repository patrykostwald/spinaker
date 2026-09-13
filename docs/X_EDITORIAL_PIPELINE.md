# X i codzienny proces redakcyjny Dr Spin

Stan na 14 września 2026. Integracja wyłącznie przez oficjalne API X.

## Zakres pilotażu

Zaczynamy od ręcznie zweryfikowanego katalogu około 100–150 kont: aktywni liderzy parlamentarni, członkowie rządu, rzecznicy, kluby i partie oraz najważniejsze instytucje. Rozszerzenie następuje po pomiarze kosztu i jakości. Przynależność do obozu pochodzi z jawnych, oficjalnych danych i ręcznej redakcyjnej klasyfikacji; nie jest wnioskowana przez model z zachowania użytkownika na X.

Nie wykonujemy pełnego archiwalnego importu X w MVP. Zachowujemy identyfikatory postów i dane dozwolone przez warunki API; wyświetlanie korzysta z wymaganej atrybucji i rehydracji. Danych X nie używamy do treningu własnego modelu.

## Przepływ

1. Collector pobiera nowe posty tylko z katalogu kont i deduplikuje je po ID.
2. Reguły grupują posty według ręcznie przypisanego obozu, czasu i wspólnych jawnych haseł.
3. AI proponuje kandydatów na „przekaz dnia” i rozbija wypowiedź na sprawdzalne twierdzenia. To wewnętrzny szkic, nie werdykt.
4. Wyszukiwarka bazy dobiera powiązane boxy, w pierwszej kolejności źródła pierwotne i materiały pokazujące różne strony.
5. System tworzy kartę redakcyjną: oryginalny post, twierdzenia, materiały za/przeciw, brakujące dane i proponowaną nitkę do 15 boxów.
6. Redaktor zatwierdza, poprawia albo odrzuca. Publiczna etykieta i publikacja zawsze wymagają człowieka.
7. Po publikacji system przygotowuje teksty do ręcznego opublikowania na koncie spin.clinic wraz z linkiem do boxa/nitki.

## Etykiety

Nie używamy automatycznej etykiety „spin confirmed”. Preferowane jawne wyniki redakcyjne:

- `POMIJA ISTOTNY KONTEKST`
- `SPRZECZNE Z DOSTĘPNYM ŹRÓDŁEM`
- `ZGODNE Z DOSTĘPNYMI ŹRÓDŁAMI`
- `BRAK WYSTARCZAJĄCYCH DANYCH`
- `OPINIA / TWIERDZENIE NIEWERYFIKOWALNE`

„Spin dnia” może być nazwą redakcyjnego cyklu, ale karta musi wskazywać konkretne twierdzenie, źródła i ograniczenia. Nie przypisujemy intencji ani procentu spinu.

## Publikowanie na X

W MVP portal generuje szkic postu lub nitki, a redaktor publikuje go ręcznie. Nie odpowiadamy automatycznie pod postami polityków i nie dodajemy nieproszonych wzmianek. Automatyczne odpowiedzi generowane przez AI wymagałyby uprzedniej zgody X i spełnienia zasad automatyzacji.

## Budżet pilotażu

Aktualna publiczna cena odczytu wynosi 0,005 USD za zwrócony post, odczytu użytkownika 0,010 USD, utworzenia treści 0,015 USD, a utworzenia treści z URL 0,200 USD. Zasoby są zwykle deduplikowane w ramach dnia UTC. Ceny i limity trzeba potwierdzić w Developer Console przed zakupem.

Przykładowy bieżący monitoring:

- 100 kont × średnio 3 nowe posty/dzień: około 300 postów/dzień = 45 USD/miesiąc za odczyt.
- 150 kont × średnio 3 nowe posty/dzień: około 450 postów/dzień = 67,50 USD/miesiąc.
- 300 kont × średnio 3 nowe posty/dzień: około 900 postów/dzień = 135 USD/miesiąc.

To model orientacyjny; retweety, odpowiedzi, usunięcia i rzeczywista aktywność zmieniają wynik. Pilotaż zaczyna się od twardego limitu kredytów i alarmów 50/80/100%.

Pełny miesięczny limit 2 mln odczytów kosztowałby przy stawce jednostkowej 10 000 USD, dlatego nie służy jako budżet MVP. Archiwalny backfill X będzie osobno wycenioną, małą partią dopiero po pomiarze bieżącego strumienia.

Źródła zasad i cen: https://docs.x.com/x-api/getting-started/pricing, https://docs.x.com/x-api/fundamentals/post-cap, https://docs.x.com/developer-guidelines, https://docs.x.com/x-api/posts/manage-tweets/integrate
