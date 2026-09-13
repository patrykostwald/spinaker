# Dostawcy AI — decyzja na MVP

Stan na 14 września 2026.

## Decyzja

- OpenAI pozostaje pierwszym dostawcą dla istniejącego prototypu wyszukiwania internetowego, ponieważ ta integracja jest już przygotowana w kodzie.
- Mistral zostaje drugim dostawcą pilotażowym. Europejski endpoint `https://api.eu.mistral.ai` wykorzystamy najpierw do klasyfikacji metadanych, wyboru i porządkowania kandydatów do nitki oraz testów embeddings — wyłącznie po potwierdzeniu dostępności wybranego modelu w regionie UE.
- Nie włączamy teraz globalnego wyszukiwania Mistral. Regionalny endpoint UE nie udostępnia wszystkich funkcji globalnych. Jego zakres sprawdzimy testem technicznym, bez przesyłania danych użytkowników.
- Claude może pomagać w pracach nad repozytorium, ale jego API nie jest wymagane w MVP.
- DeepSeek pozostaje wykluczony decyzją właściciela.

## Zasady integracji

Każdy dostawca działa przez wymienny adapter. Model nie zapisuje bezpośrednio rekordów, nie publikuje nitek i nie wydaje samodzielnie ocen politycznych. Zwraca propozycje oparte na identyfikatorach boxów i jawnych adresach źródeł. Publikację zatwierdza redakcja.

Do zewnętrznych modeli nie wysyłamy danych kont, komentarzy, adresów e-mail ani prywatnej aktywności użytkowników. W pilotażu przekazujemy tylko zapytanie, publiczne metadane źródeł i — jeśli istnieje odpowiednia podstawa — niezbędny fragment publicznego materiału.

## Porównanie dostawców

Przed rozszerzeniem ruchu wykonujemy ten sam zestaw 30–50 polskich zapytań dla obu dostawców. Mierzymy poprawność linków i dat, zgodność z dozwolonymi źródłami, trafność chronologii i wyboru do 15 boxów, twierdzenia bez pokrycia, czas, koszt i stabilność formatu. Wynik decyduje, który dostawca obsługuje daną funkcję.

## Konfiguracja Mistral

Klucz jest przechowywany wyłącznie po stronie serwera i nigdy nie trafia do GitHub, przeglądarki ani rozmowy. Początkowo ustawiamy `MISTRAL_ENABLED=false`; włączymy go dopiero po dodaniu adaptera, limitu kosztu i dziennika wywołań. Pierwszy test korzysta z europejskiego endpointu i sztucznych lub publicznych danych.

Konto płatne i większy limit nie są potrzebne przed testem połączenia. Do produkcji włączymy budżet oraz alerty wydatków po pomiarze kosztu pilotażu.

Pierwsze zadanie w Mistral Studio powinno pozostać odizolowaną analizą bez dostępów do systemów. Gotowy prompt: `MISTRAL_PILOT_PROMPT_PL.md`.
