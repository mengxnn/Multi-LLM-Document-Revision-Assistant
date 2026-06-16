param(
  [ValidateSet("rule", "llm")]
  [string]$SummaryMode = "rule"
)

$ErrorActionPreference = "Stop"

.\.venv\Scripts\python.exe .\run_revision.py `
  --cycles 2 `
  --summary-mode $SummaryMode
