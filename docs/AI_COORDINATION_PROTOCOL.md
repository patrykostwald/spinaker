# Stała koordynacja Codex + Claude

Przy każdym nowym zadaniu Codex najpierw ocenia, czy istnieje niezależny,
ograniczony i bezpieczny fragment, który można przekazać Claude Code równolegle.

- Claude otrzymuje audyty, wąskie implementacje z testem, raporty, przygotowanie
  dokumentacji i katalogowanie kandydatów.
- Codex zachowuje integrację zmian, działania zależne od bieżącej bazy,
  decyzje o źródłach, kontrolę procesów oraz pracę wymagającą bezpośredniego
  kontaktu z właścicielem.
- Zadanie dla Claude’a musi wyraźnie określać zakres, pliki, test oraz zakazy:
  brak produkcji, brak sekretów, brak masowego pobierania i brak frontendu,
  jeżeli nie jest to jego celem.
- Nie czekamy na przypomnienie właściciela: wykorzystujemy dostępnego pomocnika
  wszędzie, gdzie zmniejsza czas realizacji bez zwiększania ryzyka.
