# Wdrożenie 23.10 - gałąź `cloud/integracja-2310`

Zawiera: `cloud/osoby-x` (Strażnik kont X, lista `osoby_x.csv`), `cloud/korektor` (urzędy i osoby, poranny raport),
`cloud/przeszlosc-rozwoj` (kolejka KRS, przepływy pieniędzy, Stan danych) i poprawki integracji (P0-11, P0-12, P0-13,
konflikty Strażnika w raporcie Korektora, katalog X bez `sjnowacka`). Raport: `INTEGRACJA_RAPORT.md`.

Wszystkie komendy na serwerze z `/srv/spin-clinic`, jak w `deploy/wdrozenie-0610.sh`:

```sh
cd /srv/spin-clinic
ENV=.env.production
DC="docker compose --env-file $ENV -f deploy/docker-compose.production.yml"
M="$DC exec -T backend python manage.py"
```

## 1. Kopia i kod
```sh
sh deploy/backup.sh                       # kopia bazy przed migracjami
git fetch origin && git checkout cloud/integracja-2310 && git pull
```

## 2. Zmienne środowiskowe (wartości domyślne w kodzie - dopisz tylko, gdy chcesz inne)
| Zmienna | Domyślnie | Co robi |
|---|---|---|
| `KOREKTOR_ENABLED` | true | poranny Korektor (6:50) |
| `KOREKTOR_NAPRAW` | true | Korektor poprawia gościa wywiadu i wstrzymuje treść z błędem urzędu (treści nie edytuje) |
| `LOOP_REPORT_EMAIL` | - | odbiorca maila Korektora (ten sam co Raport pętli; już ustawiony 6.10) |
| `WARDEN_SECOND_KEY_ENABLED` | true | Drugi klucz Strażnika (automatyczne rozstrzyganie kolejki kont) |
| `X_POLITICAL_MONTHLY_USD_LIMIT` | 5 w kodzie, **na produkcji 100** | twardy limit kosztu X - **nie zmieniać** (patrz koszt niżej) |
| `KRS_POKRYCIE_ENABLED` | true | nocna kolejka KRS (1:47) |
| `KRS_POKRYCIE_LIMIT` | 200 | odpisów KRS na noc |
| `KRS_POKRYCIE_DNI` | 90 | po ilu dniach odświeżać odpis / ponowić „brak KRS dla NIP” |
| `KRS_POKRYCIE_ODSTEP` | 1 | sekundy między zapytaniami do api-krs |
| `KRS_AGENT_ENABLED` | jak dotąd | agent KRS (imiennicy: potwierdza tylko z przeczytanym źródłem) |
| `PRZESZLOSC_NIW_AUTO`, `PRZESZLOSC_OPP_AUTO` | true | NIW i 1,5% OPP co niedzielę |
| `PUBLIC_RECORDS_TED_ENABLED`, `PUBLIC_RECORDS_FTS_ENABLED` | false w kodzie, true na produkcji od 6.10 | źródła przepływów pieniędzy |

Sprawdzenie bez wypisywania wartości:
```sh
for v in LOOP_REPORT_EMAIL X_POLITICAL_MONTHLY_USD_LIMIT PRZESZLOSC_ENABLED PUBLIC_RECORDS_TED_ENABLED PUBLIC_RECORDS_FTS_ENABLED; do
  grep -q "^$v=." "$ENV" && echo "$v: ok" || echo "UWAGA: brak $v"; done
```

## 3. Budowa, migracje, restart
```sh
$DC build backend worker beat frontend
$DC run --rm backend python manage.py migrate --noinput   # 0170_konta_oboz_inni_zespol, 0171_krs_kolejka
$DC up -d backend worker beat frontend
$M showmigrations news | tail -3                           # [X] 0170..., [X] 0171_krs_kolejka
```
Migracje: `0170` zmienia tylko listy wyborów (obóz „Inni i niezrzeszeni”, „zespół” zamiast „redakcja”), `0171` dodaje tabelę
kolejki KRS. Obie bez zmian istniejących danych.

## 4. Pierwsze komendy kontrolne
```sh
$M korektor --dni 7                     # sam raport, bez zmian; sekcja „Konta X” ma też konflikty Strażnika z ostatniej nocy
$M osoby_x_pokrycie                     # ile osób bez konta, kolejka, koszt „gdyby wszystkie dostały konto”
$M przeszlosc_krs_pokrycie --json       # pokrycie KRS i stan kolejki
curl -s https://przeszlosc.today/api/przeszlosc/stan-danych/ | head -c 600   # Stan danych (też /przeszlosc/dane)
```
Gdy raport Korektora wygląda dobrze: `$M korektor --dni 7 --napraw --wyslij` (dalej sam codziennie o 6:50).

## 5. Koszt nowych kont X
Lista zweryfikowana `osoby_x.csv`: 78 kont z oficjalnym źródłem. Na konto miesięcznie ok. 0,34 USD przy 2 wpisach dziennie
(średnia wpisów x 30 x 0,005 USD + kontrola profilu co 7 dni). **Górna granica: ok. 27 USD/miesiąc**, jeśli żadne z 78 kont nie
jest jeszcze czytane; faktycznie mniej (część już przypięta) - dokładną liczbę z danych produkcji podaje `osoby_x_pokrycie`.
Przy ok. 80 USD wydanych w październiku i limicie 100 USD: w listopadzie suma może dojść do ok. 105 USD - wtedy Strażnik sam
wydłuża odstępy czytania (wpisy przychodzą rzadziej, nic nie przestaje działać). Limitu w kodzie nie zmieniamy; decyzja o
podniesieniu na produkcji należy do właściciela.

## 6. Co sprawdzić po wdrożeniu (pierwsza noc i rano)
- Celery beat: są `account-warden-nightly`, `korektor-morning`, `krs-pokrycie-night`, `przeszlosc-niw-weekly`, `przeszlosc-opp-weekly`
  (`$DC logs beat --since 10m | grep -E "korektor|krs-pokrycie|warden"`).
- Rano mail Korektora: błędy urzędów, konta X, konflikty dowodów z propozycją, puste sekcje profili.
- `przeszlosc_krs_pokrycie --json`: `kolejka.wedlug_stanu.ok` > 0 po pierwszej nocy; błędy < 5%.
- `/przeszlosc/dane`: sekcja „Zbiory na profilach” (głosowania, oświadczenia, RCL, wpisy X, KRS, wzmianki) z liczbami > 0.
- Profil spółki (np. Orlen): boksy „Wygrane zamówienia”, „Dotacje i 1,5% podatku”, „Udzielone zamówienia” - nigdzie słowa „Wpływy”.
- Relacje KRS potwierdzone po wdrożeniu: każda z przeczytanym źródłem albo z odpisem KRS (w panelu: `evidence_note`).

## 7. Wycofanie
```sh
$DC stop beat                                              # najpierw harmonogram
$M migrate news 0169_rcl_legislacja                        # cofa 0171 i 0170 (tabela kolejki KRS znika; dane źródłowe zostają)
git checkout <poprzedni commit produkcji> && $DC build backend worker beat frontend && $DC up -d
```
Szybsze, bez cofania kodu: `KOREKTOR_ENABLED=false`, `KRS_POKRYCIE_ENABLED=false`, `WARDEN_SECOND_KEY_ENABLED=false`
w `.env.production` i `$DC up -d backend worker beat`.
