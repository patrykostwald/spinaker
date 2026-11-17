# Zlecenie dla Budowniczego - szablon (pętla Śledczy-Budowniczy)

Skopiuj do `zlecenia-codex/<numer>-<nazwa>.md`, wypełnij każdą sekcję. Jedno zlecenie = jeden worktree = jedna gałąź.
Puste pole „Pliki, których nie dotykasz” oznacza, że Dyrygent nie sprawdził kolizji - zlecenie wraca.

## 1. Zakres
- Numery z backlogu Śledczego (np. P1-3, P2-7) i jedna linia, co ma działać po zmianie.
- Czego NIE robimy w tym zleceniu (żeby Budowniczy nie rozszerzał zakresu).

## 2. Kryteria odbioru (skopiowane z raportu Śledczego, mierzalne)
- [ ] adres / komenda / test, który to potwierdza
- [ ] zrzut 1440 i 390 px bez ZLE: `node scripts/sledczy_zrzuty.js <katalog> <adres>`
- [ ] pomiar szybkości, jeśli zmiana dotyka API: `python scripts/przeszlosc_bench.py --db <kopia> --runs 10`

## 3. Worktree i gałąź
```
git worktree add C:\Users\User\spin-clinic\wt-<nazwa> -b <rola>/<nazwa>-r<runda> codex/mvp-public-frontend
```
- Pliki, które masz prawo zmieniać (lista): …
- Pliki, których nie dotykasz, bo zmienia je inne zlecenie (lista + kto): …
- Pliki wspólne (np. `backend/news/urls.py`, `przeszlosc.py`): tylko dopisanie osobnych funkcji / linii na końcu bloku, bez przestawiania istniejących.

## 4. Zasady stałe
- Testy do każdej zmiany (pytest w `backend/`, znane 12 błędów CSRF/Django-Py3.14 to środowisko).
- Bez migracji, jeśli się da (indeksy: `manage.py przeszlosc_indeksy`); bez wdrożeń, bez push, bez czytania `.env`.
- Prawo: osoby publiczne tylko przez identyfikatory, nic po samym nazwisku; „brak w naszych danych (zakres, data)” zamiast „brak”.
- Design: lista kontrolna z CLAUDE.md (dociąganie w boksie, równe wysokości, 44 px, odstępy), każda poprawka wskazuje prawo z Laws of UX.
- Commity lokalne, osobne na każde zadanie, końcówka `Co-Authored-By: Claude <model> <noreply@anthropic.com>`.

## 5. Raport zwrotny (do 15 linii)
- co zrobione (numer → commit), pomiary przed/po, testy (ile zielonych), ryzyko konfliktów (plik → funkcja → z kim), gałąź.
- czego nie zrobiono i dlaczego; pytania do właściciela osobno (tylko pieniądze, prawo, publikacja).
