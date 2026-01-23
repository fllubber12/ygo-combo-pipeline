#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"

"$PYTHON_BIN" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo ""
echo "Note: lxml is required for spot-check parsing."
echo "Venv ready. Next:"
echo "  source .venv/bin/activate"
echo "  python scripts/qa/run_qa.py"
