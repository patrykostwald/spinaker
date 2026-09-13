param(
    [ValidateRange(1, 64)]
    [int]$Workers = 4
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$manage = Join-Path $projectRoot 'backend\manage.py'
$runtime = Join-Path $projectRoot '.runtime'
$pidFile = Join-Path $runtime 'harvesters.pid'
$stdoutLog = Join-Path $runtime 'harvesters.out.log'
$stderrLog = Join-Path $runtime 'harvesters.err.log'

if (-not (Test-Path -LiteralPath $python)) { throw 'Brak lokalnego środowiska Python .venv.' }
if (-not (Test-Path -LiteralPath $manage)) { throw 'Brak backend/manage.py.' }
New-Item -ItemType Directory -Path $runtime -Force | Out-Null

if (Test-Path -LiteralPath $pidFile) {
    $oldPid = [int](Get-Content -LiteralPath $pidFile -Raw)
    if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) {
        Write-Host "Harvestery już działają (PID $oldPid)."
        exit 0
    }
    Remove-Item -LiteralPath $pidFile -Force
}

$env:USE_SQLITE = 'true'
$env:DJANGO_DEBUG = 'true'
$env:ARCHIVE_WORKERS = $Workers.ToString()
$env:ARCHIVE_STORE_FULL_TEXT = 'false'

$process = Start-Process -FilePath $python `
    -ArgumentList @($manage, 'run_local_jobs') `
    -WorkingDirectory (Join-Path $projectRoot 'backend') `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -WindowStyle Hidden `
    -PassThru

Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ascii
Write-Host "Uruchomiono harvestery metadanych (PID $($process.Id), $Workers wykonawców archiwum)."
Write-Host "Log: $stdoutLog"
Write-Host 'Pełne teksty są wyłączone; zbierane są metadane potrzebne do Boxów.'
