# Archived Tests

These tests were written for the deprecated `src/sim/` Python simulation reimplementation.

**Why archived:**
- They depend on `sim` and `combos` modules which are now in `archive/`
- The CFFI bindings to ygopro-core (`src/cffi/`) superseded the Python simulation
- These tests are not executable without the archived modules

**Current active tests:**
- `tests/unit/test_state.py` - 19 unit tests for state representation
- `tests/integration/test_fiendsmith_duel.py` - Integration tests for CFFI bindings

**Do not run.** Kept for historical reference only.
