spin.clinic
Pełny plan wdrożenia — wersja ostateczna (v3)
Przygotowano: 13 września 2026 · Dokument roboczy — bez fragmentów kodu, wyłącznie decyzje,
fakty i liczby.
1. Ostateczna zasada agregacji i legalności
To jest fundament całego produktu, więc zapisujemy to jako regułę nadrzędną, ważniejszą niż
jakakolwiek decyzja techniczna poniżej.
1.1 Co Box pokazuje publicznie
• Tytuł artykułu/materiału.
• Miniaturka (obrazek).
• Nazwa źródła + data.
• Krótki cytat/lead (kilka-kilkanaście słów, zgodnie z prawem cytatu — art. 29 ustawy o
prawie autorskim: wolno przytaczać urywki utworów w zakresie uzasadnionym m.in.
prawem cytatu, wyjaśnianiem, nauczaniem).
• Link do oryginału, otwierany w nowej karcie — użytkownik zawsze trafia ostatecznie do
wydawcy, ruch wraca do źródła (dokładnie tak, jak w Google News czy dowolnym
agregatorze linków).
1.2 Co wie „nasze AI”, ale nigdy nie pokazuje
Pełna treść artykułu może zostać pobrana i przetworzona wewnętrznie (embeddingi,
rozumienie kontekstu, wykrywanie powiązań) — to potrzebne, żeby Dr. Spin wiedział, że dany
artykuł obala albo potwierdza jakąś tezę. Ale AI nigdy nie referuje ani nie cytuje z tej pełnej
treści więcej niż to, co i tak jest widoczne publicznie na Boxie. Odpowiedź Dr. Spina wygląda
zawsze jak: „na obalenie tej tezy: [link do Boxa X]” — bez własnej narracji, bez dodatkowego
cytowania.
Konsekwencja techniczna: warstwa API serwująca dane do frontendu musi na poziomie
zapytania zwracać tylko pola z listy 1.1 — pełna treść nie powinna być nawet teoretycznie
osiągalna przez publiczne endpointy, tylko przez wewnętrzny backend AI.
1.3 Źródła bez RSS/API — co się z nimi dzieje
Brak kanału RSS czy oficjalnego API u danej redakcji nie oznacza, że pomijamy ją w bazie.
Oznacza tylko, że metadane (tytuł, miniaturka, lead) trzeba pozyskać przez uprzejme,
zgodne z robots.txt pobranie strony — co i tak jest legalne, bo to co publikujemy dalej mieści
się w prawie cytatu, niezależnie od tego, czy wydawca udostępnił RSS.
Dla takich źródeł system automatycznie:
• dodaje Box na podstawie samych metadanych (tytuł/miniaturka/lead/link) — nic więcej nie
jest potrzebne do działania produktu,
• oznacza redakcję jako kandydata do „Agenta Kontaktowego” (patrz 1.4) — czyli
automatycznego procesu, który przygotowuje i kolejkuje do wysyłki (przez człowieka, nie
automatycznie) zapytanie o pełniejszy dostęp: RSS, API, archiwum, ewentualną
współpracę.
1.4 Agent Kontaktowy (nowy element planu)
Osobny, prosty proces w tle: dla każdego źródła bez RSS/API generuje gotowy szkic
wiadomości (kto, po co, jaki zakres dostępu, propozycja współpracy/wzajemnego linkowania)
i zapisuje go w kolejce „do wysłania”. Człowiek (Ty, na start) przegląda i wysyła ręcznie —
bez pełnej autonomii wysyłki, choćby po to, żeby nie wysłać czegoś nieadekwatnego do dużej
redakcji przez pomyłkę w automacie.
⚠ Dlaczego bez pełnej autonomii wysyłki
Automatyczne, masowe wysyłanie wiadomości do wielu redakcji naraz, bez przeglądu, to
prosta droga do tego, żeby zostać potraktowanym jak spam, a nie jak potencjalny partner.
Człowiek w pętli przed wysyłką kosztuje niewiele czasu, a chroni reputację marki na
starcie.
✓ To rozwiązuje wcześniejsze napięcie
„Zero obejść” dotyczy zabezpieczeń technicznych (robots.txt, limity, captcha) — nie
oznacza „nie dodawaj źródła bez RSS”. Cytowanie tytułu i miniaturki jest legalne
niezależnie od tego, czy wydawca ma RSS. Ta wersja planu godzi obie rzeczy: agregujemy
wszystko, pokazujemy tylko to, co wolno.
2. Architektura — ujęcie koncepcyjne
Bez zmian względem poprzedniej wersji w warstwie technicznej, z jednym nowym elementem
(Agent Kontaktowy):
• Source Registry — tabela sterująca (masz już gotową, 71 źródeł, z kolumnami prawnymi).
• Pipeline ingestu — discover URL → fetch (zgodnie z robots.txt) → extract → snapshot +
hash → zapis do bazy (pełna treść trafia TYLKO do warstwy wewnętrznej).
• Warstwa publiczna (API serwujące frontend) — zwraca wyłącznie pola cytowalne (1.1).
• RAG / Dr. Spin — Qdrant + embeddingi na pełnej treści (wewnętrznie), model odpowiada
wyłącznie linkami do Boxów jako dowodami.
• Agent Kontaktowy (nowy) — osobny, lekki proces: skanuje Source Registry pod kątem
źródeł bez RSS/API, generuje szkice wiadomości, zapisuje do kolejki „do wysłania przez
człowieka”.
• Append-only + wersjonowanie + SHA-256 — bez zmian, kluczowe dla wiarygodności
dowodowej.
3. Etapy rozwoju — zakres, technologia,
infrastruktura
Etap I — MVP
Zakres produktowy: redakcyjne nitki, Dr. Spin 1×/dzień, feed Boxów (cytat-only), reakcja + 1
komentarz na Box/nitkę, przycisk „zgłoś błąd”.
Technologia: Supabase (Postgres + Auth + Storage), 1 VPS + Docker
(worker/scheduler/redis), Next.js na Vercelu (lub ten sam VPS), Qdrant (RAG), model
open-weight przez Ollama do testowania promptów Dr. Spina, docelowo własne GPU do
produkcyjnego Dr. Spina.
Infrastruktura: 1 VPS (ingest), Supabase (managed), opcjonalnie wynajęta godzinowo
instancja GPU do testów RAG, zanim padnie decyzja o zakupie własnego sprzętu.
Orientacyjny koszt miesięczny: VPS 100–300 zł, Supabase (plan Pro) ok. 100–120 zł, domena
i drobne narzędzia ok. 50 zł, GPU wynajmowane wg zużycia (zmienne, płatność za czas
pracy).
Etap II
Zakres produktowy: UGC („Izba Przyjęć”), dwa widoki (News / Nitki), Weryfikator po URL,
alerty (in-app + web push), paywall (limity zapytań/eksport), pierwszy dashboard B2B, Agent
Kontaktowy w pełnej wersji.
Technologia: Web Push (service worker + klucze VAPID), kolejka alertów (Redis pub/sub albo
Supabase Realtime), bramka płatności (Stripe lub Przelewy24/PayU dla polskich kart), panel
B2B jako kolejny moduł tego samego Next.js.
Infrastruktura: drugi worker (redundancja, nie „obejście blokad”), CDN dla miniaturek (np.
Cloudflare), monitoring błędów i wydajności (Sentry, podstawowy Grafana/Prometheus).
Orientacyjny koszt miesięczny: 500–1 500 zł przy średniej skali ruchu, rosnąco wraz z liczbą
użytkowników i alertów.
Etap III
Zakres produktowy: własny RAG na pełnej bazie (Boxy + cytaty + rejestry + BIP + reklamy
polityczne z Meta Ad Library), automatyczne osie czasu z uzasadnieniem powiązań,
wyszukiwarka hybrydowa (słowa kluczowe + semantyka), produkt white-label /
licencjonowanie danych.
Technologia: dedykowany serwer/klaster GPU (własny lub kolokacja), pełny `bip-indexer` (ok.
20 tys. BIP-ów), rozbudowany silnik wyszukiwania (OpenSearch/Elasticsearch lub Qdrant na
większą skalę).
Infrastruktura: serwery GPU (zakup lub kolokacja), rozproszony ingest (kilka lokalizacji jako
redundancja i odporność na awarie — nie jako sposób na omijanie blokad redakcji), zespół
(redakcja, moderacja, sprzedaż B2B).
Orientacyjny koszt miesięczny: od kilku do kilkunastu tysięcy złotych przy własnym GPU
(sprzęt + amortyzacja + prąd), więcej przy rozliczeniu w chmurze GPU na żądanie.
4. Monetyzacja — modele i szacunki przychodu
Wszystkie liczby poniżej to szacunki oparte na typowych wskaźnikach dla podobnych
produktów (monitoring mediów, niszowe portale informacyjne, freemium w Polsce) — nie
prognozy finansowe. Rzeczywisty wynik zależy od jakości produktu, tempa budowania
społeczności i sprzedaży B2B.
4.1 Reklama / sponsorowane nitki i paski
Sprzedaż bezpośrednia (nie programmatic — unikamy w ten sposób ryzyka sporu z
wydawcami o to, że ich zacytowana treść „sprzedaje” reklamy komuś trzeciemu bez ich
zgody). Docelowo pojedynczy sponsorowany pasek/slot dziennie lub tygodniowo,
sprzedawany bezpośrednio markom, agencjom PR, think-tankom.
Skala ruchu (unikalni/mies.) Szacowana stawka za
slot/mies.
Szacowany przychód/mies.
Start (do 10 tys.) 0 – 1 500 zł 0 – 3 000 zł
Średnia (20–50 tys.) 3 000 – 8 000 zł 5 000 – 20 000 zł
Dojrzała (100 tys.+) 8 000 – 15 000 zł 15 000 – 40 000 zł
4.2 Dobrowolne wsparcie (Buy Me a Coffee / Patronite)
Typowa konwersja dla polskich niszowych mediów: 0,1–0,5% aktywnych czytelników, średnia
wpłata 10–20 zł/mies. Przy 20 000 aktywnych miesięcznie daje to 20–100 wspierających, czyli
ok. 200–2 000 zł/mies. Niewielki, ale stabilny strumień — dobry na pokrycie kosztów hostingu
na wczesnym etapie, mało realny jako główne źródło przychodu.
4.3 Konta płatne (limity zapytań, alerty, eksport)
Typowa konwersja freemium→paid dla narzędzi prosumer w Polsce: 1–3%. Cena orientacyjna
15–40 zł/mies.
Aktywni użytkownicy/mies. Płacący (1–3%) Przychód/mies. (15–40 zł)
20 000 200 – 600 3 000 – 24 000 zł
50 000 500 – 1 500 7 500 – 60 000 zł
100 000 1 000 – 3 000 15 000 – 120 000 zł
4.4 Dane analityczne / alerty dla agencji PR i marek (B2B)
Najbardziej dochodowy segment w tego typu produktach — analogicznie do polskich firm
monitoringu mediów (np. Brand24, Newspoint, IMM, Press-Service), gdzie ceny subskrypcji
zwykle mieszczą się w przedziale 300–3 000+ zł/mies. na klienta, zależnie od zakresu (liczba
monitorowanych haseł, alertów, raportów). Przewagą spin.clinic nad czystym monitoringiem
wzmianek może być właśnie sieć powiązań i fact-checking Dr. Spina — to unikalna wartość,
którą można wycenić wyżej niż standardowy monitoring.
Etap Liczba klientów B2B Przychód/mies.
Etap II (start sprzedaży) 5 – 20 5 000 – 40 000 zł
Etap III (dojrzały produkt) 20 – 80 20 000 – 150 000+ zł
4.5 Inne możliwe źródła
• API dla dziennikarzy śledczych / naukowców — płatne per-zapytanie albo subskrypcja
akademicka ze zniżką.
• Granty i dotacje — europejskie i krajowe programy przeciwdziałania dezinformacji oraz
wspierania fact-checkingu (np. European Media and Information Fund i podobne) — to nie
sprzedaż, ale realny kapitał na start, warty rozważenia równolegle do przychodu
komercyjnego.
• Biała etykieta (white-label) — licencjonowanie silnika agregacji/Dr. Spina innym redakcjom
lub samorządom (np. lokalna transparentność) — model licencji per wdrożenie.
⚠ Czego unikać
Reklama programmatic (np. Google Ads) bezpośrednio przy cytowanej treści innej redakcji
to ryzyko sporu — wydawca może argumentować, że jego treść „zarabia” u kogoś innego
bez zgody. Bezpieczniejsza jest sprzedaż bezpośrednia, gdzie kontrolujesz kontekst i
możesz jasno rozdzielić „to jest reklama” od „to jest cytat”.
5. Ryzyka i zgodność — wersja zaktualizowana
Model cytatu (tytuł + miniaturka + lead + link) istotnie obniża ryzyko prawnoautorskie w
porównaniu z wcześniejszą wersją planu (pełne teksty na widoku publicznym). Zostaje kilka
rzeczy do domknięcia:
• Prawo cytatu — upewnij się w regulaminie i w kodzie, że cytat jest rzeczywiście krótki i
wyraźnie oznaczony, a nie „streszczeniem” złożonym z kilku zdań, które oddaje całą
wartość tekstu (to już nie byłoby cytatem, tylko zamaskowaną reprodukcją).
• RODO — bez zmian: minimalizacja danych z KRS/CEIDG (tylko powiązania z podmiotami,
zero PESEL/adresów), jasne kryterium „kto jest osobą publiczną”, mechanizm sprostowań.
• Zniesławienie / Dr. Spin — bez zmian: próg confidence przed automatyczną publikacją,
kolejka redakcyjna poniżej progu, publiczny formularz sprostowania.
• Agent Kontaktowy — utrzymuj człowieka w pętli przed wysyłką wiadomości do redakcji
(patrz 1.4) oraz upewnij się, że wysyłka B2B (nie marketing masowy) mieści się w
zasadach ustawy o świadczeniu usług drogą elektroniczną.
⚠ Nadal jedyna rekomendacja „pilna”
Mimo że model cytatu jest znacznie bezpieczniejszy, warto go potwierdzić z prawnikiem od
prawa prasowego/autorskiego, zanim skala pobierania sięgnie dziesiątek tysięcy artykułów
dziennie — sama zasada jest dobra, ale wdrożenie (długość cytatu, sposób oznaczenia)
najlepiej zweryfikować raz, porządnie, na starcie.
6. Checklist — z uwzględnieniem Claude Code
• Import Source Registry do Supabase (masz gotowy plik CSV).
• RLS + reszta schematu core w Supabase.
• Z Claude Code podłączonym w VS Code: pisanie modułów ingestu krok po kroku, moduł
po module — zaczynając od Tier 0 (Sejm API), potem RSS-owe media, na końcu HTML bez
RSS + Agent Kontaktowy.
• Backfill Tier 0, potem Tier 1/2 w tempie z kolumny rate_limit_sekundy.
• Qdrant + pierwsze embeddingi Boxów (RAG pod Dr. Spina) — niezależnie od limitu
ChatGPT.
• Szkic regulaminu opisującego model cytatu — do przejrzenia przez prawnika przy
pierwszej okazji.
7. Podsumowanie
Ta wersja planu domyka główne ryzyko prawne z poprzedniej iteracji (pełne teksty
na widoku publicznym) przy zachowaniu pełnej funkcjonalności produktu — baza
wciąż agreguje wszystko, AI wciąż „wie” wszystko, zmienia się tylko to, co jest
pokazywane na zewnątrz. To jest różnica, która pozwala spać spokojnie i
jednocześnie nie traci nic z wartości produktu dla użytkownika
