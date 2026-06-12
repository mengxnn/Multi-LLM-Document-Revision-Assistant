param(
  [ValidateSet("rule", "llm")]
  [string]$SummaryMode = "rule"
)

$ErrorActionPreference = "Stop"

.\.venv\Scripts\python.exe .\run_revision.py `
  --cycles 3 `
  --summary-mode $SummaryMode
