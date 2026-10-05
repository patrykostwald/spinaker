#!/bin/sh
# Wdrożenie 6.10: pętle (raport, bezpieczniki, sprint, koła), przeszłość sprint 1, nowe źródła,
# odstępstwa, "Ta sama fraza" (ukryta), profil osoby. Uruchamiać z /srv/spin-clinic po git checkout.
# Nie wypisuje wartości z .env.production - tylko nazwy i stan.
set -eu
cd /srv/spin-clinic
ENV=.env.production
ADMIN=patrykostwald@gmail.com
DC="docker compose --env-file $ENV -f deploy/docker-compose.production.yml"
M="$DC exec -T backend python manage.py"

setv() { if grep -q "^$1=" "$ENV"; then sed -i "s|^$1=.*|$1=$2|" "$ENV"; else echo "$1=$2" >> "$ENV"; fi; }

echo '== 1. Adresy admina i flagi źródeł'
setv LOOP_REPORT_EMAIL "$ADMIN"
setv COUNCIL_RECRUITER_EMAIL "$ADMIN"
setv X_POST_ALERT_EMAIL "$ADMIN"
for f in VOTES STATEMENTS INTERPELLATIONS QUESTIONS LOBBY_MSWIA LOBBY_SEJM CONSULTATIONS PKW ASSETS \
         PROCESSES COMMITTEES KRS_CHANGES TED EU_TRANSPARENCY; do
  setv "PUBLIC_RECORDS_${f}_ENABLED" true
done
setv BZP_API_ENABLED true
grep -q '^PRZESZLOSC_ENABLED=true' "$ENV" && echo 'PRZESZLOSC_ENABLED: ok' || echo 'UWAGA: brak PRZESZLOSC_ENABLED=true'
grep -q '^SOURCE_MAIL_SMTP_HOST=.' "$ENV" && echo 'SMTP: ok' || echo 'UWAGA: brak SOURCE_MAIL_SMTP_HOST'

echo '== 2. Budowa i restart'
$DC up -d --build --force-recreate
i=0
until $M showmigrations news 2>/dev/null | grep -q '\[X\] 0146'; do
  i=$((i+1)); [ $i -gt 60 ] && { echo 'Migracje nie przeszły w 5 min - wklej Claude: docker compose logs backend --tail 80'; exit 1; }
  sleep 5
done
echo 'Migracje: ok (do 0146)'

echo '== 3. Karty dostępu źródeł (przegląd właściciela, ważne 365 dni)'
cfg() { $M configure_public_records --source "$1" --apply --reviewed-by patrykostwald \
          --evidence-url "$2" --terms-url "$3" --valid-days 365 | tail -1; }
SEJM_DOC=https://api.sejm.gov.pl/sejm.html
for s in votes statements interpellations questions consultations processes committees assets; do
  cfg "$s" "$SEJM_DOC" "$SEJM_DOC"
done
cfg lobby_sejm https://www.sejm.gov.pl/sejm10.nsf/page.xsp/lobbing "$SEJM_DOC"
cfg lobby_mswia https://www.gov.pl/web/mswia/dzialalnosc-lobbingowa https://www.gov.pl/web/gov/regulamin
cfg pkw https://pkw.gov.pl/finansowanie-polityki/ https://pkw.gov.pl/
cfg krs_changes https://prs.ms.gov.pl/krs/openApi https://prs.ms.gov.pl/krs/openApi
cfg ted https://docs.ted.europa.eu/api/latest/index.html https://op.europa.eu/en/web/about-us/legal-notices/eu-law-and-publications-website
cfg eu_transparency https://data.europa.eu/data/datasets/transparency-register https://ec.europa.eu/info/legal-notice_en
$M configure_bzp_metadata_source --apply --reviewed-by patrykostwald | tail -1

echo '== 4. Porządki i dopięcia'
$M porzadki_petli --wykonaj | tail -5
$M link_public_record_people | tail -3
$M sprint_intake | tail -10

echo '== 5. Podgląd porannego maila alertów przeszłości (bez wysyłki)'
$M przeszlosc_alerts_digest --dry-run | tail -8

echo '== 6. Raport pętli: wysyłka na adres admina'
$M raport_petli --wyslij | tail -40
echo 'GOTOWE'
