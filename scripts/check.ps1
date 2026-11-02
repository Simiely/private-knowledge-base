# 质量门禁（R6，Windows PowerShell）：ruff → mypy → pytest，任一失败即非零退出。
# 用法：.\scripts\check.ps1
#       $env:PYTHON="C:\path\to\python.exe"; .\scripts\check.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$py = if ($env:PYTHON) {
    $env:PYTHON
} elseif (Test-Path ".venv\Scripts\python.exe") {
    ".venv\Scripts\python.exe"
} else {
    "python"
}

"==> ruff check app tests"
& $py -m ruff check app tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

"==> mypy app"
& $py -m mypy app
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

"==> pytest tests"
& $py -m pytest tests -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

"ALL CHECKS PASSED"
