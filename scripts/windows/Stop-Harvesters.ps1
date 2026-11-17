$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pidFile = Join-Path $projectRoot '.runtime\harvesters.pid'

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host 'Brak zapisanego działającego procesu harvesterów.'
    exit 0
}

$harvesterPid = [int](Get-Content -LiteralPath $pidFile -Raw)
$process = Get-Process -Id $harvesterPid -ErrorAction SilentlyContinue
if ($process) {
    Stop-Process -Id $harvesterPid
    Write-Host "Zatrzymano harvestery (PID $harvesterPid)."
}
Remove-Item -LiteralPath $pidFile -Force
