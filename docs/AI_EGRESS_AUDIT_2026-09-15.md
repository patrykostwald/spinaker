# Audyt egressu AI i publicznego API — 15 września 2026

## Zakres

Audyt obejmuje bieżący kod lokalnego worktree. Nie wykonano requestów ani nie użyto sekretów.

## Potwierdzone wyjścia

### Szkic redakcyjny

`news.draft.EditorialDraftView` przekazuje przez `news.selection_provider` do OpenAI albo Mistral EU wyłącznie listę kandydatów z polami:

- `id`;
- `title` (maks. 500 znaków);
- nazwa źródła;
- kategoria;
- data publikacji.

Nie przekazuje `description`, `evidence_note`, `ArticleContent.text`, snapshotu, obrazu ani pełnego URL artykułu. Dostęp jest wyłącznie dla redakcji i wynik wymaga kontroli redakcyjnej.

### Dr Spin z web search

`news.ai_research` przekazuje do OpenAI temat albo podaną przez użytkownika wypowiedź. Dostawca sam wykonuje ograniczone web search w skonfigurowanych domenach. Funkcja nie przekazuje zawartości `ArticleContent.text` z lokalnej bazy.

Po odpowiedzi funkcja może zwrócić już zapisane boxy odpowiadające znalezionym URL-om. Przez `ArticleSerializer` odpowiedź publiczna zawiera m.in. tytuł, URL, opis, tagi oraz `evidence_note`; nie zawiera pełnej treści `ArticleContent.text` ani snapshotu.

### Publiczne listy i kontekst

`news.portal` korzysta z `ArticleSerializer`, dlatego aktualnie publikuje opis i notatkę dowodową dla wszystkich widocznych boxów. Nie używa pełnej treści `ArticleContent.text`.

## Wniosek

Najpierw trzeba dodać kwalifikację legacy i jeden filtr użycia, a dopiero później dopinać go do trzech granic:

1. kandydaci wysyłani do szkicu redakcyjnego;
2. wyniki zwracane przez Dr Spin po dopasowaniu do zapisanych boxów;
3. publiczny serializer i publiczne listy/kontekst.

Domyślnie legacy bez decyzji może pozostać `citation_only`: tytuł, źródło, data i link. Nie powinien wysyłać opisu, notatki dowodowej ani żadnej treści do zewnętrznego AI. Pełny tekst oraz snapshot pozostają wyłączone.

## Testy wymagane przed zmianą

- legacy bez decyzji nie jest kandydatem szkicu redakcyjnego i nie powoduje wywołania dostawcy;
- legacy `citation_only` ma w publicznym wyniku tylko minimalne metadane;
- legacy bez decyzji nie trafia do timeline zwracanego przez Dr Spin;
- `ArticleContent.text` i snapshot nie pojawiają się w payloadach AI ani publicznym API;
- decyzja cofnięta lub wygasła działa jak odmowa w kolejnym żądaniu.
