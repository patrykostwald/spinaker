#!/bin/sh
# Nocna kopia bazy spin.clinic (Z2, przegląd architekta 7.10):
#   pg_dump z kontenera db -> plik lokalny /srv/backups (14 dni) -> zaszyfrowana kopia w Backblaze B2 (30 dni).
# Szyfrowanie (openssl AES-256-CBC, PBKDF2) i wysyłka (API S3, podpis SigV4) robi kontener backend: manage.py kopia_zapasowa.
# Klucze B2 i hasło BACKUP_PASSPHRASE są tylko w .env.production (skrypt wdrożenia generuje hasło raz; właściciel trzyma je
# w menedżerze haseł - bez niego kopii nie da się odczytać). Odtworzenie: docs/KOPIE-I-ODTWORZENIE.md.
# Cron (deploy/wdrozenie-0610.sh dopisuje sam):  30 3 * * * /srv/spin-clinic/deploy/backup.sh >> /srv/backups/backup.log 2>&1
set -eu
cd /srv/spin-clinic
mkdir -p /srv/backups
DC="docker compose --env-file .env.production -f deploy/docker-compose.production.yml"
stamp=$(date +%Y%m%d-%H%M)
name="spin_clinic-$stamp.sql.gz"
file="/srv/backups/$name"
$DC exec -T db pg_dump -U spin -d spin_clinic --no-owner | gzip -9 > "$file"
# Pusta albo uszkodzona kopia = błąd (nie kasujemy wtedy starszych).
[ "$(gzip -cd "$file" | head -c 100 | wc -c)" -gt 0 ] || { echo "$(date) PUSTA KOPIA $file"; rm -f "$file"; exit 1; }
find /srv/backups -name 'spin_clinic-*.sql.gz' -mtime +14 -delete
echo "$(date) OK lokalnie $file $(du -h "$file" | cut -f1)"

if ! grep -q '^B2_BUCKET=.' .env.production; then
  echo "$(date) B2: brak B2_BUCKET w .env.production - kopia tylko na dysku VPS (bez kopii poza serwer!)"
  exit 0
fi
# Baza: szyfrowanie + wysyłka + retencja 30 dni + stan dla Dyżurnego i Raportu pętli.
$DC exec -T backend python manage.py kopia_zapasowa --z-stdin --nazwa "$name" < "$file" \
  || { echo "$(date) B2: wysyłka kopii bazy NIEUDANA (Dyżurny podniesie alarm po 26 h)"; exit 1; }
# Pliki, których nie odtworzy kod (media społecznościowe; karty diagnoz generują się same): raz w tygodniu (niedziela), do 500 MB.
if [ "${BACKUP_MEDIA:-tak}" = tak ] && [ "$(date +%u)" = 7 ]; then
  media="/tmp/media-$stamp.tar.gz"
  $DC exec -T backend sh -c 'cd /app && [ -d media/social ] && tar czf - media/social' > "$media" 2>/dev/null || true
  if [ -s "$media" ] && [ "$(stat -c %s "$media")" -lt 524288000 ]; then
    $DC exec -T backend python manage.py kopia_zapasowa --z-stdin --nazwa "media-$stamp.tar.gz" --rodzaj media < "$media" \
      || echo "$(date) B2: kopia mediów NIEUDANA (baza wysłana)"
  else
    echo "$(date) B2: media pominięte (brak plików albo ponad 500 MB)"
  fi
  rm -f "$media"
fi
