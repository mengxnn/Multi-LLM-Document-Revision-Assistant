$ErrorActionPreference = "Stop"

.\.venv\Scripts\python.exe .\run_revision.py `
  --source .\inputs\source.example.docx `
  --requirements .\inputs\requirements.example.md `
  --cycles 5 `
  --dry-run
