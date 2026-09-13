# spin.clinic — obowiązujący zakres MVP

Strategia dostawców AI: [AI_PROVIDER_PLAN.md](AI_PROVIDER_PLAN.md).

Aktualizacja 13 września 2026: nadrzędne uzupełnienie etapów, harvestingu, uprawnień i współpracy z Claude znajduje się w [PLAN_2026-09-13.md](PLAN_2026-09-13.md). Poniższy opis z 9 września zachowuje kontekst funkcji; nie oznacza wdrożenia nowego Supabase.

Aktualizacja: 9 września 2026. Ten dokument zastępuje wcześniejsze warianty produktu opisane w historycznych sekcjach PROGRESS.md.

## Produkt

Archiwum źródłowych doniesień medialnych i dokumentów, z osobistym wyborem źródeł oraz tematów. Nie tworzymy automatycznych skrótów dnia ani nie przedstawiamy zestawienia źródeł jako dowodu prawdziwości. Tytuł, źródło, data i miniatura muszą mieć rzeczywiste pochodzenie. Znane braki są jawne. Archiwalne importy, aktualizacja źródeł, kontrole jakości i kopie zapasowe pozostają podstawą.

## Strona i personalizacja

1. Większy pasek najnowszych publikacji wszystkich aktywnych źródeł.
2. Pasek bieżących publikacji wybranych dziesięciu źródeł — wybór źródeł przez redakcję, nie pomiar popularności ani streszczenie.
3. Własne zapisane paski: hasło, temat, rodzaj materiału i źródła; możliwość kilku pasków.
4. Dwie redakcyjne nitki marki spin.clinic: przekaz obozu rządzącego i opozycji. Bez fikcyjnych wypowiedzi. Publikacja po decyzji redaktora.
5. Jedno oznaczone miejsce na nitkę sponsorowaną. Wizualny przykład nie jest rzeczywistą płatną kampanią i nie trafia jako fikcyjne wydarzenie do archiwum.
6. Siatka bieżących materiałów z filtrami. Typ materiału i temat są osobnymi wymiarami. Tematy opierają się na kategoriach/oznaczeniach wydawców; niewiadome pozostają niewiadome.

Kliknięcie boxa otwiera źródło i kontekst z całej dostępnej historii, licznikami kategorii oraz paskami dat. Związki tematyczne nie dowodzą przyczynowości. Negatywne i pozytywne komentarze w oddzielnych, stonowanych kolumnach.

## Konta i nitki

Konto publiczne od startu: personalizacja, ulubione nitki, jedna opinia na materiał i eksport do X. Historia aktywności na profilu jest prywatna domyślnie i publikowana tylko po decyzji użytkownika. Publiczny komentarz pod materiałem należy wyraźnie odróżnić od udostępnienia zbiorczej historii profilu. Minimalne dane konta; brak wymogu prawdziwego nazwiska.

Zwykłe konta nie publikują nitek. Redakcja może przyznać dziennikarzowi bezpłatne uprawnienia autorskie; użytkownik nie nadaje ich sobie sam. Docelowa wylęgarnia, awanse według ocen i otwarte tworzenie nitek są późniejszym etapem.

Nitka sponsorowana ma widoczne oznaczenie finansowania także w boxach i eksporcie. Sponsor nie zmienia archiwum, wyników ani źródłowych rekordów. Bez banerów reklamowych. Wsparcie przez BuyCoffee/Patronite po podaniu rzeczywistych adresów. Stawki kampanii ustalane później na podstawie zmierzonego ruchu i ekspozycji.

## AI i X

AI wspiera odnajdywanie powiązanych publikacji i pracę redakcji. Publiczne pytania do AI i generowane odpowiedzi nie są potrzebne do startu: użytkownik przegląda boxy, klasyczną wyszukiwarkę bazy, nitki redakcji i autoryzowanych autorów oraz kontekst po kliknięciu boxa. Zaplecze monitorowania potwierdzonych kont politycznych wymaga konfiguracji X, limitów i przeglądu redakcyjnego. Nie deklarujemy uruchomionego AI lub pobierania X bez rzeczywistych kluczy. W pierwszej wersji eksportujemy gotowe teksty; automatyczne publikowanie całych nitek wymaga osobnej integracji konta X.

## Jakość i bezpieczeństwo

Oddzielne uprawnienia kont publicznych, dziennikarzy i redakcji; kontrola właściciela wszystkich ustawień, CSRF, walidacja i ograniczenia żądań. Weryfikacje mutacji na osobnej bazie. Przed publicznym uruchomieniem: porządkowanie pozostałości starych wariantów, przegląd bezpieczeństwa, testy uprawnień i odzyskiwania danych, konfiguracja produkcyjnych sekretów/HTTPS/kopii oraz obsługi kont i moderacji. Nie obiecujemy systemu odpornego na każde włamanie.

## Stan wykonania

Aktualne szczegóły wdrożenia, uruchomień, pomiarów i braków są w najnowszym wpisie PROGRESS.md. Ten dokument opisuje uzgodniony produkt; sam zapis wymagania nie oznacza, że funkcja jest już uruchomiona.
