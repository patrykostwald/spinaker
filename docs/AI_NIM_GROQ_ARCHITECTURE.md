# Dr Spin — architektura asystenta redakcyjnego (NIM + Groq)

## Decyzja

AI jest osobną, wewnętrzną warstwą redakcyjną nad materiałami zapisanymi już w
Bazie. NVIDIA NIM może grupować i porządkować kandydatów, a Groq przygotować
ustrukturyzowany szkic powiązań lub nitki kontekstowej. Model nie jest źródłem
treści widocznej w portalu, nie pobiera materiałów z internetu i nie zastępuje
importerów ani Bazy. Istniejące integracje AI pozostają wyłączone, dopóki nie
przejdziemy przez etapy opisane niżej.

W komunikacji publicznej używamy nazwy: **„Dr Spin — asystent redakcyjny oparty
na modelach open-weight”**. Nie deklarujemy, że jest to własny model ani że AI
samodzielnie ustala prawdę.

## Co robi system

System może pomóc redakcji odnaleźć powiązane materiały w Bazie, pogrupować je
wokół tematu i ułożyć szkic nitki kontekstowej. Każda propozycja zawiera
identyfikatory materiałów, linki do oryginałów, podstawę powiązania, braki
danych i poziom pokrycia źródłowego.

System nie publikuje nitki, nie oznacza wypowiedzi jako „kłamstwo” ani „spin” i
nie zmienia publicznej Bazy. Wynik trafia wyłącznie do kolejki szkiców
redakcyjnych. Redaktor wybiera materiały, poprawia kolejność oraz podejmuje
decyzję o publikacji.

## Bramka danych i zgód

Przed każdym przetworzeniem działa jedna bramka kwalifikacji materiału:

1. Minimalne metadane publicznego materiału (tytuł, źródło, data, kategoria,
   URL) mogą służyć do katalogowania.
2. Snapshot, pełny tekst i OCR są niedostępne domyślnie.
3. Snapshot może zostać lokalnie wyekstrahowany wyłącznie, gdy ma status
   `allowed` oraz jawny zakres `text_extraction`.
4. Fragment z ekstrakcji może wejść do indeksu semantycznego wyłącznie, gdy ma
   dodatkowy, jawny zakres `rag`.
5. `model_training` jest osobną zgodą; nie wynika z `rag` i nie jest częścią
   pilotażu.
6. Cofnięcie zgody wyklucza materiał z kolejnych zadań, indeksu i wyników.

Żadne prywatne snapshoty, dane kont użytkowników, adresy e-mail ani prywatna
aktywność nie mogą trafić do NIM, Groq ani innego zewnętrznego dostawcy.

## Przepływ danych

1. **Wybór z Bazy:** zadanie dostaje wyłącznie rekordy już zapisane w Bazie:
   ich identyfikator, źródło, datę, kategorię, link do oryginału i dozwolony
   fragment.
2. **Kwalifikacja:** bramka sprawdza, czy krótki fragment może zostać użyty
   zgodnie z zasadami danego źródła.
3. **Indeks opcjonalny:** PostgreSQL z `pgvector` przechowuje embedding, hash wejścia,
   wersję modelu, status zgody i datę indeksacji. Jeden rekord indeksu można
   usunąć albo przebudować bez zmiany oryginału.
4. **Wyszukiwanie:** zwykłe wyszukiwanie po haśle pozostaje podstawą. Opcjonalnie
   NIM tworzy embedding zapytania; lokalny indeks zwraca kandydatów, a reranker
   porządkuje ich według trafności.
5. **Szkic nitki:** Groq dostaje tylko wybrane, cytowalne rekordy z Bazy i zwraca JSON
   zgodny z wersjonowanym schematem. Walidator odrzuca odpowiedź bez źródeł,
   nieprawidłowymi identyfikatorami lub nieznanym polem.
6. **Przegląd:** redaktor akceptuje, odrzuca albo poprawia propozycję. Dopiero
   osobna czynność redakcyjna może stworzyć publiczną nitkę.

## Trzy widoki X

- **Przekaz obozu rządzącego:** grupuje podobne publiczne posty wyłącznie z
  zatwierdzonych kont tej kolekcji.
- **Przekaz opozycji:** działa tak samo dla kont opozycyjnych.
- **Kandydaci Dr Spina:** wyszukuje wypowiedzi warte sprawdzenia z obu zbiorów,
  wskazując cytat, materiały za/przeciw oraz luki dowodowe.

Wszystkie trzy korzystają tylko z zapisanych, publicznych postów X i już
dopuszczonych materiałów z Bazy. Nie wykonują automatycznej publikacji ani nie
wydają wyroku o osobie.

## Bezpieczeństwo kosztów i działania

- Dostawcy są obsługiwani przez wymienne adaptery.
- Brak automatycznego przełączania NIM ↔ Groq ↔ inny dostawca. Awaria kończy
  zadanie czytelnym statusem, bez nieoczekiwanych kosztów i egressu danych.
- Klucze pozostają wyłącznie po stronie serwera, poza Git i przeglądarką.
- Limity: maksymalny koszt dzienny i miesięczny, maksymalna liczba rekordów na
  zadanie, limit znaków fragmentu, limit ponowień oraz ręczne włączenie każdego
  adaptera.
- Do dostawcy trafia najmniejszy konieczny zestaw danych; oryginalny snapshot
  i pełny tekst pozostają lokalne.

## Audytowalność

Każde zadanie AI zapisuje co najmniej: identyfikator zadania, cel, dostawcę,
model, wersję promptu i schematu, hash wejścia, identyfikatory materiałów,
status zgód, czas, liczbę tokenów (jeżeli dostawca zwraca), szacowany koszt,
wynik walidacji oraz decyzję i korektę redaktora. Nie zapisujemy kluczy ani
niepotrzebnej pełnej treści wejściowej.

## Etapy wdrożenia

1. **Kontrakty bez sieci:** adaptery, typy wejść/wyjść, JSON Schema, testowe
   fałszywe implementacje i walidator. Ten etap można zlecić Claude Code.
2. **Kwalifikacja danych:** jeden serwis bramki zgód, testy cofnięcia zgody i
   komplet audytowy. Bez migracji masowych i bez egressu.
3. **Lokalna ekstrakcja:** wykorzystanie istniejącego pipeline'u wyłącznie dla
   ręcznie dopuszczonych snapshotów.
4. **Indeks pilotażowy:** zaplanowana migracja `pgvector`, indeks 30–50
   materiałów, indeksowanie ręcznie uruchamiane.
5. **NIM:** jest adapter embeddingów/rerankingu za wyłączoną domyślnie flagą;
   przed włączeniem potrzebuje testu na danych publicznych, limitu kosztu i
   obserwacji wyników.
6. **Groq:** jest adapter szkicu JSON za wyłączoną domyślnie flagą; odpowiedź
   przechodzi ścisłą walidację i nie ma jeszcze ścieżki zapisu ani publikacji.
7. **Ocena:** porównanie trafności, cytowań, błędów, czasu i kosztu. Dopiero po
   akceptacji redakcji można zwiększać zakres materiałów.

## Lista dla właściciela: konta i klucze

Nie zakładaj kluczy przed etapem 4, chyba że chcesz wykonać wyłącznie test
połączenia na sztucznych danych.

1. Załóż konto w NVIDIA API Catalog / NIM i konto w Groq Console.
2. Włącz rozliczenia oraz mały limit wydatków po stronie każdego dostawcy.
3. Utwórz po jednym kluczu serwerowym: osobno dla NIM i Groq.
4. Zapisz je tylko w lokalnym `.env` lub późniejszym managerze sekretów; nigdy
   w czacie, kodzie, zrzucie ekranu ani repozytorium.
5. Ustaw adaptery jako wyłączone do chwili wdrożenia etapu 5/6 i pozytywnego
   testu pilotażowego.
6. Przed włączeniem upewnij się, że istnieją limity kosztów, dziennik zadań i
   procedura unieważnienia klucza.

## Kryterium gotowości pilotażu

Pilotaż jest gotowy, gdy na 30–50 ręcznie wybranych materiałach redakcja może
sprawdzić wszystkie cytaty, żaden niedopuszczony snapshot nie został użyty,
każdy szkic ma decyzję człowieka, a koszt i jakość są zmierzone.
