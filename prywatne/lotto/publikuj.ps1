# Publikuje strone eksperymentu Lotto na zbudujmi.com/lotto (kopiuje strona\lotto do folderow zbudujmi i robi wrangler deploy).
# Uruchamiane przez Harmonogram zadan po "generuj" i "sprawdz". Usuniecie zadania: Unregister-ScheduledTask -TaskName Lotto-publikuj
$ErrorActionPreference = "Stop"
$Lotto = Split-Path -Parent $MyInvocation.MyCommand.Path
$Log = Join-Path $Lotto "automat.log"
function Zapisz($t) { Add-Content -Path $Log -Value ("{0} publikuj: {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $t) }
try {
    Set-Location $Lotto
    & py -3 lotto.py strona *>> $Log
    $Src = Join-Path $Lotto "strona\lotto"
    foreach ($Dist in @("C:\Users\User\zbudujmi\wdrozenie\dist\lotto", "C:\Users\User\zbudujmi\dist\lotto")) {
        New-Item -ItemType Directory -Force $Dist | Out-Null
        Copy-Item -Path (Join-Path $Src "*") -Destination $Dist -Force
    }
    Set-Location "C:\Users\User\zbudujmi\wdrozenie"
    & npx wrangler deploy *>> $Log
    Zapisz "ok"
} catch {
    Zapisz ("blad: " + $_.Exception.Message)
}
