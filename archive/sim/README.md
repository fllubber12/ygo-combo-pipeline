# Deprecated: Python Simulation Reimplementation

This code was an attempt to reimplement ygopro-core game rules in pure Python.

**Why deprecated:**
- Required 300KB+ of hand-coded effect implementations
- Could never achieve 100% rule accuracy
- CFFI bindings to real ygopro-core are more reliable

**Superseded by:** `src/cffi/` which uses CFFI bindings to actual ygopro-core.

**Do not use.** Kept for historical reference only.

## Contents

- `state.py` - Game state representation
- `actions.py` - Action definitions
- `rules.py` - Game rules implementation
- `search.py` - Beam search algorithm
- `effects/` - Hand-coded card effects (~275KB)
