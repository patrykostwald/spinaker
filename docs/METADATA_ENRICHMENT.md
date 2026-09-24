# Uzupełnianie brakujących miniaturek

Importer archiwum wykorzystuje metadane już pobranej strony, aby uzupełnić pusty adres miniatury w automatycznym rekordzie RSS/archiwum. Nie wykonuje z tego powodu drugiego pobrania strony. Przyjmuje adres wskazany przez `og:image` lub `twitter:image`; nie tworzy obrazu.

Warunki: ten sam URL publikacji, pusta miniatura, rekord automatyczny, brak zatwierdzonej klasyfikacji redakcyjnej. Tytuł, opis, data, kategoria i wcześniejsze dowody pozostają zachowane. Obecna miniatura nigdy nie jest nadpisywana. Zmiana z blokadą rekordu zapisuje w `evidence_note` czas odczytu, rodzaj pola wydawcy, adres miniatury, URL publikacji i SHA-256 odpowiedzi. Skrót nie oznacza, że przechowujemy pełny dokument tej odpowiedzi.

`python manage.py queue_thumbnail_backfill --limit 50` kolejkowuje ograniczoną partię starszych braków. To lokalna operacja bez pobierania stron. Trwały kursor przechodzi przez rekordy raz, bez zapętlania niedostępnych zdjęć. Ukończone zadanie może wrócić do kolejki z priorytetem10, niższym niż100 dla URL wyszukiwanych. Istniejące zadania pending/running/error zachowują lease i backoff. Roboty, odstępy domen oraz limit współbieżności pozostają wspólne z archiwum; pierwszeństwo dotyczy co czwartego slotu.

Nie każdy materiał zawiera miniaturę. Pustego pola nie traktujemy jako obowiązku znalezienia dowolnego pasującego zdjęcia. Pierwsza partia9września2026: rozpatrzono50 rekordów, zakolejkowano35, pozostałe15 miały już zadania.
