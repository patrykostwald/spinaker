param([int[]]$SourceId)
$ErrorActionPreference = 'Stop'
$python = "$PSScriptRoot\backend\.venv\Scripts\python.exe"
$env:USE_SQLITE = 'true'
$env:ARCHIVE_STORE_FULL_TEXT = 'false'
$ids = if ($SourceId) { $SourceId | ForEach-Object { "--source-id $_" } } else { @() }
& $python "$PSScriptRoot\backend\manage.py" backfill_status @ids
if (Test-Path "$PSScriptRoot\.runtime\harvesters-backfill.log") {
    Get-Content "$PSScriptRoot\.runtime\harvesters-backfill.log" -Tail 20
}