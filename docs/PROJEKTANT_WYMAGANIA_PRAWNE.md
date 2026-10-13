# Wymagania prawne i treściowe, które przebudowa wyglądu przeszłość.today musi zachować

Stan na 13.10.2026. Dotyczy widoków z pieniędzmi publicznymi (drzewo przepływu pieniędzy, profil spółki, profil osoby). Wygląd można zmieniać dowolnie, **treści i pola poniżej muszą zostać widoczne**. Podstawa: opinia Prawnika z 13.10.2026 (NIW-CRSO, wykaz OPP, lista FE) oraz zasada „ta sama miara dla wszystkich”.

## Pliki, których to dotyczy
- `frontend-spin/app/przeszlosc/DrzewoPieniedzy.tsx`
- `frontend-spin/app/przeszlosc/PersonProfile.tsx`
- `frontend-spin/app/przeszlosc/spolka/[krs]/page.tsx`

Ten sam plik zmieniają projektant i budowa danych, więc przy przebudowie **scalaj z gałęzią `codex/mvp-public-frontend` przed oddaniem**, żeby nie powstał konflikt (13.10 konflikt w `DrzewoPieniedzy.tsx` zablokował wdrożenie).

## Co musi być widoczne
1. **Gałąź „Dotacje (unijne i krajowe)”**, zakładka „Dotacje”, licznik „dotacja/dotacje/dotacji”. Nie wolno wrócić do „Dotacje UE”: od 13.10 w tych samych wierszach są dotacje krajowe (źródło `niw`, NIW-CRSO).
2. **Źródło każdego wiersza dotacji** (`g.source`: `fts` → FTS, `niw` → NIW-CRSO) i licencja źródła w stopce gałęzi (`informacja publiczna` dla NIW).
3. **Dopisek przy wierszu NIW** (`g.attribution`): źródło, stan pliku, „opracowanie iapply, nie jest publikacją NIW”, „kwota wynika z umowy i nie oznacza wypłaty”.
4. **Dopiski zbiorcze** zwracane przez API, wszystkie widoczne pod listą rekordów:
   - `grants.sums_note`: środki krajowe, unijne i z 1,5% PIT pokazujemy osobno i nie sumujemy,
   - `grants.note`: stan pliku źródłowego,
   - `people.note`: zastrzeżenie przy powiązaniach osób publicznych z organizacją (powiązanie z rejestrów jawnych, nie oznacza decyzji ani zależności; daty roli i umowy obok siebie).
5. **Kwoty w PLN i EUR osobno**, nigdy w jednej sumie (`sumLine`).
6. **Brak słów sugerujących zależność**: „zależny”, „związany z”, strzałek przyczynowych między osobą a pieniędzmi.
7. **Gdy nie ma danych**: stan pusty z opisem, bez zer udających pomiar.

## Czego nie robić
- Nie pokazywać wierszy bez KRS ani osób fizycznych (backend je odfiltrowuje; frontend nie powinien ich dorabiać z innych pól).
- Nie łączyć beneficjenta z organizacją po samej nazwie.
- Nie usuwać stopki ze źródłami i licencjami.

## Dane do wglądu
`GET /api/przeszlosc/spolka/<KRS>/` zwraca `grants.results[]` (pola: `source`, `title`, `programme`, `amount`, `currency`, `date`, `url`, `matched_by`, `attribution`, `beneficiary`, `contract_no`, `file_date`), `grants.sums`, `grants.sums_note`, `grants.note`, `people.note`. Przykład organizacji z dotacjami NIW: `0000037027`.
