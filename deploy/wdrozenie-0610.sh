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
         PROCESSES COMMITTEES KRS_CHANGES TED EU_TRANSPARENCY VIDEOS HOWTHEYVOTE WIKIDATA KOHESIO FTS INTEGRITY_WATCH MILEAGE; do
  setv "PUBLIC_RECORDS_${f}_ENABLED" true
done
setv BZP_API_ENABLED true
# Raport źródeł 6.10: diagnozy wystąpień z nagrań Sejmu (3 dziennie, 1 USD) i strażnik mediów (Wayback).
# Fakty (Google Fact Check) włączamy dopiero z kluczem: setv FACTCHECK_API_KEY <klucz> i setv FACTCHECK_ENABLED true.
setv SEJM_VIDEO_SPIN_ENABLED true
setv SEJM_VIDEO_SPIN_DAILY 3
setv MEDIA_WATCH_ENABLED true
grep -q '^FACTCHECK_API_KEY=.' "$ENV" && setv FACTCHECK_ENABLED true || echo 'Fakty: brak FACTCHECK_API_KEY - pętla czeka na klucz'
grep -q '^PRZESZLOSC_ENABLED=true' "$ENV" && echo 'PRZESZLOSC_ENABLED: ok' || echo 'UWAGA: brak PRZESZLOSC_ENABLED=true'
grep -q '^SOURCE_MAIL_SMTP_HOST=.' "$ENV" && echo 'SMTP: ok' || echo 'UWAGA: brak SOURCE_MAIL_SMTP_HOST'
# Przegląd architekta 7.10 (Z1-Z3): kopia poza serwer (B2), puls z zewnątrz, kolejka Issues. Wartości wkleja właściciel; tu tylko stan.
for v in B2_KEY_ID B2_APP_KEY B2_BUCKET HEALTHCHECK_URL GITHUB_ISSUES_TOKEN; do
  grep -q "^$v=." "$ENV" && echo "$v: ok" || echo "UWAGA: brak $v w $ENV"
done
if ! grep -q '^BACKUP_PASSPHRASE=.' "$ENV"; then
  echo "BACKUP_PASSPHRASE=$(openssl rand -base64 48 | tr -d '\n=/+')" >> "$ENV"
  echo '!!! NOWE HASŁO KOPII: BACKUP_PASSPHRASE zapisane w .env.production. Zapisz je TERAZ w menedżerze haseł'
  echo '!!! (bez niego kopii w B2 nie da się odczytać): grep ^BACKUP_PASSPHRASE= /srv/spin-clinic/.env.production'
else
  echo 'BACKUP_PASSPHRASE: ok (istnieje; ma być w menedżerze haseł właściciela)'
fi
grep -q '^GITHUB_ISSUES_TOKEN_CREATED=.' "$ENV" || { grep -q '^GITHUB_ISSUES_TOKEN=.' "$ENV" && setv GITHUB_ISSUES_TOKEN_CREATED "$(date +%F)"; } || true
grep -q '^EXPECTED_SERVER_IP=' "$ENV" || setv EXPECTED_SERVER_IP 148.113.242.109

echo '== 2. Budowa i restart'
$DC up -d --build --force-recreate
i=0
until [ "$($M showmigrations 2>/dev/null | grep -c '\[ \]')" = 0 ] && $M showmigrations news >/dev/null 2>&1; do
  i=$((i+1)); [ $i -gt 60 ] && { echo 'Migracje nie przeszły w 5 min - wklej Claude: docker compose logs backend --tail 80'; exit 1; }
  sleep 5
done
echo 'Migracje: ok (wszystkie zastosowane)'

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
cfg videos "$SEJM_DOC" "$SEJM_DOC"
cfg howtheyvote https://howtheyvote.eu/api/votes https://howtheyvote.eu/about
cfg wikidata https://www.wikidata.org/wiki/Wikidata:Data_access https://www.wikidata.org/wiki/Wikidata:Licensing
cfg kohesio https://data.europa.eu/data/datasets/557j-pmg8 https://kohesio.ec.europa.eu/en/faq
cfg fts https://data.europa.eu/data/datasets/fts https://ec.europa.eu/info/legal-notice_en
cfg integrity_watch https://www.integritywatch.eu/about.php https://opendatacommons.org/licenses/odbl/1-0/
cfg mileage https://jakglosuja.pl/dane-otwarte https://creativecommons.org/licenses/by/4.0/
$M configure_bzp_metadata_source --apply --reviewed-by patrykostwald | tail -1

echo '== 4. Porządki i dopięcia'
$M porzadki_petli --wykonaj | tail -5
$M link_public_record_people | tail -3
$M sprint_intake | tail -10

echo '== 5. Podgląd porannego maila alertów przeszłości (bez wysyłki)'
$M przeszlosc_alerts_digest --dry-run | tail -8

echo '== 6. Raport pętli: wysyłka na adres admina'
$M raport_petli --wyslij --raz | tail -40

echo '== 7. Zasilanie bazy: karty z limitem na historię i plan (szczegóły: deploy/zasil-baze.sh)'
sh deploy/zasil-baze.sh

echo '== 8. Kworum Konsylium: powtórka diagnoz bez kworum od 4.10 (opcjonalnie, tylko raz)'
# Podgląd zawsze. Znacznik tylko po prawdziwym przebiegu (status ok albo idle). Poza 2:00-7:00 komenda tylko planuje
# (status deferred) i znacznika NIE stawia - powtórkę zrobi zadanie nocne 2:40 (ostatnie 7 dni, 8 diagnoz na noc).
# Nowa nazwa znacznika: stary (.konsylium-powtorz-0610.done) mógł powstać po samym planowaniu w dzień.
MARK=.konsylium-powtorz-0610-v2.done
$M konsylium_powtorz --od 2026-10-04 --dry-run | head -40
if [ "${POWTORKA:-tak}" = tak ] && [ ! -f "$MARK" ]; then
  OUT=$($M konsylium_powtorz --od 2026-10-04 --limit 8 2>&1) || OUT='{"status": "error"}'
  echo "$OUT" | head -40
  if printf '%s' "$OUT" | grep -q '"status": "\(ok\|idle\)"'; then
    touch "$MARK"; echo 'Powtórka wykonana - znacznik ustawiony'
  else
    echo 'Powtórka nie wykonana teraz (np. poza 2:00-7:00 albo brak kworum) - znacznik nie ustawiony; zrobi ją zadanie nocne 2:40'
  fi
elif [ -f "$MARK" ]; then
  echo "Powtórka pominięta: znacznik $MARK istnieje (usuń go, jeśli powtórka naprawdę się nie odbyła)"
else
  echo 'Powtórka pominięta (POWTORKA=nie)'
fi
echo '== 9. Karty dostępu z limitem 0 (zatwierdzone, ale nic nie przepuszczają)'
$M shell -c "
from django.utils import timezone
from news.models import SourceAccessInstruction as I
q=I.objects.filter(status='approved',daily_request_cap=0)
live=q.filter(valid_until__gt=timezone.now())
print('zatwierdzone z limitem 0:',q.count(),'- w tym ważne:',live.count())
for i in live.select_related('source')[:20]: print('  ',i.source_id,i.source.name[:40],i.channel,i.endpoint[:60])
n=live.update(daily_request_cap=50)
print('ustawiono limit 50/dobę dla:',n)
"
echo '== 10. Kopia poza serwer (B2), puls z zewnątrz, terminy zewnętrzne, kolejka Issues (przegląd architekta 7.10)'
chmod +x deploy/backup.sh
( crontab -l 2>/dev/null | grep -v 'deploy/backup.sh' ; echo '30 3 * * * /srv/spin-clinic/deploy/backup.sh >> /srv/backups/backup.log 2>&1' ) | crontab -
echo "cron kopii: $(crontab -l | grep -c 'deploy/backup.sh') wpis (3:30)"
if grep -q '^B2_BUCKET=.' "$ENV"; then
  echo '-- pierwsza kopia do B2 (rozmiar i „KOPIA OK” poniżej):'
  sh deploy/backup.sh | tail -4
  echo '-- test odtworzenia pierwszej kopii (pobranie, odszyfrowanie, spójność zrzutu):'
  $M kopia_zapasowa --test-odtworzenia | tail -2 || echo 'UWAGA: test odtworzenia nie przeszedł - wklej Claude wynik powyżej'
else
  echo 'B2: pomijam (brak B2_BUCKET) - kopia tylko lokalna, Dyżurny tego nie pilnuje'
fi
echo '-- pierwszy puls do healthchecks.io:'
$M puls_zewnetrzny --raz | tail -2
echo '-- terminy zewnętrzne (domeny, TLS, DNS, salda, token):'
$M terminy_zewnetrzne --sprawdz | tail -40
echo '-- kolejka budowy: zatwierdzone bilety S/M -> GitHub Issues:'
$M shell -c "from news.sprint_github import export_issues; print(export_issues())"
echo '== 11. Media: karty „tylko metadane” dla redakcji z publicznym RSS (właściciel 6.10; najpierw plan, potem zapis; idempotentne)'
$M zatwierdz_media_metadane --plan | tail -30
$M zatwierdz_media_metadane | tail -30
$M shell -c "
from news.models import Source, SourceAccessInstruction as I
media = Source.objects.filter(source_type__in=('portal', 'newspaper', 'rss')).exclude(rss_url='')
print('karty metadanych mediów (tryb media_metadata_only):', I.objects.filter(status='approved', evidence__mode='media_metadata_only').count())
print('media z RSS aktywne:', media.filter(is_active=True, scrape_enabled=True).count(), 'z', media.count())
print('media wciąż bez karty (no_approved_instruction):', media.filter(last_error='no_approved_instruction').count())
print('media pominięte przez robots/TDM:', media.filter(last_error__startswith='robots_').count() + media.filter(last_error__startswith='tdm_').count())
"
echo '== 12. Drzewo przepływu pieniędzy (właściciel 6.10): NIP i REGON podmiotów z API KRS (idempotentne, podmioty z NIP pomijane), potem stan'
$M drzewo_pieniedzy --plan | tail -4
$M drzewo_pieniedzy --identyfikatory --limit 300 | tail -3
$M drzewo_pieniedzy --stan | tail -3
echo '== 13. Poczta (właściciel 6.10): agent czyta skrzynki projektów i odpowiada; idempotentne, nic nie wysyła'
# Wartości wkleja właściciel do .env.production; skrypt pokazuje tylko NAZWY brakujących zmiennych.
# Wysyłka automatyczna dopiero po: setv MAIL_AGENT_AUTOSEND true (domyślnie false: szkice tylko w zestawieniu 7:10).
grep -q '^MAILBOXES=.' "$ENV" || echo 'UWAGA: brak MAILBOXES (np. MAILBOXES=SPIN,PRZESZLOSC,ZBUDUJMI,IAPPLY)'
for box in $(grep '^MAILBOXES=' "$ENV" | cut -d= -f2 | tr ',' ' '); do
  for k in IMAP_HOST IMAP_USER IMAP_PASSWORD SMTP_HOST SMTP_USER SMTP_PASSWORD; do
    grep -q "^MAILBOX_${box}_${k}=." "$ENV" || echo "UWAGA: brak MAILBOX_${box}_${k} w $ENV"
  done
done
grep -q '^MAIL_AGENT_AUTOSEND=' "$ENV" || setv MAIL_AGENT_AUTOSEND false
grep -q '^MAIL_AGENT_DAILY_LIMIT=' "$ENV" || setv MAIL_AGENT_DAILY_LIMIT 20
$M poczta --stan | tail -20
$M poczta --plan | tail -60
echo '== 14. Poczta wychodząca (właściciel 7.10): kolejka listów deploy/poczta-wychodzaca -> kontener; tylko PLAN, ten skrypt nigdy nie wysyła'
# Obraz backendu nie zawiera katalogu deploy/, więc kolejka jest kopiowana do kontenera przy każdym wdrożeniu.
# Wnioski do urzędów mają miejsce {{PODPIS}}: imię i nazwisko oraz funkcję osoby uprawnionej wpisuje właściciel
# do .env.production jako MAIL_OUTBOX_SIGNER (nigdy do repozytorium). Wysyłka tylko ręcznie: $M poczta --wyslij-kolejke
$DC cp deploy/poczta-wychodzaca/. backend:/app/poczta-wychodzaca/
grep -q '^MAIL_OUTBOX_SIGNER=.' "$ENV" || echo 'UWAGA: brak MAIL_OUTBOX_SIGNER="Imię Nazwisko, funkcja" - wnioski do urzędów czekają'
grep -q '^MAIL_OUTBOX_DAILY_LIMIT=' "$ENV" || setv MAIL_OUTBOX_DAILY_LIMIT 10
$M poczta --wyslij-kolejke --plan | tail -80
echo 'GOTOWE'
