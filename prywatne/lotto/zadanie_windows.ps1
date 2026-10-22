# Rejestruje w Harmonogramie zadan Windows dwa zadania automatu Lotto (wirtualne pieniadze).
# Uruchom RAZ, w PowerShell, z folderu prywatne\lotto:
#     powershell -ExecutionPolicy Bypass -File .\zadanie_windows.ps1
# Usuniecie zadan:
#     powershell -ExecutionPolicy Bypass -File .\zadanie_windows.ps1 -Usun
param([switch]$Usun)

$ErrorActionPreference = "Stop"
$Folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$Nazwy = @("Lotto-generuj", "Lotto-sprawdz")

if ($Usun) {
    foreach ($n in $Nazwy) { Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue }
    Write-Host "Usunieto zadania: $($Nazwy -join ', ')"
    exit 0
}

# Python: najpierw launcher py, potem python z PATH
$Py = (Get-Command py.exe -ErrorAction SilentlyContinue).Source
$PyArg = "-3 "
if (-not $Py) { $Py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source; $PyArg = "" }
if (-not $Py) { throw "Nie znaleziono Pythona (py.exe ani python.exe). Zainstaluj Python 3.11+ z python.org." }

function Akcja($polecenie) {
    # cmd /c dopisuje wynik kazdego uruchomienia do automat.log w folderze lotto
    New-ScheduledTaskAction -Execute "cmd.exe" -WorkingDirectory $Folder `
        -Argument "/c `"`"$Py`" $PyArg`"$Folder\lotto.py`" $polecenie >> `"$Folder\automat.log`" 2>&1`""
}

# StartWhenAvailable: gdy komputer byl wylaczony o tej porze, zadanie ruszy po wlaczeniu.
$Ustawienia = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# 1. generuj: we wtorek, czwartek i sobote o 18:00 (przed losowaniem o 22:00)
$Gen = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday, Thursday, Saturday -At "18:00"
Register-ScheduledTask -TaskName "Lotto-generuj" -Action (Akcja "generuj") -Trigger $Gen -Settings $Ustawienia `
    -Description "Lotto (wirtualnie): kupony strategii na najblizsze losowanie" -Force | Out-Null

# 2. sprawdz: po losowaniu o 23:00 oraz rano nastepnego dnia o 9:00 (zalegle, gdy komputer byl wylaczony)
$Wieczor = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday, Thursday, Saturday -At "23:00"
$Rano = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday, Friday, Sunday -At "09:00"
Register-ScheduledTask -TaskName "Lotto-sprawdz" -Action (Akcja "sprawdz") -Trigger @($Wieczor, $Rano) `
    -Settings $Ustawienia -Description "Lotto (wirtualnie): wyniki i wirtualne wygrane do DZIENNIK.csv" -Force | Out-Null

Write-Host "Zarejestrowano: Lotto-generuj (wt/czw/sob 18:00), Lotto-sprawdz (wt/czw/sob 23:00 i sr/pt/nd 9:00)."
Write-Host "Python: $Py   Folder: $Folder   Dziennik uruchomien: $Folder\automat.log"
