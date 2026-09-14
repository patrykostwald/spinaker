# Kwalifikacja historycznego korpusu

## Cel

Stare rekordy pozostają przydatne jako mapa źródeł i chronologia. Nie są jednak automatycznie dopuszczone do przetwarzania tylko dlatego, że znalazły się w bazie przed wprowadzeniem wersjonowanej bramki dostępu.

Ten dokument opisuje kolejność wdrożenia. Nie jest opinią prawną i nie nadaje zgód wstecz.

## Zasada domyślna

Każdy materiał pozyskany przed bramką dostępu startuje jako `legacy_unreviewed`:

- publicznie może pokazać wyłącznie tytuł, datę, nazwę źródła i link;
- nie pokazuje fragmentu pełnej treści;
- nie trafia do OCR, embeddingów, RAG ani treningu;
- prywatny snapshot, jeśli istnieje, zostaje artefaktem dowodowym poza publicznym i AI-owym obiegiem.

Nowe materiały przechodzą wyłącznie przez aktualną `SourceAccessInstruction`. Starsza decyzja nie może zastąpić tej instrukcji dla nowego pobrania.

## Najmniejszy model decyzji

Pierwsza wersja powinna działać na poziomie źródła i zakresu czasu, a nie tworzyć od razu milionów indywidualnych wpisów.

`LegacyQualificationDecision` zapisuje:

- źródło oraz granicę czasu, do której obejmuje materiały historyczne;
- status metadanych: `quarantined` albo `citation_only`;
- status treści: `quarantined`, `rag_snippet` albo `full_corpus`;
- oddzielny, zawsze ostrożny status snapshotu;
- autora, czas, uzasadnienie i dowody decyzji;
- datę ponownego przeglądu oraz wersję decyzji.

Decyzja nie zmienia faktu pozyskania. Pochodzenie materiału pozostaje osobnym, niezmiennym zapisem: metoda, czas, znany adres źródła oraz — gdy istnieje — odniesienie do późniejszej instrukcji lub próby pobrania.

## Dopuszczalne użycie

| Stan | Publiczny wynik | Pełny tekst | AI / RAG / OCR / trening |
| --- | --- | --- | --- |
| `legacy_unreviewed` | tytuł, źródło, data, link | nie | nie |
| `citation_only` | tytuł, źródło, data, link | nie | nie |
| `rag_snippet` | link i ograniczony, uzasadniony cytat | wyłącznie zgodnie z decyzją | tylko embeddingi i krótki RAG |
| `full_corpus` | zgodnie z decyzją | tak | wyłącznie wyraźnie włączone użycia |
| `quarantined` | nie | nie | nie |

Snapshot historyczny pozostaje `dark_archive`: administrator może go wykorzystać do audytu pochodzenia, lecz sam snapshot nie odblokowuje OCR ani modelu AI.

## Kolejność wdrożenia

1. Dodać filtr fail-closed do wszystkich przyszłych zapytań pełnotekstowych i AI: legacy bez decyzji nie może wejść do wyniku ani promptu. Publiczna karta bez decyzji to wyłącznie tytuł, źródło, data i link — bez opisu, tagów oraz notatki dowodowej.
2. Dodać minimalne, wersjonowane decyzje źródłowe oraz metrykę pokrycia decyzjami.
3. Najpierw kwalifikować źródła urzędowe i własne materiały redakcyjne na podstawie udokumentowanego statusu.
4. Dla wydawców komercyjnych zachować co najmniej `citation_only`, dopóki dokumentacja lub zgoda nie pozwoli na węższe albo szersze użycie. Decyzja pełnotekstowa nie oznacza automatycznie zgody na trening AI; trening pozostaje osobnym, wyraźnym użyciem.
5. Backfill embeddingów i dalszych transformacji uruchamiać dopiero po filtrowaniu kwalifikacji; każda transformacja zapisuje wersję decyzji, na której się opiera.

## Testy blokujące wdrożenie

- legacy bez decyzji nie pojawia się w kontekście RAG;
- `citation_only` zwraca metadane i link, lecz nigdy body ani snippet;
- snapshot nie jest dostępny przez publiczne API i nie trafia do OCR;
- decyzja dla starego zakresu dat nie autoryzuje późniejszego pobierania;
- cofnięcie lub wygaśnięcie decyzji usuwa materiał z kolejnych przebiegów AI.

## Co świadomie odkładamy

Nie implementujemy teraz masowego backfillu milionów rekordów, OCR ani wektorów. Najpierw potrzebny jest filtr wykorzystania i mały, audytowalny model decyzji. Dzięki temu MVP może używać bezpiecznych metadanych i linków, a korpus rozwija się bez udawania zgód wstecz.

Indywidualne wyjątki pozostają dodatkiem dla pojedynczych wycofań lub korekt. Nie tworzymy ich automatycznie dla całej bazy. Cofnięcie decyzji źródłowej następuje przez dopisanie nowszej wersji, nigdy przez kasowanie poprzedniej decyzji ani materiału.
