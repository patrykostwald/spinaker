# Uruchomienie publiczne — lista kontrolna

Ten dokument przygotowuje wdrożenie. Nie uruchamia produkcji i nie zawiera sekretów.

## Przed pierwszym wdrożeniem

- Ustal domenę, administratora danych, adres redakcyjny i adres do spraw prywatności.
- Ustaw wszystkie sekrety na serwerze: `DJANGO_SECRET_KEY`, hasła bazy i Redis, klucze API, adresy dozwolonych hostów oraz `NEXT_PUBLIC_CONTACT_EMAIL`.
- Nie zapisuj kluczy w Git ani w pliku przeznaczonym do udostępniania współpracownikom.
- Zbuduj obrazy z bieżącego commitu i uruchom migracje na kopii bazy przed produkcją.
- Skonfiguruj HTTPS i automatyczne odnowienie certyfikatu według `deploy/README.md`.

## Dane i źródła

- Zweryfikuj, że każda aktywna integracja ma dozwolony sposób pobierania i limit.
- Zachowaj limity X; włączone konta pobieraj zgodnie z ich interwałem, bez ponownego pobierania tych samych postów.
- Uruchamiaj harwestery wyłącznie dla źródeł zatwierdzonych w katalogu dostępu.
- Zrób kopię PostgreSQL przed większym importem oraz sprawdź możliwość jej odtworzenia.

## Funkcje użytkowników

- Najpierw udostępnij konta i prywatne nitki ograniczonej grupie testowej.
- Włącz komentarze publicznie dopiero po sprawdzeniu panelu zgłoszeń, limitów i dyżuru moderacyjnego.
- Przetestuj usunięcie konta oraz usunięcie danych użytkownika na kopii bazy.

## AI

- Zostaw `NIM_ENABLED=false` i `GROQ_EDITORIAL_ENABLED=false`, dopóki nie ma zestawu pilotażowego oraz kryteriów jakości.
- W pilotażu rejestruj źródła, fragmenty wejściowe, wersję modelu, wynik i decyzję redaktora.
- Żaden wynik nie może opublikować się samoczynnie.

## Kontrola końcowa

- Uruchom testy backendu i sprawdzenie typów frontendu na tym samym commicie, który będzie wdrażany.
- Sprawdź stronę mobilną, logowanie, źródła, politykę prywatności, zasady, kontakt i stronę błędu.
- Sprawdź logi po uruchomieniu, zdrowie bazy/Redis/workerów oraz alarmy błędów.
- Ustaw regularne kopie bazy, retencję kopii i osobę odpowiedzialną za ich przegląd.
- Dopiero po zatwierdzeniu tych punktów ustaw publiczny DNS.
