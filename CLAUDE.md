# CLAUDE.md for YGO-Combo-Pipeline

> **ultrathink** — Take a deep breath. We're not here to write code. We're here to make a dent in the universe.

---

## The Vision

A research project for exhaustively enumerating combo paths in Yu-Gi-Oh! using the ygopro-core engine via CFFI bindings. The goal is to find every possible combo line from a given starting hand, enabling optimal deck building and play pattern analysis.

---

## Architecture Principles

This project follows a clean module hierarchy:

```
ocg_bindings.py     → Constants & CFFI (canonical source)
       ↓
paths.py            → Centralized path configuration
       ↓
engine_interface.py → Callbacks, parsing, EngineContext
       ↓
combo_enumeration.py, state_representation.py, transposition_table.py
```

**Rules:**
- All MSG_* and QUERY_* constants live in `ocg_bindings.py`
- Production code never imports from test files
- Configuration lives in `config/` directory, not hardcoded
- Use `EngineContext` for safe resource management

---

## Bash Guidelines

### IMPORTANT: Avoid commands that cause output buffering issues

- **DO NOT** pipe output through `head`, `tail`, `less`, or `more` when monitoring
- **DO NOT** use `| head -n X` or `| tail -n X` to truncate output
- Instead, use native command flags when possible

### Examples

```bash
# BAD - causes buffering issues
git log | head -20
cat large_file.txt | tail -100

# GOOD - use native flags
git log -n 20
tail -n 100 large_file.txt
```

---

## Testing Philosophy

- Tests should be deterministic (fixed seeds, sorted outputs)
- Use meaningful assertions, not just "it didn't crash"
- Test edge cases: empty boards, max depth, duplicate states
- Integration tests verify the engine, unit tests verify logic

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run unit tests only
python -m pytest tests/unit/test_state.py -v

# Run with coverage
python -m pytest tests/ --cov=src/cffi --cov-report=html
```

---

## Code Quality Standards

- Type hints on all public functions
- Docstrings with Args/Returns/Raises
- No bare `except:` — always catch specific exceptions
- Logging at module level, not inside functions
- Constants in SCREAMING_SNAKE_CASE

---

## Audit History

### P0 Implementation: Zobrist Hashing (January 2026) - COMPLETED

Implemented O(1) incremental hashing for transposition table performance:

| Component | Status |
|-----------|--------|
| `src/cffi/zobrist.py` | Created - ZobristHasher, StateChange, CardState |
| `src/cffi/transposition_table.py` | Updated - int/str hash support, enhanced stats |
| `src/cffi/state_representation.py` | Updated - zobrist_hash() methods on BoardSignature, IntermediateState |
| `tests/unit/test_zobrist.py` | Created - 14 tests |

**Key Features:**
- Lazy key generation (handles large state space efficiently)
- Deterministic with seed (reproducible across sessions)
- Backwards compatible (string MD5 hashes still work)
- StateChange helpers for common operations (card_moved, card_added, etc.)

### V6 Audit (January 2026) - COMPLETED

| Priority | Issue | Status |
|----------|-------|--------|
| High | transposition_table.py regression check (already correct) | Done |
| Medium | README.md doesn't reference new docs (RESEARCH.md, IMPLEMENTATION_ROADMAP.md) | Done |
| Medium | README.md structure section needs docs subfolder | Done |
| Medium | CLAUDE.md missing V6 audit entry | Done |

**New Documentation Added:**
- `docs/RESEARCH.md` - Comprehensive algorithm research and related work analysis
- `docs/IMPLEMENTATION_ROADMAP.md` - Prioritized improvement plan (P0-P4)

### V4 Audit (January 2026) - COMPLETED

| Priority | Issue | Status |
|----------|-------|--------|
| High | `depth_to_terminal` → `creation_depth` in tests | Done |
| Medium | README.md file structure outdated | Done |
| Medium | QUERY_* constants duplicated | Done |
| Medium | Logging imports inside exception handlers | Done |
| Medium | Missing config warning | Done |
| Medium | Unused BOSS_MONSTERS import | Done |
| Low | Library description unclear | Done |
| Low | Dev tools TODO comments | Done |
| Low | tests/README.md missing | Done |
| Low | Refactoring TODO for Phase 6 | Done |

### V3 Audit (January 2026) - COMPLETED

- C1: Extracted engine_interface.py from test file
- C2: Added EngineContext for safe state management
- C3: Removed risky /tmp fallback paths
- H1-H6: Consolidated constants, fixed imports, added config
- M11, M13: Platform detection, evaluation config

---

## Future Audit Checklist

When running the next audit, verify:

- [ ] All constants defined in single canonical location
- [ ] No circular imports between modules
- [ ] All test files use current field names
- [ ] Configuration files required (not silently defaulted)
- [ ] README reflects actual project structure
- [ ] Logging configured at module level
- [ ] No production→test imports
- [ ] EngineContext used for resource management

---

## Key Files

| File | Purpose |
|------|---------|
| `src/cffi/ocg_bindings.py` | CFFI bindings, MSG_*/QUERY_* constants |
| `src/cffi/engine_interface.py` | EngineContext, callbacks, parsing |
| `src/cffi/paths.py` | Centralized path configuration |
| `src/cffi/combo_enumeration.py` | Core DFS enumeration engine |
| `src/cffi/state_representation.py` | BoardSignature, evaluation |
| `src/cffi/transposition_table.py` | Memoization cache |
| `src/cffi/zobrist.py` | O(1) incremental state hashing |
| `config/locked_library.json` | 26-card Fiendsmith library |
| `config/evaluation_config.json` | Board evaluation weights |
| `docs/RESEARCH.md` | Algorithm research, related work analysis |
| `docs/IMPLEMENTATION_ROADMAP.md` | P0-P4 prioritized improvements |

---

## Environment Requirements

```bash
# Required environment variable
export YGOPRO_SCRIPTS_PATH=/path/to/ygopro-core/scripts

# Required files
cards.cdb              # Card database in project root
src/cffi/build/libygo.dylib  # Built ygopro-core library
```

---

> "The people who are crazy enough to think they can change the world are the ones who do."
