#!/bin/bash
# Prepares handoff bundle and updates TODO for session continuity

set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
HANDOFF_DIR="handoffs"
mkdir -p "$HANDOFF_DIR"

echo "=== Preparing Handoff $TIMESTAMP ==="

# 1. Run QA
echo "Running tests..."
python3 -m unittest discover -s tests

echo "Running coverage audit..."
python3 scripts/audit_effect_coverage.py

echo "Running modeling status..."
python3 scripts/audit_modeling_status.py --fail

echo "Running validation framework..."
python3 scripts/validate_effects_comprehensive.py | tail -5

# 2. Git status
echo ""
echo "=== Git Status ==="
git status --short

# 3. Commit any uncommitted changes
if [[ -n $(git status --porcelain) ]]; then
    echo "Uncommitted changes detected. Committing..."
    git add -A
    git commit -m "Auto-handoff checkpoint $TIMESTAMP"
fi

# 4. Create handoff bundle
echo ""
echo "=== Creating Bundle ==="
BUNDLE_NAME="$HANDOFF_DIR/handoff_$TIMESTAMP.zip"
zip -r "$BUNDLE_NAME" \
    src/ scripts/ tests/ config/ decklists/ docs/ \
    *.md requirements.txt \
    -x "*.pyc" -x "__pycache__/*" -x "*.cdb" -x "reports/verified_lua/*"

echo "Bundle created: $BUNDLE_NAME"

# 5. Update TODO
echo ""
echo "=== Current Status ==="
echo "Commit: $(git rev-parse --short HEAD)"
echo "Tests: $(python3 -m unittest discover -s tests 2>&1 | tail -1)"
echo "Validation: $(python3 scripts/validate_effects_comprehensive.py 2>&1 | grep PASSED)"

echo ""
echo "=== Handoff Ready ==="
echo "Bundle: $BUNDLE_NAME"
echo "To continue: unzip and run 'git log -1' to see last state"
