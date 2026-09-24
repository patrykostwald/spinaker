$ErrorActionPreference = 'Stop'
$portalRoot = $PSScriptRoot
$portalPython = Join-Path $portalRoot '.venv\Scripts\python.exe'
$portalNext = Join-Path $portalRoot 'frontend-spin\node_modules\next\dist\bin\next'
$portalLogs = Join-Path $portalRoot '.local'
if (-not (Test-Path -LiteralPath $portalPython)) { throw 'Brak środowiska Python. Zobacz README.md.' }
if (-not (Test-Path -LiteralPath $portalNext)) { throw 'Brak zależności frontendu. Uruchom pnpm install.' }
if (-not (Test-Path -LiteralPath (Join-Path $portalRoot 'frontend-spin\.next\BUILD_ID'))) { throw 'Najpierw zbuduj frontend: corepack pnpm build:spin.' }
$portalNodeCommand = Get-Command node -ErrorAction SilentlyContinue
$portalNode = if ($portalNodeCommand) { $portalNodeCommand.Source } else { Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' }
if (-not (Test-Path -LiteralPath $portalNode)) { throw 'Brak Node.js. Zobacz README.md.' }
New-Item -ItemType Directory -Path $portalLogs -Force | Out-Null
$env:USE_SQLITE = 'true'
$env:DJANGO_DEBUG = 'true'

function Test-PortalEndpoint([string]$Address) {
    try { return (Invoke-WebRequest -Uri $Address -TimeoutSec 3).StatusCode -eq 200 } catch { return $false }
}

if (-not (Test-PortalEndpoint 'http://127.0.0.1:8000/api/health/')) {
    Start-Process -FilePath $portalPython -ArgumentList @('-X', 'utf8', 'manage.py', 'runserver', '127.0.0.1:8000', '--noreload') -WorkingDirectory (Join-Path $portalRoot 'backend') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $portalLogs 'backend.log') -RedirectStandardError (Join-Path $portalLogs 'backend-error.log') | Out-Null
}
if (-not (Test-PortalEndpoint 'http://localhost:3000')) {
    Start-Process -FilePath $portalNode -ArgumentList @('node_modules/next/dist/bin/next', 'start', '-p', '3000', '-H', '127.0.0.1') -WorkingDirectory (Join-Path $portalRoot 'frontend-spin') -WindowStyle Hidden -RedirectStandardOutput (Join-Path $portalLogs 'frontend.log') -RedirectStandardError (Join-Path $portalLogs 'frontend-error.log') | Out-Null
}
Write-Host 'Portal: http://localhost:3000'
Write-Host 'Redakcja: http://localhost:3000/editor'
Write-Host 'Lokalne dane logowania, jeśli utworzono je automatycznie: .local/admin-login.txt'
Write-Host 'Ten podgląd nie uruchamia harmonogramu pobierania. Instrukcja pełnego środowiska: docs/DEPLOYMENT.md.'
