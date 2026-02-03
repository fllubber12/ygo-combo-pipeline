# PC Port Manifest

## Files to Transfer

### Core Package (REQUIRED)
```
src/ygo_combo/
├── __init__.py
├── types.py
├── combo_enumeration.py
├── cli.py
├── sampling.py
├── ranking.py
├── checkpoint.py
├── cards/
│   ├── __init__.py
│   ├── roles.py
│   └── validator.py
├── engine/
│   ├── __init__.py
│   ├── paths.py          # Cross-platform path handling
│   ├── interface.py      # CFFI bindings
│   ├── bindings.py       # Constants
│   ├── board_types.py
│   ├── board_capture.py
│   ├── duel_factory.py
│   └── state.py
├── enumeration/
│   ├── __init__.py
│   ├── handlers.py
│   ├── parsers.py
│   ├── responses.py
│   └── sum_utils.py
├── search/
│   ├── __init__.py
│   ├── parallel.py
│   ├── transposition.py
│   └── iddfs.py
├── encoding/
│   ├── __init__.py
│   └── ml.py
└── utils/
    ├── __init__.py
    └── hashing.py
```

### Scripts (REQUIRED)
```
scripts/
├── export_traces.py      # Main trace collection script
├── run_pipeline.py       # Full pipeline runner
└── random_hand_enumeration.py  # Random sampling
```

### Config (REQUIRED)
```
config/
├── locked_library.json   # Card library (60-card deck)
├── verified_cards.json   # Verified card data
├── card_roles.json       # Card role classifications
└── evaluation_config.json
```

### Database (REQUIRED)
```
cards.cdb                 # SQLite card database (~7MB)
```

### Build Artifacts (MUST BUILD ON PC)
```
src/ygo_combo/build/
└── libygo.dll            # Windows - must build from ygopro-core
    OR libygo.so          # Linux - must build from ygopro-core
```

## Dependencies

### Python (requirements.txt - minimal for trace export)
```
cffi>=1.15.0
```

### External
- ygopro-core built as shared library
- ygopro-core scripts directory (utility.lua, card scripts)

## Environment Setup

### 1. Set YGOPRO_SCRIPTS_PATH
```bash
# Linux/Mac
export YGOPRO_SCRIPTS_PATH=/path/to/ygopro-core/script

# Windows (PowerShell)
$env:YGOPRO_SCRIPTS_PATH = "C:\path\to\ygopro-core\script"

# Windows (CMD)
set YGOPRO_SCRIPTS_PATH=C:\path\to\ygopro-core\script
```

### 2. Build ygopro-core (if not already done)
```bash
# Clone ygopro-core
git clone https://github.com/edo9300/ygopro-core.git
cd ygopro-core

# Build shared library
# Linux:
g++ -shared -fPIC -o libygo.so *.cpp -std=c++14
# Windows (MSVC):
cl /LD /EHsc *.cpp /Fe:ygo.dll
```

### 3. Place library in build directory
```
src/ygo_combo/build/libygo.dll   # Windows
src/ygo_combo/build/libygo.so    # Linux
```

## Verification Commands

```bash
# Test trace export (quick test)
python scripts/export_traces.py \
  --hand "60764609,14558127,14558127,14558127,14558127" \
  --max-paths 100 \
  --output results/test_trace.json

# Random sampling (full run)
python scripts/export_traces.py \
  --random 100 \
  --max-paths 5000 \
  --max-depth 50 \
  --output results/traces_sample.json
```

## Platform Detection

The code auto-detects platform in `src/ygo_combo/engine/paths.py`:
- Darwin (macOS): loads `.dylib`
- Windows: loads `.dll`
- Linux: loads `.so`

No code changes needed for different platforms.
