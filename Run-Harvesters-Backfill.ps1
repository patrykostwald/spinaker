param(
    [Parameter(Mandatory=$true)][string]$SourceIdText,
    [string]$CutoffAt = '2026-09-14T23:59:59+02:00',
    [int]$Workers = 32,
    [int]$LimitPerSource = 100,
    [double]$MaxHours = 10,
    [Parameter(Mandatory=$true)][string]$DatabasePath
)
$ErrorActionPreference = 'Stop'
$python = 'C:\Users\User\spin-clinic\.venv\Scripts\python.exe'
$env:USE_SQLITE = 'true'
$env:ARCHIVE_STORE_FULL_TEXT = 'false'
$env:SQLITE_DATABASE_PATH = $DatabasePath
$SourceId = $SourceIdText.Split(',') | ForEach-Object { [int]$_ }
$argsList = @('manage.py','backfill_archives_loop')
foreach ($id in $SourceId) { $argsList += @('--source-id', $id.ToString()) }
$argsList += @('--cutoff-at',$CutoffAt,'--workers',$Workers.ToString(),
    '--limit-per-source',$LimitPerSource.ToString(),'--max-hours',$MaxHours.ToString([Globalization.CultureInfo]::InvariantCulture))
& $python @argsList
exit $LASTEXITCODE
