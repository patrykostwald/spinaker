#!/bin/sh
# Wdrożenie produkcyjne (spin.clinic + przeszłość.today) na VPS: jedna komenda, zatrzymuje się przy pierwszym błędzie (6.11.2026).
# Uruchamiać z katalogu repozytorium PO pobraniu kodu:  cd /srv/spin-clinic && git pull --ff-only && sh deploy/wdroz.sh
# Kroki: sprawdzenie stanu, kopia bazy (lokalna + zaszyfrowana poza serwer), budowa i start frontend/backend/worker/beat
# (migracje robi start backendu), czekanie na backend, kontrola migracji, przeliczenie Odstępstw, lista usług.
# Używa WYŁĄCZNIE bezpiecznej komendy compose z flagami (zasada właściciela 5.11.2026): nigdy samo `docker compose up`.
set -eu
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"
[ "$ROOT" = "/srv/spin-clinic" ] || { echo "STOP: to nie jest /srv/spin-clinic ($ROOT). Nic nie zrobiono."; exit 1; }
DC="docker compose --env-file .env.production -f deploy/docker-compose.production.yml"
step() { printf '\n=== %s\n' "$1"; }
fail() { printf '\nBŁĄD: %s\nNic więcej nie rób i wklej cały ten wynik.\n' "$1"; exit 1; }

step "1/7 stan repozytorium"
echo "gałąź: $(git rev-parse --abbrev-ref HEAD)"; git log --oneline -1
[ -z "$(git status --porcelain --untracked-files=no)" ] || fail "na serwerze są zmienione pliki śledzone (git status); wdrożenie wstrzymane"

step "2/7 kopia bazy (potrwa kilka minut, nie przerywaj)"
sh deploy/backup.sh || fail "kopia bazy się nie powiodła; wdrożenie wstrzymane (nic nie zmieniono na produkcji)"

step "3/7 budowa i uruchomienie (frontend, backend, worker, beat; kilka minut, strona niedostępna ok. 1-3 minut)"
GIT_COMMIT=$(git rev-parse HEAD); BUILD_TIME=$(date -u +%Y-%m-%dT%H:%M:%SZ); export GIT_COMMIT BUILD_TIME
$DC up -d --build --no-deps frontend backend worker beat || fail "budowa albo start usług nie powiodły się"

step "4/7 czekam, aż backend wstanie po migracjach (do 5 minut)"
i=0
until $DC exec -T backend python manage.py check >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -ge 30 ] && fail "backend nie wstał w 5 minut (logi: $DC logs --tail 40 backend)"; sleep 10
done
echo "backend odpowiada"

step "5/7 migracje"
$DC exec -T backend python manage.py migrate --check >/dev/null 2>&1 || fail "są niezastosowane migracje (migrate --check)"
echo "wszystkie migracje zastosowane"

step "6/7 przeliczenie Odstępstw (kilkadziesiąt sekund)"
$DC exec -T backend python manage.py odstepstwa 2>&1 | head -3 || true

step "7/7 usługi"
$DC ps
printf '\nGOTOWE. Wdrożony commit: '; git log --oneline -1
