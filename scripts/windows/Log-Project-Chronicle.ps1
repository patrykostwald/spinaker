param(
    [ValidateSet('Patryk','Codex','Claude','Mistral','System')][string]$Actor,
    [Parameter(Mandatory=$true)][string]$Event,
    [string]$Why = '',
    [string]$Result = ''
)
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path  # scripts/windows -> repository root
$path = Join-Path $RepoRoot 'docs\PROJECT_CHRONICLE.md'
$clean = { param($value) (($value -replace "[`r`n]+", ' ').Trim()) }
$line = "- **$(Get-Date -Format 'yyyy-MM-dd HH:mm') · $Actor:** $(& $clean $Event)"
if ($Why) { $line += " Powód: $(& $clean $Why)" }
if ($Result) { $line += " Wynik: $(& $clean $Result)" }
Add-Content -Encoding utf8 $path $line
& "$PSScriptRoot\Log-AI-Activity.ps1" -Actor $(if ($Actor -eq 'Patryk' -or $Actor -eq 'System') {'Codex'} else {$Actor}) -Message $Event
