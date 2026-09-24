# Uruchomienie dr. Spina — lista dla właściciela

Obecna wersja kodu obsługuje OpenAI. Mistral jest zaplanowany jako drugi adapter i jego klucz nie jest jeszcze używany przez aplikację. Nie kupuj większego planu Mistral przed pomiarem pilotażu; patrz `AI_PROVIDER_PLAN.md`.

Projekt ma dwie osobne konfiguracje: publiczne wyszukiwanie kontekstu i wewnętrzną redakcyjną analizę wypowiedzi z internetem oraz redakcyjny wybór materiałów już zapisanych w bazie.

## Co ustawić lokalnie na serwerze

- `OPENAI_API_KEY`: klucz API projektu OpenAI. Nie wklejaj go do rozmowy, kodu strony ani plików publicznych.
- `DR_SPIN_RESEARCH_MODEL`: identyfikator modelu dostępnego na Twoim koncie, obsługującego Responses i narzędzie `web_search`.
- `DR_SPIN_RESEARCH_ENABLED=true`: włącza publiczne wyszukiwanie AI po przygotowaniu pozostałych ustawień.
- `DR_SPIN_RESEARCH_DAILY_LIMIT=20`: początkowy wspólny limit prób na dobę UTC dla kontekstu i wewnętrznej analizy redakcyjnej. Nieudane wywołania również zużywają próbę.
- `DR_SPIN_MODEL`: model dla redakcyjnego wyboru materiałów z bazy. To osobna ścieżka, bez internetowego wyszukiwania.
- `DR_SPIN_DAILY_CALL_LIMIT=20`: osobny dzienny limit prób redakcyjnych szkiców.

Brave nie jest potrzebne do wyszukiwania przez Responses `web_search`. Jest alternatywną, osobno konfigurowaną usługą. Abonament ChatGPT nie konfiguruje klucza API tej strony.

## Jak sprawdzić gotowość bez ponoszenia kosztu zapytań

Po zastosowaniu migracji uruchom w środowisku backendu:

```
python manage.py ai_preflight
```

Raport pokazuje obecność ustawień (`present` / `missing`), nie ich tajne wartości. Wypisuje liczbę domen, limity i zużyte próby oraz zapisane pomiary wywołań AI. Nie wysyła zapytań do dostawcy i nie zmienia bazy.

`local_configuration_ready` oznacza wyłącznie spełnienie sprawdzanych warunków lokalnych. Nie potwierdza poprawności klucza, uprawnień modelu ani salda. Lista powyżej 100 domen wymaga zmiany konfiguracji — nie pomijamy po cichu źródeł.

## Co mierzymy

Każde rozpoczęte wywołanie internetowego AI ma rekord: czas, wybrany model, tryb, wynik, status HTTP i — gdy dostawca je zwróci — liczbę tokenów wejściowych, wyjściowych i zaobserwowanych wywołań `web_search`. Liczba narzędzi obejmuje pozycje odpowiedzi, nie szacowaną liczbę wszystkich pobranych stron. Niedostępny pomiar ma wartość `null`, nigdy domyślne zero. `observed_totals` sumuje tylko znane pomiary; `unknown_metrics` pokazuje, ile pozostaje nieznanych.

Audyt nie zapisuje kluczy, zapytań użytkownika, wklejanych wypowiedzi, odpowiedzi AI ani adresów badanych materiałów. Nie wylicza kosztu USD bez właściwych danych rozliczeniowych. Obecny audyt tokenów dotyczy internetowej ścieżki AI; redakcyjny szkic ma na razie tylko licznik prób.

Przed uruchomieniem dla wszystkich sprawdź w panelu dostawcy ustawienia wydatków i alerty. Limit prób i limity tokenów pomagają ograniczać zużycie, ale nie są gwarancją konkretnej ceny. Pierwszy płatny pilotaż powinien sprawdzić oba tryby i faktyczne dane rozliczeniowe. Przygotowanie oraz testy tej funkcji nie wykonały płatnych zapytań.


Nie uruchamiamy publicznego SPIN VERIFY. Analiza wypowiedzi polityka wymaga konta redakcyjnego (`is_staff`); pozostali otrzymują odmowę przed rezerwacją próby i wywołaniem AI. Jej docelowym zastosowaniem jest przygotowanie redakcyjnej nitki Dr Spina z wypowiedzią jako pierwszym boxem. Publiczna pozostaje funkcja wyszukiwania kontekstu. Pole `verify` w raporcie preflight oznacza jedynie wewnętrzną ścieżkę redakcyjną, nie funkcję publiczną.
