# Śledczy - głos kontrolny do mapy funkcji (Fable, 11.10.2026)

Założenia: P1 z rundy 1 (P1-1 wyszukiwarka spółek, P1-3 głosowania, P1-4 provenance, P1-7 szum) idzie przed nowymi funkcjami; nowe funkcje tylko tam, gdzie kod już jest albo nakład to S. Bez kont użytkowników w tych 3 tygodniach - konta ciągną za sobą RODO, szyfrowanie, usuwanie i tryb bezpieczny naraz.

## 1. Sześć funkcji na 3 tygodnie (wartość / nakład)
1. **F9 Przybornik odnośników** - S, zero ryzyka, robi się razem z P1-4 (link do KRS MS zamiast rejestr.io); godzina pracy śledczego mniej na każdą spółkę.
2. **F2 Strażnik cytatu** - S, backend `article_changes.py` już jest, brakuje etykiety i różnicy; jedyna funkcja z listy, którą obiecujemy na `/funkcje/`, a nie działa.
3. **F3 Zapis dowodu, wersja bez konta** - plik do pobrania (PDF + nagłówki + SHA-256 + token czasu), u nas tylko hash, URL i data; fundament przypisów w F4 i F16, bez przechowywania treści.
4. **F1 Sankcje i PEP tylko z list urzędowych** (UE, ONZ, MSWiA, OFAC, PEP z Wikidata) - S, dopasowanie najpierw po identyfikatorze, trafienie po nazwie zawsze jako „możliwe”; OpenSanctions dopiero po umowie.
5. **F4 Teczka lokalna** - przypięte rekordy i notatki w przeglądarce użytkownika, eksport MD/DOCX z przypisami (źródło, data pobrania, hash z F3, etykieta z F2); zero danych u nas, więc zero RODO i prawie gotowy tryb bezpieczny.
6. **F7 Generator wniosku o informację publiczną** - S, z rekordu TED/BZP bez kwoty (łączy się z flagą `amount_suspect` z P0-1); termin 14 dni jako plik .ics zamiast licznika w koncie.

## 2. Trzy funkcje, których nie robić teraz
- **F18 Własne dokumenty** - L, umowa powierzenia (art. 28 RODO), serwery UE, OCR, złośliwe pliki; jedno naruszenie kończy zaufanie redakcji. Datashare robi to lokalnie i za darmo - odsyłać do niego.
- **F17 Publiczne archiwum odpowiedzi UDIP** - publikujemy cudze dokumenty z PESEL-ami i adresami; automatyczna anonimizacja nie jest niezawodna, a odpowiadamy my. Najpierw F7 musi mieć użytkowników.
- **F15 Łańcuch własności z CRBR** - podstawa dostępu do CRBR dla dziennikarzy niepotwierdzona ([DP] AMLD6, termin PL), licencja GLEIF Level 2 niesprawdzona, M-L. Czekać na Prawnika; robić tylko po tym, jak P1-1 da pełne KRS.

## 3. Kolejność budowy i zależności
- Tydzień 1: P1-4 + F9 (jeden widok „źródła i rejestry”), F2 (widok na istniejącym `ArticleChangeEvent`), higiena F5-minimum: `journey_report` i „Zgłoś błąd” bez treści zapytań `q` - to naprawa, nie funkcja, przed wszystkim innym.
- Tydzień 2: F3 (potrzebuje: wybranego darmowego serwera TSA RFC 3161, testu `openssl ts -verify`), F1 (potrzebuje: tabeli identyfikatorów NIP/KRS/LEI przy podmiotach, cronu pobierania list z datą wersji; działa na 800 podmiotach, pełną wartość da po P1-1).
- Tydzień 3: F4 (zależy od F2 i F3: przypis bierze hash i etykietę zmiany), F7 (zależy od adresów zamawiających z TED, opcjonalnie od F4: wniosek wpada do teczki).
- Po 3 tygodniach: F13 ścieżka X-Y (zależy od P1-1 i filtra okresu z P0-2), F16 pakiet dla prawnika (zależy od F4 + F3), F14 red flags (zależy od P0-1 i tła statystycznego, którego przy TED od 10.2025 i wyłączonym BZP jeszcze nie ma).

## 4. Czego brakuje na liście
1. **Okno pokrycia danych przy każdej sumie i liście** („TED od 2025-10-21, BZP brak, artykuły: 2000 z 525 tys.”) - runda 1 to wytknęła, lista funkcji tego nie podnosi; to najtańsza funkcja zaufania.
2. **Filtr „tylko źródła pierwotne”** (druki, interpelacje z odpowiedziami, sprawozdania RDF, komunikaty prokuratury) - scenariusz S5 pokazał, że twierdzenia polityków nie da się sprawdzić w narzędziu; F22 to różnice wersji, nie to.
3. **Pilot z 3 prawdziwymi redakcjami przed budową przestrzeni pracy** - cała mapa to ocena AI udającej dziennikarza; kolejność F4/F16/F19 powinien potwierdzić człowiek, który pisze teksty.

## 5. Największe ryzyko
Fałszywa pewność w obie strony: trafienie po samej nazwie czytane jako wina (F1, F8, F13) i „brak trafień / brak ścieżki / brak zmian” czytane jako czyste konto, gdy baza ma 800 podmiotów i rok TED. Zasada dla każdej nowej funkcji: nigdy samo „brak”, zawsze „brak w naszych danych (zakres, data listy, metoda)”, a wynik po nazwie nigdy nie wchodzi do sum, grafu ani eksportu bez etykiety. Drugie w kolejce: obietnica „trybu bezpiecznego” częściowo spełniona jest groźniejsza niż jej brak - dziś zapytania trafiają do analityki ścieżek, więc najpierw to wyłączyć, dopiero potem o tym mówić.
