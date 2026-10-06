#!/bin/sh
# Zasilanie bazy 6.10: wyższe dzienne limity kart dostępu (przegląd właściciela) i plan dociągania historii.
# Odstęp 3 s między zapytaniami do hosta zostaje; noc 01:00-06:00 i 23:00-24:00 robi zadanie zasil_baze_task samo.
# Uruchamiać z /srv/spin-clinic po wdrożeniu kodu (wdrozenie-0610.sh woła ten skrypt na końcu).
set -eu
cd /srv/spin-clinic
ENV=.env.production
DC="docker compose --env-file $ENV -f deploy/docker-compose.production.yml"
M="$DC exec -T backend python manage.py"

echo '== Zasilanie bazy: karty dostępu z limitem na historię (365 dni ważności)'
cfg() { $M configure_public_records --source "$1" --apply --reviewed-by patrykostwald \
          --evidence-url "$2" --terms-url "$3" --valid-days 365 --daily-cap "$4" | tail -1; }
SEJM_DOC=https://api.sejm.gov.pl/sejm.html
cfg votes "$SEJM_DOC" "$SEJM_DOC" 1500
cfg statements "$SEJM_DOC" "$SEJM_DOC" 2000
cfg interpellations "$SEJM_DOC" "$SEJM_DOC" 500
cfg questions "$SEJM_DOC" "$SEJM_DOC" 500
cfg consultations "$SEJM_DOC" "$SEJM_DOC" 200
cfg processes "$SEJM_DOC" "$SEJM_DOC" 800
cfg committees "$SEJM_DOC" "$SEJM_DOC" 300
cfg assets "$SEJM_DOC" "$SEJM_DOC" 500
cfg krs_changes https://prs.ms.gov.pl/krs/openApi https://prs.ms.gov.pl/krs/openApi 600
cfg ted https://docs.ted.europa.eu/api/latest/index.html https://op.europa.eu/en/web/about-us/legal-notices/eu-law-and-publications-website 400
cfg pkw https://pkw.gov.pl/finansowanie-polityki/ https://pkw.gov.pl/ 200
cfg videos "$SEJM_DOC" "$SEJM_DOC" 1800
cfg howtheyvote https://howtheyvote.eu/api/votes https://howtheyvote.eu/about 1800
cfg mileage https://jakglosuja.pl/dane-otwarte https://creativecommons.org/licenses/by/4.0/ 500

echo '== Zasilanie bazy: plan (bez sieci)'
$M zasil_baze --plan
echo 'Noc 01:00-06:00 i 23:00: zadanie zasil_baze_task dociąga historię samo; gotowe źródła pomija.'
