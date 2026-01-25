# Project Reorganization Plan

> Generated: 2026-01-25
> Purpose: Hand off to Claude Code for implementation

---

## Current State Analysis

### Root Directory Clutter (TO BE CLEANED)

| File/Dir | Status | Action |
|----------|--------|--------|
| `audit_effect_coverage.py` | Duplicate | DELETE (exists in scripts/) |
| `audit_modeling_status.py` | Duplicate | DELETE (exists in scripts/) |
| `generate_spot_check_report.py` | Duplicate | DELETE (exists in scripts/qa/) |
| `suggest_card_tags.py` | Duplicate | DELETE (exists in scripts/qa/) |
| `tag_review_report.py` | Duplicate | DELETE (exists in scripts/qa/) |
| `validate_card_tags.py` | Duplicate | DELETE (exists in scripts/qa/) |
| `populate_fiendsmith_card_library.py` | Utility | MOVE to scripts/ |
| `chatgpt_upload.part-00` | Temp file | DELETE |
| `ziMkzBNZ` | Temp file | DELETE |
| `zivconIV` | Temp file | DELETE |
| `LOCAL_ONLY_NO_GITHUB.txt` | Marker | DELETE (use .gitignore) |
| `card_tags.json` | Data | MOVE to data_raw/ |
| `card_tags.jsonl` | Data | MOVE to data_raw/ |
| `card_tags.xlsx` | Data | MOVE to data_raw/ |
| `Fiendsmith_*.xlsx` | Data | MOVE to data_raw/ |
| `ygo_combo_pipeline_handoff_*.md` | Archive | MOVE to handoffs/ |
| `ygo_combo_pipeline_up_to_date_*.md` | Archive | MOVE to handoffs/ |
| `yu-gi-oh-analysis-pipeline-rules-standards.md` | Docs | MOVE to docs/ |
| `tag_review_report.md` | Report | MOVE to reports/ |
| `make_handoff.sh` | Script | MOVE to scripts/ |
| `requirements.txt` | Config | KEEP (but add pyproject.toml) |
| `CHANGELOG.md` | Docs | KEEP |
| `cards.cdb` | Data | KEEP (large, gitignored) |

### Deprecated Code (TO BE ARCHIVED)

| Directory | Lines | Action |
|-----------|-------|--------|
| `src/sim/` | ~2,050 | MOVE to archive/sim/ |
| `src/sim/effects/` | ~275KB | MOVE with parent |
| `src/combos/` | ~200 | MOVE to archive/combos/ (unused) |

### Generated Files (SHOULD BE GITIGNORED)

| File Pattern | Location | Action |
|--------------|----------|--------|
| `enumeration_*.json` | src/cffi/ | Already gitignored ✓ |
| `verification_run.json` | src/cffi/ | Already gitignored ✓ |
| `__pycache__/` | Multiple | Already gitignored ✓ |
| `.pytest_cache/` | Multiple | Add to .gitignore |
| `*.pyc` | Multiple | Already gitignored ✓ |

---

## Target Structure

```
ygo-combo-pipeline/
├── README.md                    # Project overview
├── CHANGELOG.md                 # Version history
├── pyproject.toml               # Modern Python packaging (NEW)
├── requirements.txt             # Keep for compatibility
├── .gitignore                   # Updated with new patterns
│
├── src/
│   └── cffi/                    # Active implementation
│       ├── __init__.py
│       ├── combo_enumeration.py # Core enumeration engine
│       ├── state_representation.py
│       ├── transposition_table.py
│       ├── ocg_bindings.py      # CFFI interface
│       ├── test_fiendsmith_duel.py
│       ├── verify_all_cards.py
│       ├── build/               # Build artifacts
│       └── deps/                # Dependencies (lua, etc.)
│
├── scripts/
│   ├── enumerate_all_paths.py   # Main entry point
│   ├── validate_effects.py      # Renamed from validate_effects_comprehensive.py
│   ├── validate_card_data.py
│   ├── add_new_card.py
│   ├── make_handoff.sh
│   ├── populate_library.py      # Renamed from populate_fiendsmith_card_library.py
│   └── qa/                      # QA utilities
│       ├── run_qa.py
│       ├── validate_card_tags.py
│       ├── suggest_card_tags.py
│       ├── generate_spot_check_report.py
│       └── tag_review_report.py
│
├── tests/
│   ├── unit/
│   │   ├── test_state.py        # Moved from src/cffi/
│   │   └── test_transposition.py # New: split from test_state.py
│   ├── integration/
│   │   ├── test_create_duel.py  # Moved from src/cffi/
│   │   ├── test_activate_engraver.py
│   │   ├── test_full_combo.py
│   │   └── test_opt_tracking.py
│   └── conftest.py              # pytest fixtures
│
├── config/
│   ├── locked_library.json      # Card library
│   ├── evaluation_config.json   # Board evaluation settings (NEW)
│   └── verified_effects.json    # Effect verification data
│
├── docs/
│   ├── COMBO_PIPELINE_ROADMAP.md
│   ├── PROJECT_INVENTORY.md
│   ├── ARCHITECTURE.md          # Extract from roadmap (NEW)
│   ├── DECISIONS.md             # Extract decision log (NEW)
│   ├── ISSUES_AND_FIXES.md      # This companion doc
│   └── rules-standards.md       # Renamed from yu-gi-oh-analysis-pipeline-rules-standards.md
│
├── data/
│   ├── raw/                     # Renamed from data_raw/
│   │   ├── card_tags.json
│   │   ├── card_tags.jsonl
│   │   └── *.xlsx
│   ├── processed/               # Renamed from data_processed/
│   └── cache/                   # Renamed from data_cache/
│
├── reports/
│   ├── batch/                   # Batch run reports
│   └── analysis/                # Analysis reports
│
├── handoffs/
│   └── *.md                     # Session handoff documents
│
├── archive/                     # Deprecated code (NEW)
│   ├── sim/                     # Old Python reimplementation
│   │   ├── README.md            # Deprecation notice (NEW)
│   │   ├── state.py
│   │   ├── actions.py
│   │   ├── rules.py
│   │   ├── search.py
│   │   └── effects/
│   └── combos/                  # Unused combo evaluator
│
└── decklists/                   # Deck configurations
```

---

## Migration Commands

### Step 1: Create New Directories

```bash
cd /path/to/project

# Create new directories
mkdir -p archive/sim archive/combos
mkdir -p tests/unit tests/integration
mkdir -p data/raw data/processed data/cache
mkdir -p docs
```

### Step 2: Archive Deprecated Code

```bash
# Move deprecated sim implementation
mv src/sim/* archive/sim/
rmdir src/sim

# Move unused combos module
mv src/combos/* archive/combos/
rmdir src/combos

# Create deprecation notice
cat > archive/sim/README.md << 'EOF'
# Deprecated: Python Simulation Reimplementation

This code was an attempt to reimplement ygopro-core game rules in pure Python.

**Why deprecated:** 
- Required 300KB+ of hand-coded effect implementations
- Could never achieve 100% rule accuracy
- CFFI bindings to real ygopro-core are more reliable

**Superseded by:** `src/cffi/` which uses CFFI bindings to actual ygopro-core.

**Do not use.** Kept for historical reference only.
EOF

cat > archive/combos/README.md << 'EOF'
# Deprecated: Combo Evaluator

Early prototype for combo evaluation. Superseded by state_representation.py.
EOF
```

### Step 3: Clean Root Directory

```bash
cd /path/to/project

# Delete duplicates (already exist in scripts/)
rm -f audit_effect_coverage.py
rm -f audit_modeling_status.py
rm -f generate_spot_check_report.py
rm -f suggest_card_tags.py
rm -f tag_review_report.py
rm -f validate_card_tags.py

# Delete temp files
rm -f chatgpt_upload.part-00
rm -f ziMkzBNZ
rm -f zivconIV
rm -f LOCAL_ONLY_NO_GITHUB.txt

# Move utilities to scripts/
mv populate_fiendsmith_card_library.py scripts/populate_library.py
mv make_handoff.sh scripts/

# Move data files
mv card_tags.json data/raw/
mv card_tags.jsonl data/raw/
mv card_tags.xlsx data/raw/
mv Fiendsmith_Card_Library_CLEAN_TEMPLATE.xlsx data/raw/
mv Fiendsmith_Master_Card_Library_CLEAN.xlsx data/raw/

# Move handoffs
mv ygo_combo_pipeline_handoff_*.md handoffs/
mv ygo_combo_pipeline_up_to_date_*.md handoffs/

# Move docs
mv yu-gi-oh-analysis-pipeline-rules-standards.md docs/rules-standards.md
mv tag_review_report.md reports/

# Consolidate data directories
mv data_raw/* data/raw/ 2>/dev/null || true
mv data_processed/* data/processed/ 2>/dev/null || true
mv data_cache/* data/cache/ 2>/dev/null || true
rmdir data_raw data_processed data_cache 2>/dev/null || true
```

### Step 4: Reorganize Tests

```bash
cd /path/to/project

# Move unit tests
mv src/cffi/test_state.py tests/unit/

# Move integration tests
mv src/cffi/test_create_duel.py tests/integration/
mv src/cffi/test_activate_engraver.py tests/integration/
mv src/cffi/test_full_combo.py tests/integration/
mv src/cffi/test_opt_tracking.py tests/integration/

# Create conftest.py for shared fixtures
cat > tests/conftest.py << 'EOF'
"""Shared pytest fixtures for ygo-combo-pipeline tests."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "cffi"))

@pytest.fixture
def sample_board_state():
    """Sample board state for testing."""
    return {
        "player0": {
            "monsters": [{"code": 79559912, "name": "Caesar"}],
            "spells": [],
            "graveyard": [{"code": 60764609, "name": "Engraver"}],
            "hand": [],
            "banished": [],
            "extra": [],
        },
        "player1": {
            "monsters": [], "spells": [], "graveyard": [],
            "hand": [], "banished": [], "extra": [],
        },
    }

@pytest.fixture
def sample_idle_data():
    """Sample MSG_IDLE data for testing."""
    return {
        "activatable": [
            {"code": 60764609, "loc": 2, "desc": 0},
        ],
        "spsummon": [],
        "summonable": [],
        "mset": [],
        "sset": [],
        "to_ep": True,
    }
EOF
```

### Step 5: Create pyproject.toml

```bash
cat > pyproject.toml << 'EOF'
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ygo-combo-pipeline"
version = "0.1.0"
description = "Yu-Gi-Oh! combo enumeration and analysis pipeline"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Zachary Hartley", email = "zach.hartley12@gmail.com"},
]
keywords = ["yugioh", "combo", "analysis", "ygopro"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Topic :: Games/Entertainment",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
]

dependencies = [
    "cffi>=1.15.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
    "mypy",
    "ruff",
]

[project.urls]
"Homepage" = "https://github.com/fllubber12/ygo-combo-pipeline"
"Bug Tracker" = "https://github.com/fllubber12/ygo-combo-pipeline/issues"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v"

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_ignores = true
EOF
```

### Step 6: Update .gitignore

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/
env/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.nox/

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Project-specific generated files
enumeration_*.json
verification_run.json
depth_*.json

# Large data files (download separately)
cards.cdb

# Compiled binaries
*.dylib
*.so
*.dll
libygo.*

# Lua build artifacts
deps/lua-*/src/*.o
deps/lua-*/src/lua
deps/lua-*/src/luac

# Reports (regeneratable)
reports/batch/*.json
reports/batch/*.md

# Archives and backups
*.zip
!config/*.zip

# Temp files
ziMkzBNZ
zivconIV
*.part-*
EOF
```

### Step 7: Create evaluation_config.json

```bash
cat > config/evaluation_config.json << 'EOF'
{
  "_meta": {
    "description": "Board evaluation configuration",
    "version": "1.0.0"
  },
  "tier_thresholds": {
    "S": 100,
    "A": 70,
    "B": 40,
    "C": 20
  },
  "score_weights": {
    "boss_monster": 50,
    "interaction_piece": 30,
    "equipped_link": 20,
    "monster_on_field": 5,
    "fiendsmith_in_gy": 10
  },
  "boss_monsters": [
    79559912,
    4731783,
    32991300,
    82135803,
    11464648,
    29301450,
    45409943
  ],
  "interaction_pieces": [
    79559912,
    29301450,
    4731783
  ],
  "fiendsmith_gy_targets": [
    2463794,
    49867899,
    60764609
  ]
}
EOF
```

---

## Post-Migration Verification

```bash
cd /path/to/project

# 1. Verify structure
find . -type d -name "__pycache__" -prune -o -type f -name "*.py" -print | head -30

# 2. Run tests from new location
cd tests
python -m pytest unit/ -v
python -m pytest integration/ -v --ignore=integration/test_full_combo.py  # Full combo is slow

# 3. Verify imports still work
cd ../src/cffi
python -c "from state_representation import BoardSignature; print('OK')"
python -c "from combo_enumeration import EnumerationEngine; print('OK')"

# 4. Quick enumeration test
python combo_enumeration.py --max-depth 10 --max-paths 50

# 5. Git status check
cd ../..
git status
```

---

## Files to Commit After Reorganization

```bash
git add -A
git status

# Expected changes:
# - Deleted: Root duplicates, temp files
# - Renamed: data_* -> data/*, test files moved
# - New: pyproject.toml, evaluation_config.json, archive/*/README.md
# - Modified: .gitignore

git commit -m "Reorganize project structure

- Archive deprecated src/sim/ and src/combos/
- Move tests to tests/unit/ and tests/integration/
- Clean root directory of duplicates and temp files
- Add pyproject.toml for modern Python packaging
- Add evaluation_config.json for tunable parameters
- Consolidate data directories
- Update .gitignore"
```

---

## Summary

| Action | Count |
|--------|-------|
| Files to delete | 10 |
| Files to move | 18 |
| Directories to create | 6 |
| Directories to archive | 2 |
| New files to create | 5 |

**Estimated time:** 30-45 minutes with Claude Code
