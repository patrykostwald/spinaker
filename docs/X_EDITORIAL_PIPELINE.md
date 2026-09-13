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
6. W MVP dyżurny redaktor zatwierdza, poprawia albo odrzuca. Decyzja jest publikowana jako wynik procesu `spin.clinic`, a nie osobista opinia administratora.
7. Po publikacji system przygotowuje teksty do ręcznego opublikowania na koncie spin.clinic wraz z linkiem do boxa/nitki.

## Odpowiedzialność redakcyjna i dojście do automatyzacji

Automatyzacja ani podpis „AI” nie przenoszą odpowiedzialności z wydawcy na model. Dlatego rozdzielamy autora analizy od operatora technicznego: publicznym autorem jest `Redakcja spin.clinic`, a nazwisko osoby klikającej zatwierdzenie pozostaje w prywatnym dzienniku audytowym. Na stronie pokazujemy wersję metody, czas analizy, wykorzystane źródła, stopień pewności, historię zmian oraz przycisk „zgłoś źródło / poproś o korektę”.

Droga do automatyzacji ma trzy poziomy:

1. **Asystent** — AI przygotowuje twierdzenia, dowody i szkic; jedna osoba zatwierdza publikację.
2. **Kontrolowana autopublikacja** — po zebraniu reprezentatywnego zestawu decyzji redakcji system może sam publikować jedynie niskiego ryzyka etykiety oparte na jednoznacznym, ustrukturyzowanym źródle, np. wynik głosowania, data, liczba lub dosłowne porównanie dwóch oficjalnych dokumentów. Losowa próbka i wszystkie odwołania trafiają do kontroli człowieka.
3. **Szersza automatyzacja** — dopiero po niezależnym audycie jakości i prawnym, ustalonym progu błędów, mechanizmie natychmiastowego wycofania oraz uzyskaniu wymaganych zgód X. Oceny typu „pomija kontekst” i „spin dnia” pozostają decyzją redakcyjną, dopóki nie istnieje wiarygodny, sprawdzony standard ich automatycznej oceny.

Każda publiczna karta ma status `WSTĘPNA ANALIZA`, `ZWERYFIKOWANE PRZEZ REDAKCJĘ`, `SKORYGOWANE` albo `WYCOFANE`. Dla zarzutów dotyczących konkretnej osoby, intencji, manipulacji lub kłamstwa wymagamy dwóch akceptacji i oceny źródeł pierwotnych. Nie używamy automatycznego rankingu „najbardziej kłamiących polityków”.

Krytykę kierujemy do udokumentowanej decyzji i metody: każda etykieta ma trwały identyfikator, uzasadnienie zdanie po zdaniu i publiczną historię korekt. To nie eliminuje sporów, ale pozwala odpowiadać dowodami i poprawiać błędy bez personalizowania konfliktu.

## Etykiety

Nie używamy automatycznej etykiety „spin confirmed”. Preferowane jawne wyniki redakcyjne:

- `POMIJA ISTOTNY KONTEKST`
- `SPRZECZNE Z DOSTĘPNYM ŹRÓDŁEM`
- `ZGODNE Z DOSTĘPNYMI ŹRÓDŁAMI`
- `BRAK WYSTARCZAJĄCYCH DANYCH`
- `OPINIA / TWIERDZENIE NIEWERYFIKOWALNE`

„Spin dnia” może być nazwą redakcyjnego cyklu, ale karta musi wskazywać konkretne twierdzenie, źródła i ograniczenia. Nie przypisujemy intencji ani procentu spinu.

## Publikowanie na X

W MVP portal generuje szkic postu lub nitki, a redaktor publikuje go ręcznie. Nie odpowiadamy automatycznie pod postami polityków i nie dodajemy nieproszonych wzmianek. Według aktualnych zasad API odpowiedź jest dozwolona tylko wtedy, gdy autor oryginalnego postu jawnie przywołał konto odpowiadające; odpowiedzi generowane przez AI wymagają ponadto uprzedniej zgody X. Dlatego własne, źródłowe nitki spin.clinic są podstawowym kanałem dystrybucji.

## Kierunek partnerski wobec X

Integrację budujemy jako warstwę kontekstu i jakości rozmowy, którą można kiedyś zaoferować X, wydawcom i instytucjom: szybkie wykrycie sprawdzalnego twierdzenia, komplet źródeł, jawne uzasadnienie i historia korekt. Nie opieramy strategii na masowym zaczepianiu polityków ani obchodzeniu reguł platformy. Mierzymy dokładność, czas od publikacji do kontekstu, odsetek korekt i wykorzystanie źródeł pierwotnych; nie budujemy produktu do publicznego wskazywania naruszeń zasad X bez pisemnej zgody platformy.

## Budżet pilotażu

Aktualna publiczna cena odczytu wynosi 0,005 USD za zwrócony post, odczytu użytkownika 0,010 USD, utworzenia treści 0,015 USD, a utworzenia treści z URL 0,200 USD. Zasoby są zwykle deduplikowane w ramach dnia UTC. Ceny i limity trzeba potwierdzić w Developer Console przed zakupem.

Przykładowy bieżący monitoring:

- 100 kont × średnio 3 nowe posty/dzień: około 300 postów/dzień = 45 USD/miesiąc za odczyt.
- 150 kont × średnio 3 nowe posty/dzień: około 450 postów/dzień = 67,50 USD/miesiąc.
- 300 kont × średnio 3 nowe posty/dzień: około 900 postów/dzień = 135 USD/miesiąc.

To model orientacyjny; retweety, odpowiedzi, usunięcia i rzeczywista aktywność zmieniają wynik. Pilotaż zaczyna się od twardego limitu kredytów i alarmów 50/80/100%.

Pełny miesięczny limit 2 mln odczytów kosztowałby przy stawce jednostkowej 10 000 USD, dlatego nie służy jako budżet MVP. Archiwalny backfill X będzie osobno wycenioną, małą partią dopiero po pomiarze bieżącego strumienia.

Źródła zasad i cen: https://docs.x.com/x-api/getting-started/pricing, https://docs.x.com/x-api/fundamentals/post-cap, https://docs.x.com/developer-guidelines, https://docs.x.com/x-api/posts/manage-tweets/integrate
