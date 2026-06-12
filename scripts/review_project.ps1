param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDir,

    [ValidateSet("accept", "continue", "abandon", "skip")]
    [string]$Decision,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$argsList = @(
    ".\run_revision.py",
    "--review-project", $ProjectDir
)

if ($Decision) {
    $argsList += @("--decision", $Decision)
}

if ($DryRun) {
    $argsList += "--dry-run"
}

.\.venv\Scripts\python.exe @argsList
