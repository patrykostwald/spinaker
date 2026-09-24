# Instrukcja — NVIDIA NIM i Groq

Ta instrukcja służy do bezpiecznego skonfigurowania dwóch dostawców dla Dr
Spin. Adaptery są już w backendzie, ale pozostają wyłączone, dopóki redakcja
nie uruchomi osobnego pilotażu.

- NVIDIA NIM: embeddingi i reranking materiałów.
- Groq: redakcyjna propozycja JSON, zawsze jako szkic do oceny człowieka.

Żaden dostawca nie może otrzymać prywatnego snapshotu, pełnego tekstu,
danych użytkownika ani sekretów. Do przyszłego zapytania trafia wyłącznie
zakwalifikowany pakiet cytowalnych, publicznych fragmentów.

## 1. NVIDIA NIM

1. Otwórz [NVIDIA API Catalog](https://build.nvidia.com/) i załóż konto lub
   zaloguj się.
2. Wybierz **API Keys** i utwórz nowy klucz serwerowy.
3. Nazwij go `spin-clinic-nim-server`.
4. Nie wybieraj modelu ani płatnego planu na zapas. Model i limit ustalimy po
   wdrożeniu adaptera oraz pilotażu na 30–50 materiałach.
5. Skopiuj klucz tylko do menedżera haseł. Nie wklejaj go do czatu, dokumentu,
   commita ani kodu frontendu.

NIM udostępnia modele przez API; wybrane modele mogą też później zostać
uruchomione lokalnie jako kontenery, gdy projekt będzie na to gotowy.
[Dokumentacja NVIDIA NIM](https://docs.api.nvidia.com/nim/docs/overview)

## 2. Groq

1. Otwórz [Groq Console](https://console.groq.com/) i załóż konto lub zaloguj
   się.
2. Wejdź do projektu przeznaczonego dla spin.clinic albo utwórz go w konsoli.
3. Utwórz klucz API o nazwie `spin-clinic-editorial-server`.
4. Skopiuj go tylko do menedżera haseł. Groq zaleca przekazywanie klucza przez
   zmienną środowiskową, co ogranicza ryzyko zapisania go w kodzie.
5. Sprawdź w konsoli bieżące limity i ewentualne ustawienia wydatków. Nie
   zakładaj, że bezpłatny lub płatny limit ma stałą wartość — warunki sprawdza
   się w panelu dostawcy przed użyciem produkcyjnym.

[Quickstart Groq](https://console.groq.com/docs/quickstart) ·
[limity wydatków Groq](https://console.groq.com/docs/spend-limits)

## 3. Konfiguracja lokalna

Gdy adaptery NIM i Groq przejdą przegląd kodu oraz testy, dodamy do lokalnego
pliku `.env` wartości w tym układzie:

```env
NIM_ENABLED=false
NIM_API_KEY=
NIM_EMBEDDING_MODEL=baai/bge-m3
NIM_EMBEDDING_URL=https://integrate.api.nvidia.com/v1/embeddings
NIM_RERANK_MODEL=nvidia/rerank-qa-mistral-4b
NIM_RERANK_URL=https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking
GROQ_EDITORIAL_ENABLED=false
GROQ_API_KEY=
GROQ_EDITORIAL_MODEL=openai/gpt-oss-20b
GROQ_EDITORIAL_URL=https://api.groq.com/openai/v1/chat/completions
```

1. Wklej każdy klucz wyłącznie po znaku `=` w lokalnym `.env`.
2. Ustaw wskazane nazwy modeli i adresy, a oba przełączniki zostaw jako
   `false`.
3. Ustaw limity wydatków bezpośrednio w panelu każdego dostawcy przed pierwszym testem.
4. Zapisz plik i zrestartuj wyłącznie backend zgodnie z instrukcją wdrożenia.
5. Wykonaj test zdrowia adaptera na jednym przygotowanym, publicznym pakiecie.
6. Sprawdź log: model ma utworzyć tylko szkic `pending_review`, bez publikacji.
7. Dopiero po ręcznym przeglądzie pierwszych wyników włącz jeden adapter na
   pilotaż. Nie włączaj automatycznego fallbacku między dostawcami.

## 4. Warunek startu pilotażu

Przed pierwszym prawdziwym wywołaniem muszą być spełnione wszystkie warunki:

- adaptery są wdrożone i przetestowane;
- bramka zgód dopuszcza każdy materiał do RAG;
- klucze są wyłącznie po stronie serwera;
- limity kosztu są ustawione;
- wynik jest walidowany jako szkic redakcyjny;
- redaktor ręcznie zatwierdza każdą publikację.

Szczegóły przepływu danych i granic redakcyjnych opisuje
[architektura NIM + Groq](AI_NIM_GROQ_ARCHITECTURE.md).
