# Brief strony „Jak działamy”

Stan decyzji: 14 września 2026. To brief treści i ruchu, bez wdrożenia interfejsu.

## Cel jednej minuty

Osoba, która poświęci stronie minutę, ma zrozumieć trzy rzeczy: spin.clinic gromadzi publiczne materiały w trwałej bazie, pokazuje kontekst każdego boxa i rozwija narzędzia pozwalające społeczności budować sprawdzalne nitki. Strona ma być zrozumiała jednocześnie dla czytelnika, dziennikarza, partnera i inwestora. Nie przedstawia planów jako gotowych funkcji.

## Cztery części

### 1. Czym jest spin.clinic

Proponowany lead: **„Jedno miejsce, w którym wiadomość nie znika po jednym dniu.”**

spin.clinic jest bazą publicznych materiałów, narzędziem do odnajdywania ich kontekstu i — w kolejnych etapach — społecznością tworzącą własne, źródłowe nitki. Każdy box zachowuje autora, datę, pochodzenie i odnośnik do oryginału. Zamiast jednej odpowiedzi pokazujemy oś zdarzeń i materiały, z których można ją samodzielnie sprawdzić.

Nad leadem lub bezpośrednio pod nim pokazujemy najwyżej trzy mierzalne liczby. Każda ma datę i precyzyjną nazwę, np. `źródła w katalogu`, `zachowane boxy`, `publikacje dodane w ostatnich 24 h`. Nie pokazujemy szacowanej kompletności ani liczby rekordów oczekujących jako już zebranych danych.

### 2. Jedno drzewo, trzy etapy

Pionowa oś ma trzy węzły. Przy każdym węźle lewa kolumna wyjaśnia **Wyszukiwarkę i kontekst**, prawa **Dr Spina**, a krótki trzeci wiersz opisuje społeczność i udział redakcji. Technologie pojawiają się jako zwięzły podpis, bez osobnej ściany logotypów.

#### Etap I — MVP: działające archiwum

**Wyszukiwarka i kontekst:** publiczne RSS, API, mapy stron oraz dozwolone strony; normalizacja metadanych; deduplikacja; wyszukiwanie pełnotekstowe i semantyczne; po kliknięciu boxa chronologiczna oś powiązanych publikacji. Publiczny interfejs opiera się na boxach i nitkach, nie wymaga czatu z AI.

**Dr Spin:** Dr Spin to narzędzie weryfikacji spinów — pomaga rozpoznawać sprawdzalne twierdzenia, docierać do źródeł pierwotnych i układać najważniejszy kontekst wokół wypowiedzi. Zewnętrzne modele AI przygotowują karty kontekstowe, a każdą publiczną analizę zatwierdza redakcja spin.clinic.

**Portal i ludzie:** wszystkie nitki tworzą ludzie. Kandydaci zgłaszają się przez formularz kontaktowy; w MVP zapraszamy przede wszystkim dziennikarzy i autorów kont na X, które po weryfikacji można powiązać z profilem w portalu. Główna zawiera bieżące wiadomości, TOP 10, temat dnia, jedną lub wyjątkowo dwie nitki Dr Spin, jawnie sponsorowaną nitkę i materiały autoryzowanych autorów.

**Technologie:** Next.js/PWA, Django API, PostgreSQL/Supabase, kolejki harvesterów, provider-neutral AI z pilotami OpenAI i Mistral EU.

#### Etap II — społeczność i automatyczny kontekst

**Wyszukiwarka i kontekst:** konta zapisują tematy, źródła, alerty i ulubione nitki. RAG oraz graf powiązań rozwijają kontekst boxów. Użytkownik tworzy nitki i buduje widoczną historię źródłowej pracy.

**Dr Spin:** system publikuje bez każdorazowego zatwierdzenia wyniki spełniające ustalone progi jakości i zakres niskiego ryzyka. Redakcja kontroluje próbki, wyjątki, odwołania i korekty; brak wystarczającego kontekstu automatycznie zatrzymuje publikację.

**Portal:** powstaje osobna przestrzeń nitek społeczności oraz **Izba przyjęć** dla nowych propozycji. Najlepsze nitki po przejściu jawnych progów jakości i moderacji mogą trafić na główną. Na głównej poza nimi pozostają wiadomości oraz autorzy zatwierdzeni przez redakcję. Profile pozwalają przypinać nitki i świadomie ujawniać wybrane reakcje oraz komentarze.

**Aplikacja:** natywna aplikacja na iOS i Androida przenosi sprawdzone funkcje portalu: osobiste paski, ulubione, reakcje, komentarze i alerty push zsynchronizowane z kontem.

**Technologie:** Supabase Auth, system ról, moderacja i reputacja, powiadomienia push/e-mail, wersjonowany ranking, RAG, graf wiedzy i analityka z ochroną prywatności.

#### Etap III — własny silnik kontekstu

**Wyszukiwarka i kontekst:** możliwie kompletne, legalnie pozyskane archiwa mediów, BIP-ów, instytucji, dokumentów, głosowań, audio i wideo. Własny silnik łączy osoby, zdarzenia, wypowiedzi i dokumenty, zachowując pochodzenie każdego wniosku.

**Dr Spin:** własny, ewaluowany model reaguje blisko czasu publikacji, stale pokazuje kontekst, niepewność i historię korekt. Redakcja nadzoruje metodę, jakość i odwołania, a nie każdą pojedynczą publikację.

**Portal:** dojrzała społeczność tworzy i ocenia nitki, a reputacja wynika z jakości źródeł, korekt i historii pracy, nie z samej popularności.

**Technologie:** własny model z odpowiednią licencją, RAG i graf wiedzy, speech-to-text, video-to-text, OCR, wersjonowane zbiory ewaluacyjne i automatyczna kontrola jakości.

## 3. Metoda i ograniczenia

Jedna zwarta sekcja wyjaśnia: te same reguły dla każdej strony sporu; pierwszeństwo źródeł pierwotnych; oddzielenie faktu, opinii i nieweryfikowalnego twierdzenia; jawne braki; publiczne korekty; link do oryginału; legalny zakres pozyskania. AI może przeoczyć materiał, źle połączyć zdarzenia i nie zna prywatnego ludzkiego kontekstu. Wynik ma być sprawdzalny, podważalny i możliwy do poprawienia.

## 4. Autor

Proponowana treść: **„spin.clinic buduje obecnie jedna osoba, wspierana przez różne narzędzia AI. Nie jestem i nigdy nie byłem związany z partią polityczną, kołem ani klubem. Mam własne poglądy i — jak każdy — mogę się mylić, dlatego projekt opieram na źródłach, jawnej metodzie i korektach, a nie na osobistym autorytecie. Zostałem niedawno ojcem. Chcę zbudować miejsce, w którym mój syn i inni ludzie będą mogli łatwiej sprawdzić, skąd pochodzi informacja i czego w niej brakuje.”**

Przed publikacją właściciel zatwierdza każde zdanie biograficzne. Nie podajemy nazwiska, adresu, miejsca pracy ani danych rodziny, jeśli sam nie zdecyduje inaczej.

## Ruch i prezentacja

Strona pozostaje minimalistyczna. Przy przewijaniu pionowa linia drzewa łagodnie się wypełnia, a kolejne węzły i dane pojawiają się krótkim przesunięciem oraz zmianą krycia. Liczniki mogą odświeżać się po pobraniu aktualnych danych, bez udawanej animacji wzrostu. Schemat box → powiązania → oś czasu może przepłynąć przez ekran raz, gdy znajdzie się w polu widzenia. Ruch nie blokuje treści, nie powtarza się agresywnie i jest wyłączany przez `prefers-reduced-motion`.
