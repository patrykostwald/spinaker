# spin.clinic — pakiet kontekstu dla pilotażu Mistral

Stan: 14 września 2026. Ten plik jest samowystarczalnym, odizolowanym kontekstem do pierwszej analizy. Nie zawiera sekretów, danych użytkowników ani dostępu do systemów.

## Cel produktu

spin.clinic ma być polskim archiwum publicznych źródeł i narzędziem do przedstawiania kontekstu chronologicznego. Podstawową jednostką jest box reprezentujący jedno źródło. Box zachowuje pochodzenie, tytuł, URL kanoniczny, datę publikacji, miniaturę, typ materiału, tematy wydawcy i nasze oddzielne klasyfikacje. Źródłem może być artykuł, reportaż, wywiad, film, podcast, reklama, publiczny post, oświadczenie, akt prawny, głosowanie, komunikat instytucji albo wzmianka.

System nie zmienia materiału źródłowego i nie przedstawia obecności źródła jako potwierdzenia wszystkich jego twierdzeń. Znane braki, nieudane importy i ograniczenia wydawców mają być widoczne. Nitka to uporządkowany chronologicznie wybór od 3 do 15 boxów. Nitki redakcyjne i Dr Spin są zatwierdzane przez człowieka przed publikacją.

## MVP

MVP obejmuje agregację bieżących i archiwalnych metadanych, wyszukiwarkę, konta użytkowników, personalizowane paski tematów, zapisane nitki, reakcje i pojedynczy komentarz użytkownika do boxa. Aktywność profilu może być ukryta. Udostępniany link prowadzi do boxa w spin.clinic wraz z kontekstem i odnośnikiem do oryginału.

Użytkownicy nie tworzą własnych nitek w pierwszym wydaniu. Redakcja publikuje nitki spin.clinic oraz wyraźnie oznaczone nitki sponsorowane. Sponsor nie może zmieniać źródłowych rekordów, wyników wyszukiwania ani klasyfikacji.

## Dane i harvesting

Źródła są katalogowane z tierem ważności, metodą pobierania, stanem RSS/sitemapy/crawlera, zakresem praw i stanem zgody. Import jest idempotentny i nie nadpisuje bezpiecznie zachowanych danych gorszym wynikiem. Należy przechowywać historię prób, kod odpowiedzi, czas, parser, powód błędu i następny termin próby. Pełny tekst może być pobierany lub przetwarzany tylko przy odpowiedniej podstawie; publiczna prezentacja metadanych również respektuje warunki źródła.

Gdy zakres użycia jest niepewny, system odkłada materiał do kolejki oceny. Administrator może zatwierdzić przygotowanie i wysłanie zapytania do właściciela źródła. Żaden agent nie wysyła wiadomości samodzielnie.

## Bieżąca architektura

Repozytorium zawiera backend Django/DRF i frontend Next.js. Baza docelowa działa w Supabase/Postgres, ale pierwszy pilotaż Mistral nie otrzymuje dostępu do Supabase. Obecny prototyp wyszukiwania internetowego jest przygotowany dla OpenAI Responses z web_search. Wyniki zewnętrzne przechodzą przez allowlistę aktywnych źródeł, walidację URL i odczyt publicznych metadanych. Próby AI są audytowane: dostawca, model, czas, status, znane zużycie i liczba narzędzi. Tajne prompty, klucze i pełne treści nie trafiają do logów użycia.

## Strategia AI

OpenAI pozostaje pierwszym dostawcą istniejącego prototypu wyszukiwania internetowego. Mistral jest drugim dostawcą pilotażowym. Europejski endpoint `https://api.eu.mistral.ai` ma być najpierw sprawdzony w trzech funkcjach:

1. klasyfikacja publicznych metadanych boxa,
2. ranking istniejących kandydatów do chronologicznej nitki,
3. embeddings do wyszukiwania podobnych rekordów.

Regionalny endpoint UE nie udostępnia wszystkich funkcji globalnych. Dostępność konkretnego modelu, structured output, function calling, embeddings i limitów należy potwierdzić dokumentacją lub krótkim testem. Globalnego wyszukiwania Mistral nie włączamy w tym pilotażu. DeepSeek jest wykluczony. Claude może pomagać w pracy nad repozytorium, lecz jego API nie jest wymagane w MVP.

Każdy dostawca ma działać przez wymienny adapter. Model zwraca propozycje i nie zapisuje bezpośrednio rekordów produkcyjnych. Powiązanie odwołuje się do istniejącego ID boxa lub jawnego URL źródła. Brak wystarczających danych jest poprawnym wynikiem. Wiedza własna modelu nie może uzupełniać braków jako fakt. Redaktor zatwierdza wynik.

Do zewnętrznych modeli nie wysyłamy danych kont, adresów e-mail, komentarzy ani prywatnej aktywności. W pilotażu trafia do nich zapytanie, publiczne metadane oraz ewentualnie fragment publicznego materiału, jeśli zakres użycia został potwierdzony. Odpowiedzi dostawcy nie stają się automatycznie danymi treningowymi. RAG i ewaluacja mają pierwszeństwo przed fine-tuningiem.

## Ewaluacja

OpenAI i Mistral należy porównać na tym samym zamkniętym zestawie 30–50 polskich przypadków. Zestaw obejmuje krótkie i wieloznaczne hasła, osoby o podobnych nazwiskach, wydarzenia rozciągnięte w czasie, brak danych, sprzeczne daty, źródła instytucjonalne, materiały audio-wideo i próby wymuszenia niedozwolonego źródła.

Mierzymy poprawność URL i dat, zgodność z allowlistą, trafność typu i kategorii, chronologię, jakość wyboru do 15 boxów, odsetek twierdzeń bez pokrycia, stabilność schematu, czas oraz koszt. Pilotaż przerywa się przy ujawnieniu danych prywatnych, wymyślaniu źródeł, omijaniu allowlisty, bezpośredniej mutacji produkcji lub braku kontroli kosztu.

## Przejrzystość

Portal ma otrzymać publiczną stronę „Jak działamy”. Wyjaśni zakres źródeł, sposób zbierania i aktualizacji, działanie wyszukiwarki i Dr Spina, znaczenie ocen, znane braki, korekty oraz datę zmiany metodologii. Nie ujawni sekretów, zabezpieczeń ani szczegółowych wag rankingu umożliwiających manipulację.

## Oczekiwany wynik pierwszego zadania

Mistral ma przygotować wyłącznie raport analityczny: minimalny interfejs adaptera, ścisłe schematy JSON dla trzech funkcji, kategorie testów, metryki i stop conditions, analizę zagrożeń, listę funkcji endpointu UE do sprawdzenia, odwracalny plan wdrożenia oraz handoff dla Codex. Nie ma pisać kodu, uruchamiać integracji, żądać sekretów ani projektować treningu na całym archiwum.
