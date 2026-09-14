# Pipeline rozumienia danych spin.clinic

Stan: projekt wykonawczy, 14 września 2026. Publiczne boxy, prywatne materiały źródłowe i wyniki AI pozostają oddzielnymi warstwami.

## Zasada

Wyszukiwarka, Dr Spin i przyszły własny silnik muszą umieć wskazać, z którego boxa, źródła i konkretnego fragmentu pochodzi każdy element kontekstu. Sam tytuł oraz URL nie wystarczają do analizy treści. Surowy OCR także nie jest jeszcze wiedzą: wymaga wersjonowania, kontroli jakości i zachowania związku z oryginałem.

## Przepływ jednego materiału

1. **Źródło i prawa.** Rejestr określa osobno możliwość pobrania metadanych, pełnej treści, wykonania prywatnej kopii, analizy/RAG i treningu. Brak zgody na jeden cel nie jest zgodą na pozostałe.
2. **Box.** Powstaje kanoniczny rekord publikacji z wydawcą, URL, canonical URL, datą publikacji, datą odkrycia i metodą pobrania. Identyczne publikacje różnych wydawców pozostają oddzielnymi boxami.
3. **Prywatny oryginał.** Jeśli zakres praw na to pozwala, zapisujemy oryginalny HTML, PDF, obraz lub plik audio/wideo w prywatnym magazynie. Screenshot jest uzupełnieniem dowodowym, a nie preferowanym zamiennikiem dostępnego oryginału.
4. **Ekstrakcja.** HTML przechodzi deterministyczne wydobycie tekstu; tekstowe PDF-y używają warstwy tekstowej; OCR uruchamia się dla skanów i obrazów; audio/wideo w późniejszym etapie otrzymuje transkrypcję.
5. **Wersjonowany wynik.** Każdy wynik ma identyfikator boxa i snapshotu, metodę oraz wersję narzędzia, hash wejścia i wyniku, język, status, jakość, ostrzeżenia i czas wykonania. Ponowne uruchomienie nie nadpisuje bez śladu poprzedniej wersji.
6. **Segmenty.** Zweryfikowany tekst dzielimy według struktury dokumentu. Każdy fragment zachowuje kolejność, nagłówek, pozycję w oryginale oraz dokładne pochodzenie. Cytat Dr Spina musi wskazać konkretny fragment.
7. **Wzbogacenie.** Oddzielne, wersjonowane automaty wykrywają encje, cytaty, dokumenty, wydarzenia, relacje i podobieństwo publikacji. Wynik modelu nie zmienia tekstu źródłowego.
8. **Indeksy.** Klasyczny indeks pełnotekstowy, indeks encji i indeks semantyczny powstają z tych samych zatwierdzonych fragmentów. Usunięcie lub wygaśnięcie uprawnienia wycofuje właściwe kopie i indeksy.
9. **Kontrola jakości.** Losowe próbki i reguły mierzą brak tekstu, błędne daty, zmianę parsera, duplikaty, jakość OCR oraz zgodność cytatu z oryginałem.

## Deduplikacja i podobieństwo

- Ten sam canonical URL w obrębie jednego źródła nie tworzy kolejnego boxa.
- Parametry śledzące, mobilne warianty i techniczne aliasy jednego materiału łączymy z jednym boxem.
- Taka sama lub niemal taka sama treść opublikowana przez różne źródła pozostaje w oddzielnych boxach. System zapisuje relację podobieństwa i chronologię publikacji.
- Nie zakładamy automatycznie, kto był pierwotnym autorem. Takie twierdzenie wymaga dat, dowodów i ewentualnego przeglądu redakcyjnego.

## Źródła bez dozwolonej metody

Po sprawdzeniu API, RSS, mapy strony, oficjalnego eksportu i dozwolonego HTML źródło bez odpowiedniej podstawy trafia do rejestru kontaktów. Rejestr grupuje artykuły według rzeczywistego wydawcy, zapisuje potrzebny zakres zgody i przygotowuje wiadomość oraz reprezentatywną listę URL. Wysyłkę zatwierdza człowiek; brak odpowiedzi nie oznacza zgody.

## Kolejność automatów

1. pochodzenie, zgody i prywatne snapshoty;
2. ekstrakcja tekstu/OCR oraz wersjonowanie;
3. kontrola jakości i monitor dryfu parserów;
4. kanonizacja URL i relacje podobieństwa między źródłami;
5. segmentacja, cytaty i encje;
6. osie wydarzeń oraz nitki;
7. indeks pełnotekstowy, encyjny i semantyczny;
8. audyt próbek i zbiór ewaluacyjny;
9. RAG dla wyszukiwarki i Dr Spina;
10. decyzja o dostrajaniu lub treningu własnego modelu dopiero po pomiarze jakości i praw do tego zastosowania.

## Informacja publiczna „Jak działamy”

Strona wyjaśnia zwięźle, że korzystamy z oficjalnych API, RSS, map witryn i dozwolonego pobierania stron; respektujemy ograniczenia wydawców; zapisujemy pochodzenie i czas pozyskania; oddzielamy materiał źródłowy od interpretacji AI; pokazujemy zakres pokrycia, niepewność i korekty. Nie ujawniamy zabezpieczeń ani szczegółów umożliwiających obchodzenie limitów.
