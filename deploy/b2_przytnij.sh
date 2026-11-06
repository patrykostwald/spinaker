#!/bin/sh
# Przycina kopie w Backblaze B2: zostaje N najnowszych w każdym katalogu (pg/, media/, glosy/), reszta (też ukryte wersje) jest kasowana.
# Domyślnie TYLKO RAPORT. Skasowanie: sh deploy/b2_przytnij.sh --apply [N]   (N domyślnie 2). Klucze B2 czyta z .env.production, nie wypisuje ich.
# Uwaga: kasowanie jest nieodwracalne; zostawia tylko N kopii poza serwerem. Przy włączonym Object Lock część wersji może zostać odrzucona (skrypt to zgłosi).
set -eu
cd /srv/spin-clinic
apply=no; keep=2
for a in "$@"; do case "$a" in --apply) apply=yes ;; ''|*[!0-9]*) ;; *) keep="$a" ;; esac; done
val() { grep "^$1=" .env.production | head -1 | cut -d= -f2- | sed "s/^['\"]//; s/['\"]$//"; }
KEY=$(val B2_KEY_ID); SECRET=$(val B2_APP_KEY); BUCKET=$(val B2_BUCKET); REGION=$(val B2_REGION); REGION=${REGION:-eu-central-003}
[ -n "$KEY" ] && [ -n "$SECRET" ] && [ -n "$BUCKET" ] || { echo "Brak B2_KEY_ID/B2_APP_KEY/B2_BUCKET w .env.production"; exit 1; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
aws() { docker run --rm -v "$tmp":/w -e AWS_ACCESS_KEY_ID="$KEY" -e AWS_SECRET_ACCESS_KEY="$SECRET" amazon/aws-cli --endpoint-url "https://s3.$REGION.backblazeb2.com" "$@"; }
echo "=== lista wersji w koszyku"
aws s3api list-object-versions --bucket "$BUCKET" --output json > "$tmp/versions.json"
python3 deploy/b2_przytnij.py "$tmp/versions.json" "$keep" "$tmp/del.json"
[ "$apply" = yes ] || { echo "Tryb raportu: nic nie skasowano. Aby skasować: sh deploy/b2_przytnij.sh --apply $keep"; exit 0; }
total=$(python3 -c "import json;print(len(json.load(open('$tmp/del.json'))['Objects']))")
[ "$total" -gt 0 ] || { echo "Nie ma czego kasować."; exit 0; }
echo "=== kasowanie $total wersji (partiami po 500)"
python3 - "$tmp" <<'PY'
import json, sys
d = json.load(open(sys.argv[1] + '/del.json'))['Objects']
for i in range(0, len(d), 500):
    json.dump({'Objects': d[i:i + 500], 'Quiet': True}, open(f'{sys.argv[1]}/b{i // 500:04d}.json', 'w'))
PY
errors=0
for f in "$tmp"/b*.json; do
  rm -f "$tmp/out.json"; : > "$tmp/out.json"
  aws s3api delete-objects --bucket "$BUCKET" --delete "file:///w/$(basename "$f")" --output json > "$tmp/out.json" || errors=$((errors + 1))
  python3 -c "
import json
t = open('$tmp/out.json').read().strip()
e = (json.loads(t).get('Errors') or []) if t else []   # tryb cichy: pusta odpowiedź = bez błędów
print('błędy:', len(e), (e[0]['Code'] if e else ''))"
done
echo "GOTOWE. Partie z błędem: $errors. Sprawdź koszyk w panelu Backblaze (Buckets: Current Size)."
