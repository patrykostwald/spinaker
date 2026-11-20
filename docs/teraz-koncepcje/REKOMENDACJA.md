# Rekomendacja: mapa Teraz (G1, 20.11.2026)

**Werdykt: na stronę produkcyjną bierzemy koncepcję A „Rzeźba nocna”. Z koncepcji B przenosimy karty „Zasięg z treści alertów RCB”.
Makietę 3D z B zostawiamy jako możliwy widok dodatkowy (np. obraz do udostępniania), nie jako widok główny.**

Panel designu był jednogłośny: UX, czytelnik-laik i dostępność niezależnie wybrali A z kartami RCB z B.

## Dlaczego A

| Kryterium | A „Rzeźba nocna” | B „Makieta Polski” |
|---|---|---|
| Czytelność liczby na powiat | płaska mapa, każdy powiat widoczny, pole nie zniekształcone | perspektywa zmniejsza północ, słupki zasłaniają powiaty za nimi (Śląsk, Małopolska) |
| Ryzyko odczytu „wysoko = groźnie” | małe (jedna barwa, podpis „nie poziom zagrożenia”) | duże: laik czyta wysoki słupek jako ważność |
| Telefon 390 px | mapa czytelna, podpisy się mieszczą | makieta mała, skupiska słupków, kreskowanie ledwo widać |
| Dostępność | łatwiej: brak kamery i przeciągania; tabela powiatów wystarcza | trudniej: obrót, zasłanianie, wskazywanie brył |
| Zgodność z konwencją map (Jakob) | wysoka, pasuje do MapLibre z obecnej strony Teraz | niska, wymaga własnego silnika 3D |
| Koszt wdrożenia | warstwa rzeźby i warstwic do istniejącej mapy MapLibre | nowy widok canvas/WebGL, sortowanie głębi, wskazywanie |

Rzeźba i warstwice dają poczucie miejsca, ale pozostają tłem: pod powiatami z danymi rzeźba jest przygaszona,
żeby jasne zbocza nie myliły się z barwą liczby (uwaga panelu dostępności).

## Co przenieść z B do A

1. **Karty RCB** (zdanie źródła, „objęte / wyłączenia / nierozpoznane”) i obrys strefy alertu po wybraniu karty.
   Laik uznał je za najbardziej zrozumiały element obu prototypów.
2. **Obrys strefy jako jedna linia 2 px** w kolorze kości (zamiast obrysów każdego powiatu).

## Twarde zasady, które oba prototypy już spełniają (do zachowania w produkcji)

- Grafika nie koduje wagi; legenda: „liczba komunikatów w okresie”; pod tytułem: „nie poziom zagrożenia”.
- „Brak w naszych danych” to wzór z podpisem (źródło, okres, data), nigdy zero ani zieleń; „0” to osobny stan „mamy dane”.
- Zasięg przybliżony: linia przerywana z podpisem i tematem; nie wliczamy go do liczb powiatów.
- Wyłączenia: wzór kropkowany, „wyłączone w treści komunikatu (sprawdź oryginał)”.
  W produkcji pokazujemy wyłączenie na mapie tylko przy pewnym dopasowaniu nazwy i województwa; inaczej obowiązuje
  obecna, ostrożniejsza zasada parsera (R38g: nie nazywamy wyłączonych jednostek, odsyłamy do treści).
- Animacje: domyślnie według `prefers-reduced-motion`, przełącznik „Animacje” zapamiętany; tryb prosty bez rzeźby i ruchu.
- Tekstowy odpowiednik mapy: „Najwięcej komunikatów” i tabela wszystkich powiatów.

## Następne kroki (do decyzji właściciela)

1. Zlecenie budowy: warstwa rzeźby (NMT GUGiK albo Copernicus, kafle rastrowe) i warstwic w MapLibre na stronie Teraz, skala 4 klas, karty RCB.
2. Pole „Wpisz miejscowość” nad mapą: laik przychodzi z pytaniem „co u mnie?”, a mapa sama na nie nie odpowiada.
3. Prostszy język w panelu źródeł: typ łącza pod „szczegóły”, nazwa i stan na wierzchu.
4. Skala klas liczona z rozkładu danych (kwantyle albo stałe progi po kalibracji na prawdziwych danych), nie z danych próbnych.
5. Potwierdzić: „MCI” czy „MCP” w liście łączy.
