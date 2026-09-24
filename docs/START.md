# Na początek

1. Otwórz http://localhost:3000. Jeśli podgląd nie działa, uruchom `Start-Portal.ps1` w katalogu projektu.
2. Wyszukaj `zondacrypto Mariusz Gosek`. Zobaczysz dwa głosowania wraz z dokładnym wnioskiem, głosem posła i wyjaśnieniem powiązania tematycznego.
3. Otwórz http://localhost:3000/editor. Lokalny login i wygenerowane hasło są w `.local/admin-login.txt` w katalogu projektu.
4. Nadaj nitce tytuł. Dodaj materiały z wyszukiwarki albo wklej adres źródła i wybierz pobranie metadanych. Sprawdź tytuł, kategorię, datę i autora — nieznanych danych nie trzeba uzupełniać.
5. Dopisz komentarze do źródeł. Zapisz szkic lub zaznacz publikację. Opublikowana nitka pojawi się na stronie głównej jako oś czasu.

Pierwsze nitki zostawiliśmy do Twojej redakcyjnej decyzji. Baza zawiera rzeczywiste materiały, ale samo znalezienie czegoś w bazie nie oznacza, że każde twierdzenie w źródle zostało sprawdzone.

## Co jest lokalnie

6036 materiałów: 630 pozycji RSS, 50 głosowań, 3278 druków sejmowych, 2078 pozycji Dziennika Ustaw i Monitora Polskiego. Osobno zapisano 22 997 głosów imiennych. Liczby dotyczą stanu po pierwszych importach 8 września 2026 r., a nie całego polskiego archiwum.

Panel redakcji pokazuje również błędy źródeł. 32 z 59 skonfigurowanych kanałów RSS wymagały dalszego sprawdzenia po pierwszym pobraniu. Część adresów z briefu nie jest już kanałem RSS; poprawione GUS i RMF24 zweryfikowano na stronach wydawców. Nie ukrywamy tych braków i nie zastępujemy ich fikcyjnymi rekordami.

## Do uruchomienia publicznego

Pozostają wybór i konfiguracja hostingu, bazy PostgreSQL, Redis oraz worker/Beat, domena i HTTPS. X wymaga tokenu oraz świadomej aktywacji płatnych odczytów; NewsAPI wymaga odpowiedniego planu. Linki Patronite i Buycoffee możesz podać później. Nie zakupiono usług ani nie opublikowano portalu w Internecie.

Instrukcja techniczna: `README.md` i `docs/DEPLOYMENT.md`. Zasady danych: `docs/DATA.md`. Koncepcja przyszłego asystenta: `docs/AI.md`.
