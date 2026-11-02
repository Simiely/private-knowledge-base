#!/usr/bin/env bash
# 质量门禁（R6）：ruff → mypy → pytest，任一失败即非零退出。
# 用法：
#   bash scripts/check.sh
#   PYTHON=.venv/Scripts/python.exe bash scripts/check.sh   # Windows 虚拟环境
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python}"

echo "==> ruff check app tests"
"$PY" -m ruff check app tests

echo "==> mypy app"
"$PY" -m mypy app

echo "==> pytest tests"
"$PY" -m pytest tests -q

echo "ALL CHECKS PASSED"
