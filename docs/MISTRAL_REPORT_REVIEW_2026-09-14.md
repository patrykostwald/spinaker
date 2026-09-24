# Recenzja raportu Mistral — 14 września 2026

## Decyzja

Raport potwierdza sens drugiego dostawcy i wymiennego adaptera, ale nie jest specyfikacją gotową do implementacji. Przyjmujemy kierunek: klasyfikacja metadanych, wybór kandydatów i osobny pilotaż embeddings. Odrzucamy elementy, które przenosiły deterministyczne zadania bazy lub harvestera do modelu.

## Potwierdzone w dokumentacji Mistral

- Endpoint UE to `https://api.eu.mistral.ai`; regionalne przetwarzanie ma dopłatę 10%.
- Regionalnie jedynym obsługiwanym narzędziem jest function calling. Agents, Batch i Files API nie są dostępne regionalnie.
- Dostępne modele trzeba pobierać przez `models.list` wykonane przeciw endpointowi UE. Nie wolno zakładać ich na podstawie listy globalnej.
- Oficjalny model embeddings to `mistral-embed` (1024 wymiary); dokumentacja wymienia też warianty 256 i 128. Nazwy `mistral-large-2407` oraz `mistral-embedding-384` z raportu są niepotwierdzone i nie wchodzą do konfiguracji.
- Structured Outputs istnieją globalnie, lecz ich działanie z wybranym modelem na endpointzie UE musi potwierdzić krótki test.

Źródła: https://docs.mistral.ai/inference/regional-inference, https://docs.mistral.ai/api/endpoint/embeddings, https://docs.mistral.ai/studio/conversations/structured-output/custom

## Przyjęte elementy

- Jeden kontrakt domenowy dla dostawców i osobne implementacje transportu.
- Ścisła walidacja odpowiedzi i przyjmowanie wyłącznie ID przekazanych kandydatów.
- Brak bezpośredniego zapisu modelu do produkcji.
- Rejestrowanie endpointu, modelu, request ID, czasu, statusu i rzeczywiście zwróconego zużycia bez promptów, sekretów i treści odpowiedzi.
- Porównanie obu dostawców na identycznym, zamrożonym zestawie ocenionym przez redakcję.
- Natychmiastowe zatrzymanie przy wycieku danych, nieautoryzowanej mutacji lub utracie kontroli kosztu.

## Korekty obowiązkowe

1. Model wybiera trafne ID. Kod sortuje wybrane rekordy po dacie. Chronologia nie jest zadaniem AI.
2. Normalizacja URL, sprawdzanie 404, deduplikacja, parsowanie dat, czyszczenie HTML, limity dat i kontrola allowlisty należą do harvestera, walidatora oraz bazy.
3. Nigdy nie skracamy ani nie poprawiamy źródłowego tytułu. Możemy przechowywać osobne pole prezentacyjne, jeśli zostanie świadomie dodane.
4. Brak typu pozostaje `unknown`/do klasyfikacji. Nie zamieniamy go domyślnie na artykuł.
5. Źródło instytucjonalne nie otrzymuje automatycznie wyższego rankingu. Jest źródłem pierwotnym dla własnych działań i twierdzeń, ale nie neutralnym arbitrem.
6. Wynik modelu nie jest procentem prawdy ani publicznym `confidence`. Wewnętrzne score służy tylko do rankingu i wymaga kalibracji.
7. Uzasadnienie tekstowe `reason` nie jest wymagane w MVP. Wystarczą wybrane ID, opcjonalne jawne kody sygnałów i ostrzeżenia. Ogranicza to koszt oraz ryzyko dopisywania faktów.
8. Nie stosujemy automatycznego fallbacku po płatnej próbie. Jedna próba zużywa budżet; operator może świadomie uruchomić drugiego dostawcę.
9. Klucz API nie należy do obiektu konfiguracji, który może trafić do repr/logów. Pobiera go warstwa transportowa z sekretu środowiskowego.
10. Embeddings mają osobny interfejs, wersję modelu, wymiar i politykę migracji. Zmiana modelu oznacza nową przestrzeń wektorową i kontrolowany re-embedding.

## Poprawione metryki

- Klasyfikacja: precision, recall i F1 dla kontrolowanej taksonomii oraz odsetek poprawnych odmów.
- Selekcja nitki: Recall@15, Precision@15, nDCG@15, pokrycie odrębnych wydarzeń i ocena redaktora.
- Stabilność: zgodność ze schematem, brak obcych ID, powtarzalność na identycznym wejściu.
- Embeddings: Recall@k/MRR na ocenionych parach i trudnych negatywach. Sam próg cosine similarity nie mierzy jakości wyszukiwarki.
- Operacyjne: p50/p95 czasu, błędy według rodzaju, rzeczywiste tokeny i koszt na zaakceptowany wynik.

Progi jakości ustalimy po ręcznym baseline, zamiast przyjmować arbitralne 90%, 0,85 podobieństwa lub 1 sekundę. Budżet pilotażu będzie małym limitem liczby prób i kwoty, nie domyślnym limitem 100 USD.

## Rzeczywista lokalizacja zmian

Raport podał nieistniejące ścieżki. Obecna integracja znajduje się w `backend/news/draft.py`, `backend/news/ai_research.py` i `backend/news/ai_research_stream.py`; ustawienia w `backend/config/settings.py`; audyt w `backend/news/models.py`.

Pierwszy patch powinien wyodrębnić provider-neutralny kontrakt selekcji z `backend/news/draft.py`, zachowując obecne zachowanie OpenAI i brak automatycznych ponowień. Dopiero następny patch doda transport Mistral za flagą domyślnie wyłączoną. Embeddings będą osobnym etapem po sprawdzeniu schematu pgvector i kosztu migracji.

## Odpowiedzi na pytania Mistrala

1. Kontrolowana taksonomia istnieje częściowo i wymaga osobnego przeglądu przed automatyczną klasyfikacją. Model może zwracać tylko dozwolone identyfikatory kategorii oraz `abstain`.
2. Allowlista jest dynamicznym widokiem aktywnych, zatwierdzonych źródeł; zmiany są wersjonowane i audytowane.
3. Limit tekstu wynika z konkretnego modelu i polityki prawnej. Dla MVP embeddings budujemy deterministycznie z zatwierdzonych pól metadanych, nie z dowolnego pełnego tekstu.
4. `reason` pomijamy w MVP. Dr Spin nie musi tworzyć argumentacji, aby wybrać boxy.
5. Cosine similarity nie wystarcza; użyjemy Recall@k/MRR na ocenionym zbiorze.

## Następny krok

Bez klucza i płatnych wywołań można teraz przygotować kontrakt adaptera oraz testy zachowujące obecne działanie OpenAI. Test połączenia Mistral nastąpi dopiero po utworzeniu krótkotrwałego klucza, sprawdzeniu `models.list` na endpointzie UE oraz ustawieniu twardego limitu prób.
