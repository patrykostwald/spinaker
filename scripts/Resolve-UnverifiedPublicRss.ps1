<#
Closes the five public RSS reviews for which no terms covering the exact feed
were found. This only writes non-operational review decisions and refreshes
reports. It does not send mail, create a source-access card, enable a source,
or download content.
#>

param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

$reviews = @(
  @{
    Host = "policja.pl"
    Reason = "KGP BIP reuse conditions were found, but they do not establish permission for the separate www.policja.pl RSS portal. No exact-channel terms were found."
    Evidence = "https://kgp.bip.policja.gov.pl/kgp/ponowne-wykorzystywani/warunki-ponownego-wyko/11214%2CWarunki-ponownego-wykorzystania-informacji-publicznej.html"
  },
  @{
    Host = "kzgw.gov.pl"
    Reason = "No published reuse terms covering this exact KZGW RSS channel were found in the review. Keep the source inactive pending later confirmation."
    Evidence = "https://kzgw.gov.pl/index.php/pl/?format=feed&type=rss"
  },
  @{
    Host = "imgw.pl"
    Reason = "IMGW public-data terms cover the data portal, not the separate imgw.pl news feed. Terms must not be transferred between those products."
    Evidence = "https://danepubliczne.imgw.pl/"
  },
  @{
    Host = "niw.gov.pl"
    Reason = "No published reuse terms covering the exact NIW RSS channel were found in the review. Keep the source inactive pending later confirmation."
    Evidence = "https://niw.gov.pl/feed/"
  },
  @{
    Host = "bip.opolskie.pl"
    Reason = "No published reuse terms covering the exact BIP Opolskie RSS channel were found in the review. BIP status alone is not an access instruction."
    Evidence = "https://bip.opolskie.pl/feed/"
  }
)

foreach ($review in $reviews) {
  docker compose exec backend python manage.py record_source_review_decision `
    --source-host $review.Host `
    --decision contact_required `
    --reason $review.Reason `
    --evidence-url $review.Evidence `
    --reviewed-by $ReviewedBy `
    --apply
  if ($LASTEXITCODE -ne 0) { throw "Decision was not recorded for $($review.Host)." }
}

docker compose exec backend python manage.py source_verification_register
if ($LASTEXITCODE -ne 0) { throw "Source verification register failed." }

docker compose exec backend python manage.py source_contact_register
if ($LASTEXITCODE -ne 0) { throw "Source contact preparation register failed." }
