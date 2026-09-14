param(
    [int[]]$SourceId = @(),
    [switch]$DynamicSources,
    [ValidateSet('2026-09-14T23:59:59+02:00')][string]$CutoffAt = '2026-09-14T23:59:59+02:00',
    [ValidateRange(1,32)][int]$Workers = 2,
    [ValidateRange(1,100)][int]$LimitPerSource = 20,
    [ValidateRange(0.1,24)][double]$MaxHours = 10,
    [string]$DatabasePath = "$PSScriptRoot\backend\db.sqlite3"
)

$ErrorActionPreference = 'Stop'
$python = @(
    "$PSScriptRoot\.venv\Scripts\python.exe",
    "$PSScriptRoot\backend\.venv\Scripts\python.exe",
    "$PSScriptRoot\..\..\.venv\Scripts\python.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
$pidPath = "$PSScriptRoot\.runtime\harvesters-backfill.pid"
$logPath = "$PSScriptRoot\.runtime\harvesters-backfill.log"
$errorPath = "$PSScriptRoot\.runtime\harvesters-backfill.err.log"
if (-not $python) { throw "Missing Python virtualenv in project root or backend directory." }
if (-not $DynamicSources -and $SourceId.Count -eq 0) { throw "SourceId is required unless -DynamicSources is used." }
if (Test-Path $pidPath) {
    $oldPid = [int](Get-Content $pidPath)
    if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) { throw "Backfill already running with PID $oldPid" }
    Remove-Item $pidPath -Force
}
New-Item -ItemType Directory -Force (Split-Path $pidPath) | Out-Null
$idText = $SourceId -join ','
$runArguments = @('-NoProfile','-ExecutionPolicy','Bypass','-File',"$PSScriptRoot\Run-Harvesters-Backfill.ps1",
    '-CutoffAt',$CutoffAt,'-Workers',$Workers,'-LimitPerSource',$LimitPerSource,
    '-MaxHours',$MaxHours,'-DatabasePath',$DatabasePath)
if ($idText) { $runArguments += @('-SourceIdText', $idText) }
if ($DynamicSources) { $runArguments += '-DynamicSources' }
$process = Start-Process powershell.exe -WindowStyle Hidden -WorkingDirectory "$PSScriptRoot\backend" `
    -ArgumentList $runArguments `
    -RedirectStandardOutput $logPath -RedirectStandardError $errorPath -PassThru
$process.Id | Set-Content $pidPath
$config = @{workers=$Workers; source_count=$SourceId.Count; source_ids=$SourceId; dynamic_sources=[bool]$DynamicSources;
    cutoff_at=$CutoffAt; max_hours=$MaxHours; started_at=(Get-Date).ToString('o')} | ConvertTo-Json
$config | Set-Content "$PSScriptRoot\.runtime\harvesters-backfill.config.json"
Write-Output "Started archive backfill PID $($process.Id), cutoff $CutoffAt, workers $Workers, database $DatabasePath"
