# Prywatna ekstrakcja tekstu ze snapshotów

Pipeline tworzy prywatny, wersjonowany rekord `EvidenceTextExtraction`
powiązany jednocześnie ze snapshotem i jego boxem (`Article`). Nie ma endpointu
publicznego, automatycznego zadania ani podłączenia do procesu zbierania.

Jest domyślnie wyłączony. Pojedyncze wywołanie wymaga ustawienia
`EVIDENCE_TEXT_EXTRACTION_ENABLED=true`. Samo ustawienie flagi nie uruchamia
przetwarzania masowego. Migrację należy zastosować osobno w zaplanowanym oknie;
ten moduł nie uruchamia migracji ani OCR na aktywnej bazie.

Przetwarzane są wyłącznie snapshoty ze statusem zgody `allowed`, których
`allowed_uses` zawiera osobny zakres `text_extraction`. Sama zgoda na zapis
prywatnego dowodu nie zezwala na ekstrakcję, RAG ani trening. Osobne dostępne
zakresy to `text_extraction`, `rag` i `model_training`; każdy musi być nadany
jawnie. Statusy `restricted`, `unknown` i `denied` nie uprawniają do analizy. HTML jest
przetwarzany deterministycznie lokalnym parserem: skrypty, style, szablony i SVG
są pomijane, a odstępy normalizowane. Obrazy i PDF-y kierowane są do lokalnego
OCR; HTML nigdy nie trafia do OCR. Nie ma wywołań zewnętrznego AI.

OCR jest opcjonalny. Obrazy wymagają Pillow, `pytesseract` i lokalnego programu
Tesseract. PDF-y dodatkowo wymagają PyMuPDF. Brak tych składników nie zatrzymuje
procesu: rekord otrzymuje status `failed` i czytelny błąd. Instalacja zależności
nie jest częścią wdrożenia bazowego.

Rekord zapisuje metodę, wersję pipeline'u i silnika, hash wejścia i tekstu,
status, język, błąd oraz daty. Unikalność snapshot + wersja pipeline'u + hash
wejścia zapewnia idempotencję. Ponowne przetworzenie zmienionym algorytmem wymaga
nowej wersji pipeline'u, dzięki czemu starszy wynik pozostaje audytowalny.

Migracja nadaje istniejącym snapshotom `allowed_uses=[]`. Zapewnia to zgodność
schematu bez dorozumianej zgody: stary rekord pozostaje niedostępny dla
ekstrakcji, dopóki jego zakres nie zostanie jawnie zweryfikowany i uzupełniony.

Tekst jest prywatnym materiałem roboczym do późniejszego dzielenia i indeksacji.
Przed produkcją należy objąć model tymi samymi kontrolami dostępu, retencji i
usuwania co prywatne artefakty snapshotów.
