# Automaty jakości danych

Pierwszy etap jest deterministyczny, ograniczony limitem i nie kasuje, nie scala ani nie przepisuje artykułów. `ArticleQualityProfile` zapisuje kanoniczny URL, hashe tytułu i dostępnej treści, kompletność pochodzenia oraz wersję reguł. Parametry śledzące są usuwane, ale parametry merytoryczne URL pozostają.

Duplikat kanonicznego URL w obrębie jednego źródła dostaje flagę `canonical_duplicate`. Rekord pozostaje w bazie do jawnej decyzji redakcyjnej. Zgodna treść albo dokładnie znormalizowany tytuł opublikowany w przedziale 48 godzin w różnych źródłach tworzy `similar_publication`. Oba artykuły pozostają samodzielnymi rekordami ze swoim źródłem.

`SourceQualityState` przechowuje próbkę ostatnich 100 artykułów: udział dat, autorów, tekstów i prawidłowych URL. Pierwsza próbka staje się punktem odniesienia. Spadek dowolnej metryki o co najmniej 25 punktów procentowych przy próbce co najmniej 20 rekordów zapisuje sygnał dryfu. To alarm do sprawdzenia parsera, nie automatyczna naprawa.

Kolejne etapy, w tej kolejności:

1. Audyt próbek: trwałe losowanie warstwowe według źródła i metody pozyskania, formularz oceny oraz osobne metryki błędów daty, autora, treści i pochodzenia.
2. Ekstrakcja encji: wersjonowane wzmianki o osobach, instytucjach, miejscach i aktach prawnych wraz z pozycją w tekście, pewnością i możliwością ręcznej korekty.
3. Oś czasu: zdarzenia oddzielone od publikacji, jawne relacje artykuł–zdarzenie, zakresy niepewnych dat i historia korekt.
4. Indeks hybrydowy: indeks słów i encji jako podstawa; wektory dopiero po przygotowaniu ocenionego zbioru par. Ocena przez Recall@k i MRR, z filtrem źródła, daty, języka i uprawnień.

Każdy etap musi być idempotentny, mieć wersję reguł/modelu, ograniczenie partii, trwały kursor, metryki czasu i błędów oraz możliwość pełnego odtworzenia po zmianie reguł. Uruchomienie masowe na aktywnej bazie wymaga osobnego planu wdrożenia i obserwacji.
