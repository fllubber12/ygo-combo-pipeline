#!/usr/bin/env bash
set -euo pipefail

# Fast/robust modes:
#   HANDOFF_FAST=1        -> fastest reasonable compression + skip zip listings
#   HANDOFF_SKIP_CONTEXT=1 -> do not build the big context zip (still refreshes handoff md)
#   HANDOFF_NO_LIST=1     -> skip unzip -l output (useful for slow terminals)
HANDOFF_FAST="${HANDOFF_FAST:-0}"
HANDOFF_SKIP_CONTEXT="${HANDOFF_SKIP_CONTEXT:-0}"
HANDOFF_NO_LIST="${HANDOFF_NO_LIST:-0}"

zip_opts=()
if [ "$HANDOFF_FAST" = "1" ]; then
  zip_opts+=("-q" "-1")
  HANDOFF_NO_LIST="1"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HANDOFF_MD="ygo_combo_pipeline_handoff_2026-01-20.md"

cd "$REPO_ROOT"

if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

set +e
qa_output="$(python3 -m unittest discover -s tests 2>&1)"
qa_rc=$?
set -e
printf "%s\n" "$qa_output" | tee "$tmp_dir/qa.txt"

set +e
coverage_output="$(python3 scripts/audit_effect_coverage.py 2>&1)"
coverage_rc=$?
set -e
printf "%s\n" "$coverage_output" | tee "$tmp_dir/coverage.txt"

set +e
modeling_output="$(python3 scripts/audit_modeling_status.py --fail 2>&1)"
modeling_rc=$?
set -e
printf "%s\n" "$modeling_output" | tee "$tmp_dir/modeling.txt"

latest_updates="$(ls -1 updates_*.zip 2>/dev/null | sort | tail -n 1 || true)"
if [ -z "$latest_updates" ]; then
  latest_updates="NONE"
fi

ts="$(date +%Y%m%d_%H%M%S)"
entry_ts="$(date +%Y-%m-%d\ %H:%M)"
min_zip="handoff_min_${ts}.zip"
context_zip="handoff_context_${ts}.zip"

export REPO_ROOT
export HANDOFF_MD
export LATEST_UPDATES="$latest_updates"
export ENTRY_TS="$entry_ts"
export MIN_ZIP="$min_zip"
export CONTEXT_ZIP="$context_zip"
export QA_RC="$qa_rc"
export COVERAGE_RC="$coverage_rc"
export MODELING_RC="$modeling_rc"
export QA_OUT="$tmp_dir/qa.txt"
export COVERAGE_OUT="$tmp_dir/coverage.txt"
export MODELING_OUT="$tmp_dir/modeling.txt"

python3 - <<'PY'
from __future__ import annotations

import os
import re
from pathlib import Path

repo_root = Path(os.environ["REPO_ROOT"])
handoff_path = repo_root / os.environ["HANDOFF_MD"]

latest_updates = os.environ["LATEST_UPDATES"]
entry_ts = os.environ["ENTRY_TS"]
min_zip = os.environ["MIN_ZIP"]
context_zip = os.environ["CONTEXT_ZIP"]

qa_rc = int(os.environ["QA_RC"])
coverage_rc = int(os.environ["COVERAGE_RC"])
modeling_rc = int(os.environ["MODELING_RC"])

qa_output = Path(os.environ["QA_OUT"]).read_text(encoding="utf-8")
coverage_output = Path(os.environ["COVERAGE_OUT"]).read_text(encoding="utf-8")
modeling_output = Path(os.environ["MODELING_OUT"]).read_text(encoding="utf-8")

if not handoff_path.exists():
    raise SystemExit(f"Missing handoff md: {handoff_path}")

text = handoff_path.read_text(encoding="utf-8")
lines = text.splitlines()
out: list[str] = []
in_latest = False
replaced = False
for line in lines:
    if line.strip() == "## Latest Diff Zip":
        in_latest = True
        out.append(line)
        continue
    if in_latest:
        if line.startswith("## "):
            if not replaced:
                out.append(f"- `{latest_updates}` (latest diff)")
                replaced = True
            out.append(line)
            in_latest = False
            continue
        if line.strip().startswith("- "):
            if not replaced:
                out.append(f"- `{latest_updates}` (latest diff)")
                replaced = True
            continue
        out.append(line)
        continue
    out.append(line)
if in_latest and not replaced:
    out.append(f"- `{latest_updates}` (latest diff)")

text = "\n".join(out)
if not text.endswith("\n"):
    text += "\n"

missing_match = re.search(r"Missing CIDs \\((\\d+)\\)", coverage_output)
missing_count = missing_match.group(1) if missing_match else "unknown"

modeled_match = re.search(r"Modeled count: (\\d+)", modeling_output)
stub_match = re.search(r"Stub count \\(excluding allowed\\): (\\d+)", modeling_output)
missing_model_match = re.search(r"Missing count: (\\d+)", modeling_output)

modeled_count = modeled_match.group(1) if modeled_match else "unknown"
stub_count = stub_match.group(1) if stub_match else "unknown"
missing_model_count = missing_model_match.group(1) if missing_model_match else "unknown"

entry_lines = [
    f"- Handoff refresh ({entry_ts})",
    f"  - QA: `python3 -m unittest discover -s tests` (exit {qa_rc})",
    f"  - Coverage audit: Missing CIDs ({missing_count}) (exit {coverage_rc})",
    (
        "  - Modeling-status: Modeled "
        f"{modeled_count}, Stub {stub_count}, Missing {missing_model_count} "
        f"(exit {modeling_rc})"
    ),
    f"  - Latest diff zip: `{latest_updates}`",
    f"  - Bundles: `{min_zip}`, `{context_zip}`",
    "  - QA output:",
    "```text",
    qa_output.rstrip(),
    "```",
    "  - Coverage output:",
    "```text",
    coverage_output.rstrip(),
    "```",
    "  - Modeling-status output:",
    "```text",
    modeling_output.rstrip(),
    "```",
]

text += "\n" + "\n".join(entry_lines) + "\n"

handoff_path.write_text(text, encoding="utf-8")
PY

min_files=(
  "$HANDOFF_MD"
  "config"
  "decklists/library.ydk"
  "scripts/audit_effect_coverage.py"
  "scripts/audit_modeling_status.py"
)
if [ "$latest_updates" != "NONE" ]; then
  min_files+=("$latest_updates")
fi

xlsx_files=()
if [ -f "Fiendsmith_Master_Card_Library_CLEAN.xlsx" ]; then
  xlsx_files+=("Fiendsmith_Master_Card_Library_CLEAN.xlsx")
fi
if [ -f "Fiendsmith_Card_Library_CLEAN_TEMPLATE.xlsx" ]; then
  xlsx_files+=("Fiendsmith_Card_Library_CLEAN_TEMPLATE.xlsx")
fi
if [ -d "config" ]; then
  min_files+=("config")
fi

rm -f "$min_zip" "$context_zip"
zip "${zip_opts[@]}" -r "$min_zip" "${min_files[@]}" "${xlsx_files[@]}"

context_items=(
  "src"
  "scripts"
  "tests"
  "decklists"
  "config"
  "$HANDOFF_MD"
)
if [ -f "requirements.txt" ]; then
  context_items+=("requirements.txt")
fi
context_items+=("${xlsx_files[@]}")

if [ "$HANDOFF_SKIP_CONTEXT" = "1" ]; then
  # keep variable for the md entry, but skip the expensive build
  context_zip="SKIPPED"
else
  zip "${zip_opts[@]}" -r "$context_zip" "${context_items[@]}" \
    -x ".venv/*" "venv/*" ".git/*" "__pycache__/*" "*/__pycache__/*" \
    ".pytest_cache/*" "*/.pytest_cache/*" ".mypy_cache/*" "*/.mypy_cache/*" \
    ".ruff_cache/*" "*/.ruff_cache/*" ".DS_Store" "*.DS_Store" "*.pyc" \
    "reports/*" "dist/*" "build/*" "cards.cdb"
fi

ls -la handoff_*.zip
if [ "$HANDOFF_NO_LIST" != "1" ]; then
  unzip -l "$min_zip" | head -80
  if [ "$HANDOFF_SKIP_CONTEXT" != "1" ]; then
    unzip -l "$context_zip" | head -80
  fi
fi

echo
echo "Fresh chat instructions:"
echo "Upload handoff_context_${ts}.zip AND ${HANDOFF_MD} (or just the context zip if it contains the md),"
echo "then paste: \"Read the handoff md first, then continue from 'Next Milestone'.\""

if [ "$qa_rc" -ne 0 ] || [ "$coverage_rc" -ne 0 ] || [ "$modeling_rc" -ne 0 ]; then
  exit 1
fi
