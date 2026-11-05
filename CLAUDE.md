# Zasady nadrzędne dla agentów (Claude, Codex i każdy kolejny)

Te zasady wydał właściciel i obowiązują w **każdym projekcie**, także w tym. Mają pierwszeństwo przed
wygodą. Przeczytaj je przed pierwszą zmianą.

## 1. Czystość repozytorium

- Repozytorium ma być uporządkowane: bez śmieci, plików tymczasowych, baz, logów, sekretów, `.env`,
  zbudowanych artefaktów i martwych kopii. Pliki robocze trzymaj poza repozytorium albo w ignorowanych
  katalogach.
- Nazwy plików i katalogów mają być spójne i opisowe. Jedna rzecz ma jedno miejsce. Nie dubluj dokumentów;
  jeśli nowy zastępuje stary, oznacz stary jako zastąpiony i wskaż nowy.
- Przed zakończeniem pracy sprawdź `git status`: nic przypadkowego, nic niezamierzonego.

## 2. Dokumentacja i przekazanie dla następnego agenta

W folderze projektu zawsze musi być aktualny komplet, z którego **następny agent bez pytania właściciela**
pozna: plan, poprawki, wdrożenia, uaktualnienia i wykonane ruchy.

- **Plan** — aktualny plan projektu (tu: `PLAN_AKTUALNY.md` oraz `docs/PLAN_PRZESZLOSC_OSINT.md`).
  Zmieniasz kierunek lub zakres: aktualizujesz plan **w tej samej pracy**, nie „później".
- **Przekazanie** — `HANDOFF_AI.md`: co zrobione, czego nie ruszać, znane błędy, polecenie uruchomienia,
  następny krok. Aktualizuj na końcu każdej sesji.
- **Dziennik** — `docs/PROGRESS.md`: data, co zmieniono, dlaczego, jak sprawdzono, co dalej
  (poprawki, wdrożenia, aktualizacje, decyzje właściciela).
- Nigdy nie wpisuj sekretów, haseł, kluczy ani danych użytkowników.
- Dokument musi odróżniać: **zrobione i sprawdzone** / **zrobione, niesprawdzone** / **zaplanowane**.
  Nie pisz, że coś działa, jeśli tego nie uruchomiono.

## 3. Git i GitHub — standard „jak CTO"

- Praca na osobnej gałęzi, nigdy bezpośrednio na `main`. Gałąź ma czytelną nazwę.
- Małe, logiczne commity z jasnym opisem **co i dlaczego** (komunikat w trybie rozkazującym lub zwięzłym
  opisie, bez „poprawki różne"). Jeden commit = jedna sprawa.
- Przed wypchnięciem: testy i build przechodzą (lub jawnie opisane, czemu nie), brak sekretów, brak
  plików roboczych, `git status` czysty.
- Pull request: wyraźny tytuł, opis (cel, zakres zmian, jak sprawdzono, ryzyka, co poza zakresem, następne
  kroki), powiązanie z planem. Nowy PR jako szkic (draft), dopóki nie jest gotowy.
- Nie przepisuj historii cudzych gałęzi, nie wymuszaj pushy bez wyraźnej zgody, nie pomijaj kontroli
  (testów, CI), nie kasuj ani nie wyłączaj testów, by uzyskać zielony wynik.
- Działania nieodwracalne lub zewnętrzne (publikacja, wysyłka wiadomości, wydatek, wdrożenie produkcyjne,
  zapis do produkcyjnej bazy) — tylko za zgodą właściciela.

## 4. Plany zawsze aktualne

- Plan, który nie odpowiada rzeczywistości, jest błędem. Gdy odkryjesz rozbieżność (np. żywa strona vs
  kod), zapisz ją w planie i w `HANDOFF_AI.md`.
- Każda zmiana zakresu, priorytetu, decyzji produktowej lub technicznej trafia do planu z datą.

## 5. Styl współpracy z właścicielem

- Właściciel jest amatorem: prowadź krok po kroku, podawaj pełne polecenia i **gdzie dokładnie** je wkleić.
- Odpowiadaj po polsku, konkretnie. Rozdzielaj fakty od założeń.
