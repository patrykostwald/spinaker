# Kopie poza serwer i odtworzenie na nowym VPS (Z2, przegląd architekta 7.10)

## Jak działa kopia

| Krok | Kiedy | Co | Gdzie zapis |
|---|---|---|---|
| `deploy/backup.sh` (cron na serwerze) | 3:30 co noc | `pg_dump` z kontenera `db` -> `/srv/backups/spin_clinic-RRRRMMDD-GGMM.sql.gz` (14 dni lokalnie) | dysk VPS |
| `manage.py kopia_zapasowa --z-stdin` (w skrypcie) | zaraz po zrzucie | szyfrowanie `openssl enc -aes-256-cbc -pbkdf2 -iter 200000` hasłem `BACKUP_PASSPHRASE`, wysyłka do Backblaze B2 (API S3, podpis SigV4 bez boto3), usunięcie obiektów starszych niż 30 dni, rozmiar koszyka | B2: `pg/<plik>.enc`; stan w `RepairerState['kopia-zapasowa']` |
| media (`media/social`) | niedziela | tylko gdy poniżej 500 MB (karty diagnoz generują się same, nie kopiujemy) | B2: `media/<plik>.enc` |
| `kopia_task` (Celery) | 4:30 co dzień | czy w B2 jest kopia z ostatnich 26 h, retencja, rozmiar (alarm ponad 8 GB; darmowe 10 GB) | Raport pętli: „Kopia: lokalna HH:MM, zdalna HH:MM, test odtworzenia DD.MM ok” |
| test odtworzenia | 1. dnia miesiąca (i po pierwszej kopii) | pobranie ostatniej kopii, odszyfrowanie, rozpakowanie, sprawdzenie nagłówka, stopki „dump complete” i liczby tabel wobec bieżącej bazy (>= 90%) | stan + Raport pętli; nieudany = alarm krytyczny Dyżurnego |
| Dyżurny `check_backup` | co 5 min, bez sieci | kopia zdalna starsza niż 26 h = alarm krytyczny (mail od razu) | panel, mail |

Zmienne w `.env.production` (wkleja właściciel, skrypt nigdy ich nie wypisuje): `B2_KEY_ID`, `B2_APP_KEY`, `B2_BUCKET`
(opcjonalnie `B2_REGION`, domyślnie `eu-central-003`, i `B2_ENDPOINT`), `BACKUP_PASSPHRASE` (generuje raz
`deploy/wdrozenie-0610.sh`; **właściciel zapisuje je w menedżerze haseł** - bez hasła kopie są bezużyteczne).

Polecenia: `manage.py kopia_zapasowa` (stan), `--lista` (obiekty w B2), `--kontrola`, `--test-odtworzenia`.

## Odtworzenie na nowym VPS - krok po kroku

Potrzebne z menedżera haseł: `BACKUP_PASSPHRASE`, klucze B2 (`B2_KEY_ID`, `B2_APP_KEY`, nazwa koszyka), pełny `.env.production`
(albo przynajmniej: `POSTGRES_PASSWORD`, `DJANGO_SECRET_KEY`, klucze dostawców), dostęp do DNS domen.

1. **Serwer**: Ubuntu 22.04+, `sudo apt install -y docker.io docker-compose-v2 git openssl curl` i użytkownik w grupie `docker`.
2. **Kod**: `git clone https://github.com/patrykostwald/spinaker /srv/spin-clinic && cd /srv/spin-clinic && git checkout codex/mvp-public-frontend`
   (gałąź z ostatniego wdrożenia; sprawdź w Raporcie pętli albo w `docs/PROGRESS.md`).
3. **Konfiguracja**: wklej `.env.production` z menedżera haseł do `/srv/spin-clinic/.env.production` (`chmod 600`).
   Jeśli pliku nie ma, odtwórz z `backend/.env.example` i uzupełnij sekrety. `POSTGRES_PASSWORD` musi być takie samo
   jak w kopii, inaczej baza wstanie pusta z nowym hasłem (to nie problem: kopia nadpisze dane, hasło zostaje nowe).
4. **Baza i usługi bez ruchu**: `docker compose --env-file .env.production -f deploy/docker-compose.production.yml up -d db redis`
   i poczekaj na `pg_isready` (`docker compose ... exec db pg_isready -U spin`).
5. **Pobranie ostatniej kopii z B2** (na serwerze, bez kontenera backend, bo jeszcze nie działa):
   ```sh
   export B2_KEY_ID=... B2_APP_KEY=... B2_BUCKET=... B2_REGION=eu-central-003
   # lista: najnowszy plik pg/
   docker run --rm -e AWS_ACCESS_KEY_ID=$B2_KEY_ID -e AWS_SECRET_ACCESS_KEY=$B2_APP_KEY amazon/aws-cli \
     --endpoint-url https://s3.$B2_REGION.backblazeb2.com s3 ls s3://$B2_BUCKET/pg/ | sort | tail -3
   docker run --rm -v /srv/backups:/out -e AWS_ACCESS_KEY_ID=$B2_KEY_ID -e AWS_SECRET_ACCESS_KEY=$B2_APP_KEY amazon/aws-cli \
     --endpoint-url https://s3.$B2_REGION.backblazeb2.com s3 cp s3://$B2_BUCKET/pg/<PLIK>.enc /out/<PLIK>.enc
   ```
   (Alternatywa po uruchomieniu backendu: `manage.py kopia_zapasowa --lista`; pobranie robi `--test-odtworzenia`.)
6. **Odszyfrowanie** (hasło przez zmienną, nie w linii poleceń):
   ```sh
   export BACKUP_PASSPHRASE='<z menedżera haseł>'
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_PASSPHRASE -in /srv/backups/<PLIK>.enc -out /srv/backups/<PLIK>
   gzip -t /srv/backups/<PLIK> && gzip -cd /srv/backups/<PLIK> | tail -3   # ma być „PostgreSQL database dump complete”
   ```
7. **Wgranie do bazy** (pusta baza `spin_clinic` z kroku 4):
   ```sh
   DC="docker compose --env-file .env.production -f deploy/docker-compose.production.yml"
   gzip -cd /srv/backups/<PLIK> | $DC exec -T db psql -U spin -d spin_clinic -v ON_ERROR_STOP=1 -q
   $DC exec -T db psql -U spin -d spin_clinic -c "select count(*) from news_spindiagnosis;"   # liczba diagnoz jak w Raporcie pętli
   ```
   Jeśli baza nie była pusta: `$DC exec -T db psql -U spin -d postgres -c "drop database spin_clinic; create database spin_clinic owner spin;"` i powtórz.
8. **Media** (gdy była kopia `media/`): pobierz i odszyfruj jak wyżej, potem
   `$DC run --rm -T backend sh -c 'cd /app && tar xzf -' < /srv/backups/media-<DATA>.tar.gz`.
9. **Reszta usług i migracje**: `$DC up -d --build` (backend wykona `migrate` - kopia może być sprzed ostatniej migracji, to w porządku),
   potem `sh deploy/wdrozenie-0610.sh` (flagi, karty dostępu, cron kopii, pierwsza kopia z nowego serwera, puls, terminy).
10. **DNS i kontrola**: rekordy A `spin.clinic` i `przeszlosc.today` na nowy adres (ustaw też `EXPECTED_SERVER_IP` w `.env.production`),
    Caddy pobierze certyfikaty sam; `manage.py terminy_zewnetrzne --sprawdz`, `manage.py raport_petli`, `manage.py stan_bledow`.
    Pierwsza nocna kopia z nowego serwera potwierdza, że pętla zamknęła się na nowo (Raport pętli: „Kopia: zdalna HH:MM”).

## Test odtworzenia bez przerwy w pracy (co miesiąc robi to zadanie; ręcznie tak samo)

`manage.py kopia_zapasowa --test-odtworzenia` - pobiera ostatnią kopię, odszyfrowuje, rozpakowuje i sprawdza spójność.
Pełna próba na drugiej bazie (raz na kwartał, 10 min):
```sh
DC="docker compose --env-file .env.production -f deploy/docker-compose.production.yml"
$DC exec -T db psql -U spin -d postgres -c "create database restore_test owner spin;"
gzip -cd /srv/backups/<OSTATNI>.sql.gz | $DC exec -T db psql -U spin -d restore_test -v ON_ERROR_STOP=1 -q
$DC exec -T db psql -U spin -d restore_test -c "select count(*) from news_spindiagnosis;"
$DC exec -T db psql -U spin -d postgres -c "drop database restore_test;"
```

## Co pilnuje, że to działa

- Dyżurny: `backup:stale` (krytyczny, > 26 h), `backup:restore-test` (krytyczny), `backup:size` (ostrzeżenie, > 8 GB).
- Raport pętli, sekcja „Kopia, puls i terminy zewnętrzne”; kontrakt `kopia` (wynik = udana kopia zdalna, rytm 24 h).
- Puls z zewnątrz (healthchecks.io) zauważy martwy serwer, beat albo worker - wtedy kopia też nie powstanie i właściciel dostaje
  wiadomość od serwisu zewnętrznego, nie od Dyżurnego, który już nie działa.
