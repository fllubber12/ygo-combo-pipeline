#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: scripts/run_loop.sh [--zip-name NAME] [--handoff PATH] [--files FILE...]

Runs the standard iteration loop:
  - QA (tests + audits if present)
  - updates-only zip from FILES (or git status)
  - optional handoff log entry

Examples:
  scripts/run_loop.sh --files src/sim/search.py tests/test_search_beam_diversification.py
  scripts/run_loop.sh --zip-name updates_20260123_120000.zip --files src/sim/state.py
  scripts/run_loop.sh --handoff ygo_combo_pipeline_handoff_2026-01-20.md
EOF
}

zip_name=""
handoff_path=""
files=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --zip-name)
      zip_name="${2:-}"
      shift 2
      ;;
    --handoff)
      handoff_path="${2:-}"
      shift 2
      ;;
    --files)
      shift
      while [[ $# -gt 0 && "$1" != --* ]]; do
        files+=("$1")
        shift
      done
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      files+=("$1")
      shift
      ;;
  esac
done

cd "$REPO_ROOT"

if [ -f "$REPO_ROOT/.venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
fi

if [ -z "$zip_name" ]; then
  ts="$(date +%Y%m%d_%H%M%S)"
  zip_name="updates_${ts}.zip"
fi

if [ ${#files[@]} -eq 0 ]; then
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    mapfile -t files < <(git status --porcelain | awk '{print $2}')
  fi
fi

if [ ${#files[@]} -eq 0 ]; then
  echo "ERROR: No files provided. Use --files or run inside a git repo with changes." >&2
  exit 2
fi

filtered=()
for f in "${files[@]}"; do
  if [ "$f" = "cards.cdb" ]; then
    continue
  fi
  filtered+=("$f")
done
files=("${filtered[@]}")

if [ ${#files[@]} -eq 0 ]; then
  echo "ERROR: No files left after filtering." >&2
  exit 2
fi

qa_rc=0
qa_out=""
run_cmd() {
  local cmd="$1"
  local out
  set +e
  out="$($cmd 2>&1)"
  rc=$?
  set -e
  printf "%s\n" "$out"
  return $rc
}

echo "=== QA: python3 -m unittest discover -s tests ==="
qa_out="$(run_cmd "python3 -m unittest discover -s tests")" || qa_rc=$?

if [ -f "audit_effect_coverage.py" ]; then
  echo "=== QA: python3 audit_effect_coverage.py ==="
  run_cmd "python3 audit_effect_coverage.py" || qa_rc=$?
elif [ -f "scripts/audit_effect_coverage.py" ]; then
  echo "=== QA: python3 scripts/audit_effect_coverage.py ==="
  run_cmd "python3 scripts/audit_effect_coverage.py" || qa_rc=$?
fi

if [ -f "audit_modeling_status.py" ]; then
  echo "=== QA: python3 audit_modeling_status.py --fail ==="
  run_cmd "python3 audit_modeling_status.py --fail" || qa_rc=$?
elif [ -f "scripts/audit_modeling_status.py" ]; then
  echo "=== QA: python3 scripts/audit_modeling_status.py --fail ==="
  run_cmd "python3 scripts/audit_modeling_status.py --fail" || qa_rc=$?
fi

if [ $qa_rc -ne 0 ]; then
  echo "QA failed; not creating zip." >&2
  exit $qa_rc
fi

zip -r "$zip_name" "${files[@]}"
echo "Created: $zip_name"

if [ -n "$handoff_path" ] && [ -f "$handoff_path" ]; then
  entry_ts="$(date +%Y-%m-%d\ %H:%M)"
  {
    echo ""
    echo "- Loop refresh (${entry_ts})"
    echo "  - Zip: \`${zip_name}\`"
    echo "  - Files: ${files[*]}"
  } >> "$handoff_path"
  echo "Updated handoff: $handoff_path"
fi
