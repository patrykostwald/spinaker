# Kontrakty redakcyjnych adapterów AI

`news.ai_editorial` zawiera lokalne kontrakty wejść/wyjść, walidację i
deterministyczne fake providery. `news.ai_editorial_adapters` zawiera opcjonalne
transporty HTTP dla NVIDIA NIM i Groq. Nie ma zapisu do bazy ani ścieżki
publikacji.

## Bramka danych

Adapter przyjmuje tylko jawnie zbudowany `EvidencePacket`. Rekord ma publiczny
URL, źródło, datę, krótki fragment i cytat. Kontrakt nie zawiera binariów
snapshotów, kluczy prywatnego storage ani pełnego tekstu ekstrakcji.

Materiał pochodzący ze snapshotu wymaga statusu zgody `allowed` oraz
`allowed_uses` zawierającego `rag`. Materiał bez snapshotu wymaga jawnej zgody
źródła na `ai_draft_metadata`. Brak któregoś warunku kończy się błędem przed
wywołaniem adaptera.

## Adaptery opt-in

NIM jest dostępny tylko, gdy `NIM_ENABLED=true` oraz są ustawione klucz, oba
modele i `NIM_RERANK_URL`. Groq jest dostępny tylko, gdy
`GROQ_EDITORIAL_ENABLED=true` oraz są ustawione klucz i model. Brak któregokolwiek
warunku kończy działanie **przed** próbą sieciową. Nie ma automatycznego fallbacku.

NIM dostaje do embeddingów i rerankingu wyłącznie źródło, datę i krótki fragment;
nie otrzymuje URL-i cytatów ani cytatów. Groq dostaje tylko dozwolony pakiet
cytacyjny: identyfikator, publiczny URL, źródło, datę, fragment i cytat. Żaden
adapter nie otrzymuje snapshotów, plików, ścieżek storage ani pełnego tekstu.

Groq wymusza JSON Schema, a odpowiedź jest dodatkowo parsowana restrykcyjnie i
przechodzi `validate_proposal`. Błędna odpowiedź, obcy identyfikator, URL lub
status inny niż `pending_review` są odrzucane. Wynik pozostaje obiektem w pamięci:
osobny, późniejszy serwis musi zdecydować o zapisie szkicu.

Walidator dopuszcza wyłącznie status `pending_review`. W szczególności nie
pozwala na publikację, nieznany identyfikator materiału, brak zgodnego URL-a
cytatu ani inną wersję schematu.
