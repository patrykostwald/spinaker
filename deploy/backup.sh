#!/bin/sh
# Nocna kopia bazy spin.clinic: pg_dump z kontenera db, skompresowana, 14 dni wstecz.
# Instalacja (raz, na serwerze):  crontab -e  i dopisz linię:
#   30 3 * * * /srv/spin-clinic/deploy/backup.sh >> /srv/backups/backup.log 2>&1
set -eu
cd /srv/spin-clinic
mkdir -p /srv/backups
file="/srv/backups/spin_clinic-$(date +%Y%m%d-%H%M).sql.gz"
docker compose --env-file .env.production -f deploy/docker-compose.production.yml exec -T db \
  pg_dump -U spin -d spin_clinic --no-owner | gzip -9 > "$file"
# Pusta albo uszkodzona kopia = błąd (nie kasujemy wtedy starszych).
[ "$(gzip -cd "$file" | head -c 100 | wc -c)" -gt 0 ] || { echo "$(date) PUSTA KOPIA $file"; rm -f "$file"; exit 1; }
find /srv/backups -name 'spin_clinic-*.sql.gz' -mtime +14 -delete
echo "$(date) OK $file $(du -h "$file" | cut -f1)"
