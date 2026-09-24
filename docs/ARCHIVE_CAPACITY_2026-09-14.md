# Pojemność importu archiwum — pomiar 14 września 2026

## Stan pomiaru

- 132 248 rekordów Article.
- 314 lokalnych Source.
- 3 620 742 oczekujących pozycji ArchiveJob.
- 34 zadania oznaczone jako running przy konfiguracji 32 workerów.
- 92 392 zadania done i 5 446 error.
- Około 111 nowych rekordów/min w ostatnich 10 minutach pomiaru; wcześniejszy szczyt około 230–238/min.
- Baza SQLite: około 1,8 GB. Wolne miejsce na dysku C: około 175,5 GB.

## Realny czas

Proste podzielenie kolejki przez bieżące tempo daje około 11–23 dni samego przejścia po znanych URL-ach. Nie uwzględnia to limitów domen, ponowień, blokad, nowych adresów, deduplikacji ani kontroli jakości.

- Pierwszy szeroki przebieg znanej kolejki: 3–6 tygodni przy pracy ciągłej.
- Uporządkowanie błędów, dat, duplikatów i brakujących miniaturek: dalsze 3–6 tygodni.
- Archiwum nie ma stanu „skończone”: część źródeł będzie rozszerzana miesiącami, a znane braki pozostaną jawne.

## Limit lokalnej maszyny

32 workery pozostają bezpiecznym maksimum zmierzonym dla obecnego importera. Dodawanie kolejnych dawało malejącą korzyść, a zwiększa ryzyko blokad domen, kontencji SQLite i gorszej jakości. Maksymalizujemy przepustowość per domena z osobnymi limitami, zamiast atakować wszystkie źródła jednym globalnym tempem.

Przy obecnym średnim rozmiarze bazy 3,5 mln rekordów może wymagać około 45–55 GB samej bazy. Indeksy, WAL/pliki tymczasowe i rotowane kopie mogą podnieść lokalne zapotrzebowanie do około 80–120 GB. Obecny dysk wystarczy na pierwszy przebieg przy imporcie metadanych i kontrolowanej rotacji kopii; pełne teksty, obrazy lub nieograniczone backupy szybko wyczerpią zapas.

## Zasady nocnego importu

- Metadane i krótkie opisy; brak masowego przechowywania pełnych tekstów.
- 32 workery, limity i backoff osobno dla domen.
- Bieżące źródła mają zarezerwowaną część przepustowości; archiwum nie może ich zagłodzić.
- Nieudane rekordy trafiają do kolejki jakości, a nie w nieskończone szybkie ponowienia.
- Kopie są rotowane po zweryfikowaniu nowszej kopii.
- Przed migracją do Supabase wykonać próbę rozmiaru i kosztu na reprezentatywnej partii.
