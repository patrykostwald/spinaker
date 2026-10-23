# Raport: Korektor (gałąź `cloud/korektor`, 23.10.2026)

## Skąd się wziął podpis „Andrzej Duda” przy wywiadzie z prezydentem Nawrockim
- Transkrypcję wywiadu robi Gemini (`clinic_interview._transcribe_part`). Prompt kazał mu **samemu rozpoznać gościa i jego
  funkcję**. Model ma wiedzę sprzed 6.08.2025, więc „prezydent w rozmowie” = Andrzej Duda.
- `clinic_interview.process` **nadpisywał** gościa wybranego wcześniej z tytułu filmu (`interview_votes.guest_details`)
  tym, co zwrócił Gemini - bez żadnej kontroli.
- Żaden prompt (transkrypcja, wywiad, diagnozy, przekaz dnia, wątek X, agent KRS) nie znał aktualnych urzędów.
- `scraper/catalog.py` (TWITTER_POLITICIANS) **nie** jest przyczyną: konto @AndrzejDuda jest podpisane „Andrzej Duda”,
  bez urzędu. Uwaga dla gałęzi `cloud/osoby-x`: w tej liście konto `sjnowacka` jest podpisane „Szymon Hołownia” -
  to wygląda na zamianę osób (nie poprawiam - to zakres osoby-x, a nie mam źródła, czyje to konto).

## Co naprawiono (przyczyna, nie tylko objaw)
1. `backend/news/urzedy.py` - rejestr urzędów (stan 23.10.2026): prezydent, premier, marszałkowie, cały rząd,
   kancelarie, przewodniczący partii i klubów; lista byłych (Duda 2015-2025, Hołownia jako marszałek do 18.11.2025, itd.).
   Każdy wpis ma źródło; niepewne mają `pewne=False` ([DP]) i nie trafiają do promptów ani reguł.
2. Blok „Aktualne urzędy na dzień …” w promptach: transkrypcja wywiadu (plus tytuł i kanał filmu jako wskazówka,
   „nie zgaduj gościa”), diagnoza wywiadu, diagnozy wpisów (także Konsylium), przekaz dnia, wątek X, agent KRS.
3. `backend/news/korektor.py` + `manage.py korektor [--dni N] [--napraw] [--wyslij] [--json]`:
   urząd + niewłaściwa osoba (z odmianą, z wyjątkiem „były/ówczesny”, z datą końca kadencji), gość niezgodny z tytułem
   filmu, gość różnie podpisany na jednej stronie, konta X z listy `news/data/osoby_x.csv` (jeśli gałąź osoby-x ją doda),
   puste sekcje profili (KRS, oświadczenia, głosowania posłów, zamówienia spółek z KRS).
4. Bramka przed publikacją: diagnoza z błędem urzędu wraca raz do kolejki (nowa diagnoza z blokiem urzędów), potem czeka
   na człowieka; przekaz dnia z błędem nie zastępuje zapisanego (naprawa co godzinę robi go od nowa); wywiad dnia -
   najpierw poprawka gościa według tytułu i rejestru, potem raz nowa diagnoza z transkrypcji, inaczej wstrzymany (`flagged`).
5. Harmonogram: `korektor-morning` 6:50 (po nocnych zadaniach, przed Raportem pętli 7:05), mail na `LOOP_REPORT_EMAIL`
   raz dziennie. Wpis w LOOPS (pętla „Korektor” i strażnik w pętlach Diagnozy, Wywiad dnia, Przekaz dnia), rejestr agentów,
   kontrakt w Raporcie pętli. Wyłącznik: `KOREKTOR_ENABLED=false`; same raporty bez napraw: `KOREKTOR_NAPRAW=false`.
6. Testy: `backend/news/test_korektor.py` (w tym regresja „Nawrocki podpisany jako Duda” i inne zamiany osób).

## Do potwierdzenia przez koordynatora ([DP])
- Strony gov.pl, sejm.gov.pl i senat.gov.pl nie otwierały się z chmury; skład rządu potwierdzony w mediach
  (rekonstrukcja 24.07.2025, brak zmian do 22.10.2026). Proszę rzucić okiem na `URZEDY` z https://www.gov.pl/web/premier/sklad-rady.
- Polska 2050: 22.10.2026 Pełczyńska-Nałęcz ogłosiła przekazanie przewodnictwa Hołowni - wpis [DP].
- Przewodniczący klubów (poza Hołownią) i liderzy Konfederacji - [DP], do potwierdzenia na kluby.sejm.gov.pl.
- Domański: wniosek o wicepremiera czeka na decyzję prezydenta - po decyzji zmienić wpis `finanse`.

## Komendy na serwerze (w tej kolejności)
1. `git pull` gałęzi po scaleniu, restart aplikacji, Celery i beat (nowe zadanie `korektor_task`; migracji brak).
2. `python manage.py korektor --dni 7` - sam raport, bez zmian; obejrzeć listę.
3. `python manage.py korektor --dni 7 --napraw --wyslij` - poprawki gościa wywiadu, wstrzymanie i ponowne wygenerowanie
   treści z błędem urzędu, mail z raportem.
4. Dalej automatycznie codziennie o 6:50.
