# Zlecenie dla Claude Code — kontrakty adapterów AI (bez połączeń z dostawcami)

Pracujesz w `C:\Users\User\spin-clinic\.local\spinaker-mvp-frontend`.

## Cel

Przygotuj wyłącznie fundament do późniejszej integracji NVIDIA NIM (embeddingi,
reranking) i Groq (redakcyjny JSON). Nie wykonuj prawdziwych wywołań HTTP,
nie potrzebujesz kont, kluczy ani danych zewnętrznych.

## Granice

- Nie zmieniaj Docker, `.env`, infrastruktury, migracji, publicznego frontendu,
  procesu pobierania X ani obecnych integracji AI.
- Nie odczytuj ani nie przesyłaj snapshotów, `ArticleContent`, sekretów,
  e-maili lub danych użytkowników.
- Nie dodawaj zależności dostawców ani automatycznego fallbacku.
- Nie twórz automatycznej publikacji. Każdy przyszły wynik ma być szkicem.
- Nie commituj i nie pushuj.

## Zakres implementacji

1. Dodaj mały, provider-neutralny moduł backendowy z interfejsami dla:
   - generowania embeddingu;
   - rerankingu kandydatów;
   - przygotowania redakcyjnego szkicu JSON.
2. Zdefiniuj jawne dataclasses/Pydantic/serializery wejść i wyjść z polami:
   identyfikator materiału, publiczny URL, źródło, data, krótki fragment,
   cytat, dowody za/przeciw, luki, pokrycie dowodowe i wersja schematu.
3. Zaimplementuj tylko fake providers do testów: deterministyczne, bez sieci i
   bez sekretów.
4. Dodaj walidator wyniku szkicu: ma odrzucać nieznane identyfikatory
   materiałów, brak cytowanego URL, brak wersji schematu i próby ustawienia
   statusu publikacji.
5. Dodaj testy pokazujące, że fake provider nie wykonuje sieci, nie publikuje
   oraz że niedozwolone dane nie mieszczą się w kontrakcie wejścia.
6. Dopisz krótką dokumentację modułu: rzeczywiste adaptery NIM/Groq będą
   dodane później za feature flagą i limitem kosztu.

## Definicja ukończenia

- Testy zakresu modułu przechodzą lokalnie.
- Brak zmian w plikach wymienionych w sekcji „Granice”.
- `git diff` pokazuje tylko nowy moduł, jego testy i dokumentację.
- W podsumowaniu podaj listę plików, testy i potwierdź brak wywołań sieciowych.
