param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectDir,

    [int]$Cycles = 2,

    [ValidateSet("rule", "llm")]
    [string]$SummaryMode = "rule",

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$argsList = @(
    ".\run_revision.py",
    "--continue-project", $ProjectDir,
    "--cycles", $Cycles,
    "--summary-mode", $SummaryMode
)

if ($DryRun) {
    $argsList += "--dry-run"
}

.\.venv\Scripts\python.exe @argsList
