[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RepoPath,
    [Parameter(Mandatory = $true)][string]$Subreddits,
    [Parameter(Mandatory = $true)][datetime]$DailyAt,
    [string]$TaskName = "Reddit Pain Finder Daily Research",
    [string]$RunNamePrefix = "scheduled-reddit",
    [int]$MaxThreads = 25,
    [int]$MaxComments = 8
)

$ErrorActionPreference = "Stop"
$Runner = Join-Path $RepoPath "scripts\run-reddit-research.ps1"
if (-not (Test-Path $Runner)) {
    throw "Runner script not found: $Runner"
}

$Arguments = @(
    "-NoProfile",
    "-ExecutionPolicy Bypass",
    "-File `"$Runner`"",
    "-RepoPath `"$RepoPath`"",
    "-Subreddits `"$Subreddits`"",
    "-RunNamePrefix `"$RunNamePrefix`"",
    "-MaxThreads $MaxThreads",
    "-MaxComments $MaxComments"
) -join " "

$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $Arguments
$Trigger = New-ScheduledTaskTrigger -Daily -At $DailyAt
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Bounded public read-only Reddit research with persistent cross-run deduplication." `
    -Force

Write-Host "PASS: registered task '$TaskName' for $($DailyAt.ToString('HH:mm')) daily."
