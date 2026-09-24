<#
Activates only the four public RSS channels reviewed on 2026-09-23.

The import is metadata-only: title, publication date, RSS summary and link to
the original. It does not fetch article HTML, media, attachments or full text.
Every source is re-audited immediately before its access card is created.
#>

param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

function Invoke-Compose {
  param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
  & docker compose @Arguments
  if ($LASTEXITCODE -ne 0) {
    throw "Docker command failed; no subsequent source was started."
  }
}

$sources = @(
  @{ Id = 32; Terms = "https://www.gov.pl/web/gugik/ponowne-wykorzystanie-informacji-sektora-publicznego"; Note = "Geoportal is operated by GUGiK. Metadata-only RSS import with source, dates and processing attribution." },
  @{ Id = 419; Terms = "https://bip.warszawa.wios.gov.pl/bip/ponowne-wykorzystywanie/291%2CPonowne-wykorzystywanie-informacji-sektora-publicznego.html"; Note = "WIOS Warszawa reuse conditions cover BIP and information made available otherwise. Metadata-only RSS import." },
  @{ Id = 575; Terms = "https://bip.olsztyn.eu/37/ponowne-wykorzystywanie-informacji-sektora-publicznego.html"; Note = "Olsztyn BIP reuse conditions cover information published in its BIP. Metadata-only RSS import." },
  @{ Id = 576; Terms = "https://bip.radom.pl/ra/ponowne-wykorzystanie-informac/19412,Zasady-i-tryb-udostepniania.html"; Note = "Radom BIP reuse conditions cover information published in its BIP. Metadata-only RSS import." }
)

foreach ($source in $sources) {
  Invoke-Compose exec backend python manage.py audit_sources --source-id $source.Id --force --workers 1
  Invoke-Compose exec backend python manage.py configure_audited_rss_metadata_source `
    --source-id $source.Id `
    --terms-url $source.Terms `
    --evidence-note $source.Note `
    --reviewed-by $ReviewedBy `
    --daily-cap 24 `
    --apply
  Invoke-Compose exec backend python manage.py fetch_approved_rss_source --source-id $source.Id
}

Invoke-Compose exec backend python manage.py harvester_preflight --approved-only
