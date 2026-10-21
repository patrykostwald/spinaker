# Prototyp: skaner dostępności iapply (opis dla Warsztatu, wersja robocza)

Cel: 70% pracy audytu robi maszyna, człowiek sprawdza 10 podstron i podpisuje raport. Jedno narzędzie dla H1 i H2.

## Wejście i wyjście
- Wejście: adres strony, limit podstron (domyślnie 50), typ (instytucja / sklep - dla sklepu ścieżka: wyszukiwarka, produkt, koszyk, zamówienie).
- Wyjście: raport HTML/PDF w ciemnym motywie iapply + plik JSON z błędami + projekt deklaracji dostępności.

## Kroki
1. **Crawl** z poszanowaniem robots.txt, 1 zapytanie na sekundę, tylko strona klienta, który zamówił albo poprosił o skan.
2. **Testy automatyczne:** axe-core w Playwright (Chromium jest w środowisku) dla widoku 1440 i 390 px; Lighthouse accessibility jako drugi głos.
3. **Rada modeli (PCSS: gpt-oss 120B, Qwen, Bielik):** ocena tego, czego automat nie umie - czy tekst alternatywny opisuje obraz,
   czy nazwy linków mają sens („czytaj więcej” x 20), czy tekst jest prostym językiem, czy nagłówki tworzą sensowny spis.
   Każdy model ocenia osobno, wynik łączy stała reguła, przy niezgodzie „do ręcznego sprawdzenia” (metoda Konsylium).
4. **PDF:** sprawdzenie tagów i języka dokumentów (próbka), np. veraPDF [DP: licencja].
5. **Lista do ręcznego testu:** 10 podstron wybranych automatycznie (główna, kontakt, formularz, aktualności, najcięższa strona).
6. **Raport:** błędy pogrupowane według kryterium WCAG i wagi, zrzut fragmentu, sposób naprawy, szacunek czasu naprawy (wejście do wyceny zbudujmi).

## Zakres pierwszej wersji (1-2 dni Codex)
Kroki 1, 2, 6 oraz 3 tylko dla tekstów alternatywnych i nazw linków. Bez logowania na stronach klientów.

## Czego nie robi
Nie wydaje certyfikatów, nie ocenia zgodności z prawem, nie skanuje stron bez zamówienia lub prośby właściciela strony.
