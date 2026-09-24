param(
    [string]$Worktree = "$PSScriptRoot\..\spinaker-claude-night",
    [string]$QueueRoot = "$PSScriptRoot\.local\ai-coordination",
    [ValidateRange(1,60)][int]$PollMinutes = 2,
    [ValidateRange(1,12)][int]$MaxHours = 10
)

$ErrorActionPreference = 'Stop'
$inbox = Join-Path $QueueRoot 'claude\inbox'
$running = Join-Path $QueueRoot 'claude\running'
$done = Join-Path $QueueRoot 'claude\done'
$failed = Join-Path $QueueRoot 'claude\failed'
$logs = Join-Path $QueueRoot 'claude\logs'
$stopFile = Join-Path $QueueRoot 'STOP_CLAUDE_QUEUE'
@($inbox,$running,$done,$failed,$logs) | ForEach-Object { New-Item -ItemType Directory -Force $_ | Out-Null }
if (-not (Test-Path $Worktree)) { throw "Claude worktree does not exist: $Worktree" }
$claude = @(
    (Get-Command claude -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    "$env:APPDATA\npm\claude.cmd"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $claude) { throw 'Claude Code is not installed or is not available in PATH.' }

$deadline = (Get-Date).AddHours($MaxHours)
while ((Get-Date) -lt $deadline -and -not (Test-Path $stopFile)) {
    $task = Get-ChildItem $inbox -Filter '*.md' -File | Sort-Object Name | Select-Object -First 1
    if (-not $task) { Start-Sleep -Seconds ($PollMinutes * 60); continue }
    $runningPath = Join-Path $running $task.Name
    Move-Item -LiteralPath $task.FullName -Destination $runningPath
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $output = Join-Path $logs "$($task.BaseName)-$stamp.out.txt"
    $errorOutput = Join-Path $logs "$($task.BaseName)-$stamp.err.txt"
    $policy = @'
Pracujesz jako Claude Code w projekcie spin.clinic. Wykonaj wyłącznie zadanie poniżej.
Nie odczytuj ani nie wypisuj sekretów. Nie zapisuj do produkcyjnego Supabase, nie pushuj, nie kupuj usług i nie uruchamiaj masowego pobierania bez jawnego polecenia w zadaniu. Nie używaj Git i nie twórz commitów; Codex przejrzy i zapisze wynik. Edytuj tylko pliki potrzebne do zadania, uruchom adekwatne testy, a w wyniku podaj testy, zmienione pliki, ryzyka oraz następny krok. Użyj najmniejszego wystarczającego modelu/effortu.

'@
    $prompt = $policy + (Get-Content -LiteralPath $runningPath -Raw)
    Push-Location $Worktree
    try {
        $prompt | & $claude -p --output-format text --max-turns 80 `
            --allowedTools Read Glob Grep Edit Write WebFetch WebSearch `
            'Bash(python:*)' 'Bash(pytest:*)' `
            1> $output 2> $errorOutput
        if ($LASTEXITCODE -eq 0) {
            Move-Item -LiteralPath $runningPath -Destination (Join-Path $done $task.Name)
            & "$PSScriptRoot\Log-AI-Activity.ps1" -Actor Claude `
                -Message "Completed task $($task.BaseName); result: $output"
        } else {
            Move-Item -LiteralPath $runningPath -Destination (Join-Path $failed $task.Name)
            & "$PSScriptRoot\Log-AI-Activity.ps1" -Actor Claude `
                -Message "Failed task $($task.BaseName); inspect: $output"
        }
    } finally {
        Pop-Location
    }
}
