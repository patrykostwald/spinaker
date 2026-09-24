# Sprawy właściciela — na końcu przygotowań

Portal lokalny: http://localhost:3000. Panel redakcji: /editor. Dane dostępu są w .local/admin-login.txt; nie przesyłaj haseł ani kluczy w rozmowie.

1. Publiczny serwer: konto z możliwością uruchomienia Docker/Linux, PostgreSQL, Redis, API, frontendu oraz procesów worker/Beat. Obecny pakiet home.pl wymaga sprawdzenia możliwości; nie usuwaj go ani nie przenoś domeny przed gotowością nowego środowiska. Domena może zostać u obecnego rejestratora, a DNS wskazywać nowy serwer. Konfigurację docelową sprawdzimy na zakupionym koncie przed publikacją.
2. Domena startowa: przeszlosc.today albo spin.clinic. Oba warianty korzystają ze wspólnego kodu i jednej bazy. Nie trzeba wdrażać dwóch portali.
3. YouTube: projekt Google Cloud, włączone YouTube Data API v3, klucz serwerowy. Ustaw YOUTUBE_API_KEY i YOUTUBE_ENABLED=true w środowisku backendu; ogranicz klucz do tej usługi oraz adresu serwera. Limit aplikacji to domyślnie50 zewnętrznych zapytań dziennie (YOUTUBE_DAILY_REQUEST_LIMIT), odpowiedzi są buforowane. Integracja nie pobiera filmów ani transkrypcji. Bez klucza pokazuje prawdziwy status nieaktywności.
4. Kopia poza komputerem/serwerem: wybierz niezależne miejsce przechowywania. Obecne codzienne kopie SQLite są sprawdzane, ale leżą na tym samym komputerze, więc nie chronią przed utratą całego urządzenia. Dla produkcyjnego PostgreSQL potrzebne są backupy oraz test odtworzenia.
5. Konta redakcji: podaj później osoby zaproszone do tworzenia nitek. Obecna wersja dopuszcza konta redakcyjne, bez publicznej rejestracji.
6. Opcjonalnie: linki Patronite/BuyCoffee. Bez nich przyciski wsparcia pozostają ukryte.

Nie kupuj API X dla tego MVP. X jest wyłącznie odnośnikiem dodawanym do nitki po URL. Eksport do X przygotowuje teksty do sprawdzenia i skopiowania, niczego sam nie publikuje.

Nie trzeba teraz kupować większego pakietu ChatGPT ani uruchamiać płatnego AI portalu. Czytnik i importery nie są wytrenowanym modelem. Asystent AI z cytowaniami, role dziennikarz/komentator, sponsorowanie i publiczne konta pozostają kolejnymi etapami.

# Co działa lokalnie
- Wyszukiwanie całej zgromadzonej bazy przez kolejne strony wyników, bez dawnego limitu500.
- Import RSS i dokumentów urzędowych, kolejka archiwalnych map witryn, ponawianie błędów i uzupełnianie znanych braków.
- Odczyt tekstu JSON-LD articleBody tam, gdzie wydawca go udostępnia; przeszukiwanie tego tekstu. To nie gwarantuje kompletności artykułu.
- Widoczny zakres źródeł i braków, komentarze autora, linki X w nitkach i eksport tekstów.

# Ograniczenia
Część RSS jest nadal niedostępna lub błędna; GDELT miewa przekroczenia czasu odpowiedzi. Kolejka odkrytych URL nie jest liczbą zweryfikowanych artykułów. Znane braki są zachowane zamiast ukrywania ich. Nie twierdzimy, że archiwum jest kompletne. Produkcyjnego środowiska i testu obciążenia na docelowym serwerze jeszcze nie wykonano.

# Proces lokalny
python backend/manage.py run_local_jobs (z USE_SQLITE=true) uruchamia jeden harmonogram; drugi jest blokowany. Zamknięcie tego procesu albo uśpienie komputera przerywa import. Po wznowieniu trwała kolejka zachowuje postęp. Start-Portal.ps1 uruchamia podgląd strony, nie harmonogram importów.
