<#
Scalanie gałęzi Budowniczych w jedną gałąź integracyjną z testami po każdym kroku (pętla Śledczy-Budowniczy).

Użycie (z katalogu repo, PowerShell 5.1):
  .\scripts\scal_galezie.ps1 -Baza codex/mvp-public-frontend -Cel integracja/runda-2 `
      -Galezie budowniczy/a-r2, budowniczy/b-r2, fable/speed-r2 -Testy news/test_przeszlosc*.py
  .\scripts\scal_galezie.ps1 ... -NaSucho      # tylko sprawdza konflikty (merge --no-commit), nic nie zostawia

Co robi: tworzy gałąź Cel z Bazy (albo wchodzi na istniejącą), scala gałęzie po kolei bez fast-forward,
po każdym scaleniu uruchamia wskazane testy pytest; przy konflikcie albo czerwonych testach zatrzymuje się,
cofa to scalenie (merge --abort / reset do poprzedniego stanu) i wypisuje pliki konfliktowe. Nic nie wypycha.
Wymaga czystego drzewa roboczego (git status bez zmian).
#>
param(
    [Parameter(Mandatory = $true)][string]$Baza,
    [Parameter(Mandatory = $true)][string]$Cel,
    [Parameter(Mandatory = $true)][string[]]$Galezie,
    [string[]]$Testy = @('news/test_przeszlosc.py', 'news/test_przeszlosc_osoba.py', 'news/test_przeszlosc_przeplyw.py'),
    [switch]$NaSucho
)

$ErrorActionPreference = 'Stop'
function Krok($tekst) { Write-Host "`n== $tekst" -ForegroundColor Cyan }

if (git status --porcelain) { throw 'Drzewo robocze ma zmiany - zatwierdź albo odłóż je przed scalaniem.' }

Krok "Gałąź integracyjna $Cel z $Baza"
$istnieje = git branch --list $Cel
if ($istnieje) { git checkout $Cel | Out-Null } else { git checkout -b $Cel $Baza | Out-Null }

$raport = @()
foreach ($galaz in $Galezie) {
    Krok "Scalanie $galaz"
    $przed = git rev-parse HEAD
    $konflikt = $false
    if ($NaSucho) {
        git merge --no-ff --no-commit $galaz 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { $konflikt = $true }
        $pliki = git diff --name-only --diff-filter=U
        git merge --abort 2>$null
        $raport += [pscustomobject]@{ galaz = $galaz; wynik = $(if ($konflikt) { 'KONFLIKT' } else { 'czysto' }); pliki = ($pliki -join ', ') }
        continue
    }
    git merge --no-ff -m "scalenie: $galaz do $Cel" $galaz 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        $pliki = git diff --name-only --diff-filter=U
        git merge --abort 2>$null
        $raport += [pscustomobject]@{ galaz = $galaz; wynik = 'KONFLIKT'; pliki = ($pliki -join ', ') }
        Write-Host "Konflikt w: $($pliki -join ', ') - rozwiąż ręcznie i uruchom ponownie od tej gałęzi." -ForegroundColor Yellow
        break
    }
    Krok "Testy po $galaz"
    Push-Location backend
    python -m pytest @Testy -q -x --no-header -p no:cacheprovider
    $testyOk = ($LASTEXITCODE -eq 0)
    Pop-Location
    if (-not $testyOk) {
        git reset --hard $przed | Out-Null
        $raport += [pscustomobject]@{ galaz = $galaz; wynik = 'TESTY CZERWONE (cofnięto)'; pliki = '' }
        break
    }
    $raport += [pscustomobject]@{ galaz = $galaz; wynik = 'scalono, testy zielone'; pliki = '' }
}

Krok 'Raport'
$raport | Format-Table -AutoSize
Write-Host "Gałąź $Cel na $(git rev-parse --short HEAD). Nic nie wypchnięto; wdrożenie robi właściciel." -ForegroundColor Green
