<#
Starts the independent official RSS wave: URE and GIW are pre-reviewed;
UOKiK still must pass its fresh audit before a card can be created.
#>
param([string]$ReviewedBy = "redakcja spin.clinic")

$ErrorActionPreference = "Stop"

& "$PSScriptRoot\Start-ApprovedUreRss.ps1" -ReviewedBy $ReviewedBy
& "$PSScriptRoot\Start-ApprovedGiwRss.ps1" -ReviewedBy $ReviewedBy
& "$PSScriptRoot\Start-ApprovedUokikRss.ps1" -ReviewedBy $ReviewedBy
