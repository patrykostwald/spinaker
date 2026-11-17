# Zasady wspólne dla sesji w chmurze (23.10.2026)

- Repo spin.clinic + przeszłość.today (Django w `backend/`, front w `frontend/`). Najpierw przeczytaj `CLAUDE.md` w korzeniu repo.
- Nie masz dostępu do produkcji ani serwera. Budujesz kod, testy, komendy `manage.py` i pliki danych. Wdrożenie i komendy na
  serwerze napisze koordynator dla właściciela - na końcu raportu podaj, jakie komendy trzeba uruchomić i w jakiej kolejności.
- Pracujesz tylko na swojej gałęzi `cloud/...` (podanej w zadaniu). Commit i push po każdej części; pierwsza linia commita bez
  polskich znaków, na końcu `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Nie scalaj do innych gałęzi.
- Zero halucynacji: każde nazwisko, urząd, konto X, numer KRS i liczba z podanego źródła (link w danych). Gdy niepewne - oznacz
  `[DP]` i nie publikuj. Lepiej brak danej niż zła dana.
- Tylko legalne źródła: oficjalne API i strony (sejm.gov.pl, senat.gov.pl, gov.pl, prezydent.pl, api-krs.ms.gov.pl, Wikidata).
  Bez skrobania X.com (regulamin), bez obchodzenia blokad, robots.txt szanuj.
- Diagnozy Dr. Spina i przekazy dnia: tylko zatwierdź / odrzuć / wygeneruj od nowa, nigdy ręczna edycja treści. Metadane
  (np. kto jest gościem wywiadu) można poprawiać.
- „Twierdzenia, nie osoby”. Dane osobowe zgodnie z RODO art. 14 (zasady w `backend/news/pracownia_osint.py`: LEGAL).
- Testy: `cd backend && python -m pytest <twoje pliki> -q`. Nie psuj istniejących testów.
- Ostatnia wiadomość: najwyżej 15 linii, prostym językiem, z listą komend do uruchomienia na serwerze.
