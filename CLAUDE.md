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

## CARD DATA RULES (ANTI-HALLUCINATION)

**CRITICAL: Claude must NEVER provide card data from memory.**

### Prohibited Actions

Claude must **NEVER**:
- Provide card IDs/passcodes from memory
- State card levels, ATK, DEF, types from memory
- Assume card effects without verification
- Make up card names or attributes
- Trust "common knowledge" about cards

### Required Data Sources

All card data **MUST** come from (in order of preference):

1. **config/verified_cards.json** (PRIMARY)
   - Human-verified card data
   - Audited against official sources
   - Use `CardValidator` class for lookups

2. **cards.cdb database queries** (SECONDARY)
   ```sql
   SELECT id, name, level, atk, def FROM datas
   JOIN texts ON datas.id = texts.id
   WHERE id = ?;
   ```

3. **User-provided information** (when adding new cards)
   - User searches official sources
   - User verifies data
   - Added to verified_cards.json

### Adding New Cards Protocol

1. User provides card name
2. Claude searches YGOProDeck API, Yugipedia, or Official Neuron DB
3. User verifies the search results
4. Add to `config/verified_cards.json` with `"verified": true`

### Validation Module

Use `src/cffi/card_validator.py`:

```python
from card_validator import CardValidator, get_verified_card

validator = CardValidator()

# Get verified data
card = validator.get_card(60764609)
print(card['level'])  # 6

# Validate engine data
validator.validate(60764609, 'level', engine_level, source="SELECT_SUM")
```

### Known Issues

- **SELECT_SUM parsing**: Engine shows `level=1` for Engraver (should be 6)
- Validated via `compare_cdb_to_verified()` function

### LOCKED CARD DATA (CRITICAL)

**Status: LOCKED as of 2026-01-26**

The `config/verified_cards.json` file has been **triple-verified** against official sources and is now **cryptographically locked**.

#### Lock Mechanism

1. **Integrity Checksum**: SHA256 hash of all card data stored in metadata
2. **Pre-commit Hook**: Validates checksum on every commit attempt
3. **Automatic Rejection**: Any modification without re-verification is BLOCKED

#### Modifying Locked Data

Claude must **NEVER** modify `verified_cards.json` without:

1. **Explicit user request** stating the specific card and field to change
2. **Verification from official source** (YGOProDeck API, Konami DB, Yugipedia)
3. **User confirmation** of the verified data
4. **Re-running the lock script**: `python scripts/generate_lock_checksum.py`

#### Pre-commit Validation

Every commit touching card data files triggers:
```
1. Integrity checksum verification (CRITICAL)
2. CDB consistency check (name, level, ATK/DEF)
3. Extra deck flag validation
```

If ANY check fails, the commit is **REJECTED**.

#### Emergency Override

If the pre-commit hook must be bypassed (NOT RECOMMENDED):
```bash
git commit --no-verify -m "EMERGENCY: [reason]"
```

This should ONLY be used for critical fixes and requires immediate re-verification.

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

### Deck Setup Tools (January 2026) - COMPLETED

Added Crystal Beast Fiendsmith deck setup scripts:

| Component | Status |
|-----------|--------|
| `scripts/setup_deck.py` | Created - Card lookup and validation from cards.cdb |
| `scripts/validate_engine.py` | Created - Engine validation tests |
| `docs/CB_FIENDSMITH_SETUP_GUIDE.md` | Created - Deck setup guide |

**Key Features:**
- Multi-strategy card lookup (exact, fuzzy, alternate names)
- Validation report with passcode verification
- Library and roles JSON generation
- Engine import testing

### P4 Implementation: ML Encoding (January 2026) - COMPLETED

Implemented ygo-agent compatible state encoding for ML integration:

| Component | Status |
|-----------|--------|
| `src/cffi/ml_encoding.py` | Created - StateEncoder, ActionEncoder, ObservationEncoder |
| `tests/unit/test_ml_encoding.py` | Created - 45 tests |

**Key Features:**
- 41-feature card encoding (ygo-agent compatible)
- 23-feature global state encoding
- 14-feature action encoding
- 16-step action history buffer
- Batch encoding utilities for training data
- BoardSignature integration

### P3 Implementation: Iterative Deepening (January 2026) - COMPLETED

Implemented iterative deepening wrapper for shortest-first combo discovery:

| Component | Status |
|-----------|--------|
| `src/cffi/iterative_deepening.py` | Created - SearchConfig, IterativeDeepeningSearch |
| `tests/unit/test_iterative_deepening.py` | Created - 22 tests |

**Key Features:**
- Depth-limited search iterations (1, 2, 3, ... max_depth)
- Configurable stopping conditions (target score/tier, time/path budget)
- Transposition table preserved across iterations
- Anytime behavior (can stop early with valid results)
- Finds shortest combos first

### P2 Implementation: Card Role Classification (January 2026) - COMPLETED

Implemented card role classification for move ordering and pruning:

| Component | Status |
|-----------|--------|
| `src/cffi/card_roles.py` | Created - CardRole enum, CardRoleClassifier |
| `config/card_roles.json` | Created - Fiendsmith library classifications |
| `tests/unit/test_card_roles.py` | Created - 20 tests |

**Key Features:**
- CardRole enum: STARTER, EXTENDER, PAYOFF, UTILITY, GARNET
- Priority-based action sorting (starters first)
- Extender pruning heuristic (skip if no starter activated)
- Config-driven classification with heuristic fallback

### V8 Audit (January 2026) - COMPLETED

Post-P1 audit to verify all files are committed and consistent.

| Priority | Issue | Status |
|----------|-------|--------|
| Critical | P1 files not committed (parallel_search.py, test_parallel.py) | Fixed |
| Critical | transposition_table.py verified (creation_depth, Union[int,str]) | Already correct |
| High | state_representation.py verified (zobrist_hash() methods) | Already correct |
| High | combo_enumeration.py verified (enumerate_from_hand() stub) | Fixed |
| Medium | README.md structure updated with parallel_search.py | Fixed |
| Medium | test_state.py verified (uses creation_depth) | Already correct |

### P1 Implementation: Parallel Search (January 2026) - COMPLETED

Implemented parallel enumeration across C(n,k) starting hands for near-linear speedup:

| Component | Status |
|-----------|--------|
| `src/cffi/parallel_search.py` | Created - ParallelConfig, ComboResult, ParallelResult, process pool |
| `src/cffi/combo_enumeration.py` | Updated - enumerate_from_hand() stub added |
| `tests/unit/test_parallel.py` | Created - 13 tests |
| CLI interface | --workers, --estimate flags |

**Key Features:**
- Process pool across C(n,k) starting hands (658,008 for 40-card deck, 5-card hand)
- Auto-calculated batch sizes for load balancing
- Progress tracking with ETA
- Runtime estimation mode
- Near-linear speedup with worker count (8 workers ≈ 8x faster)

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

### V7 Audit (January 2026) - COMPLETED

Post-P0 Zobrist implementation audit.

| Priority | Issue | Status |
|----------|-------|--------|
| Critical | transposition_table.py verified (creation_depth, depth-preferred eviction) | Done |
| Critical | state_representation.py verified (zobrist_hash() methods present) | Done |
| Critical | test_state.py verified (uses creation_depth) | Done |
| Medium | ocg_bindings.py verified (uses paths.py) | Done |
| Medium | README.md structure updated (includes zobrist.py) | Done |
| Medium | CLAUDE.md Key Files updated, Audit Process added | Done |

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

## Audit Process

### Claude Code ↔ Claude Chat Audit Loop

**CRITICAL:** All code changes require verification through this loop:

1. **Claude Code** commits and pushes changes
2. **Claude Code** generates AUDIT INFO block:
   ```bash
   echo "=== AUDIT INFO ==="
   echo "Repo: $(git remote get-url origin)"
   echo "SHA: $(git rev-parse HEAD)"
   echo "Message: $(git log -1 --pretty=%s)"
   echo "Changed files:"
   git show --name-only --format="" HEAD
   echo "=== END AUDIT INFO ==="
   ```
3. **Claude Code** provides verification URL(s) to user
4. **Claude Chat** fetches code using SHA-pinned URLs and audits
5. **Claude Chat** confirms OR identifies issues
6. **Only proceed to next task after audit passes**

### Standard Implementation Cycle

1. **Run tests**: `python -m pytest tests/ -v`
2. **Commit**: `git add . && git commit -m "description"`
3. **Push**: `git push`
4. **Output verification block** (see Post-Commit Audit Protocol below)
5. **Paste URLs** to auditor for verification
6. **Iterate** if issues found

### Post-Commit Audit Protocol

After every `git push`, output the following for audit verification:

**1. Commit Info:**
```
Commit: [FULL_SHA]
Message: [commit message]
Files changed: [list]
```

**2. Verification URLs**

Use commit-pinned RAW URLs (these bypass CDN cache):
```
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/ocg_bindings.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/engine_interface.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/paths.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/combo_enumeration.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/state_representation.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/transposition_table.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/zobrist.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/parallel_search.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/card_roles.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/iterative_deepening.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/src/cffi/ml_encoding.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/tests/unit/test_state.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/tests/unit/test_zobrist.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/tests/unit/test_parallel.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/tests/unit/test_card_roles.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/tests/unit/test_iterative_deepening.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/tests/unit/test_ml_encoding.py
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/README.md
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/CLAUDE.md
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/docs/RESEARCH.md
https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/[FULL_SHA]/docs/IMPLEMENTATION_ROADMAP.md
```

**CRITICAL:** Use `raw.githubusercontent.com/{owner}/{repo}/{FULL_SHA}/path` format.
- Commit-pinned raw URLs bypass CDN cache
- Do NOT use branch names (main) - they have 5-15 min cache delays
- Do NOT use blob URLs - they return HTML, not raw content

**3. Test Summary:**
```
Tests: [X] passed, [Y] skipped, [Z] failed
```

**4. Generate URLs Script:**
After `git push`, run:
```bash
SHA=$(git rev-parse HEAD)
echo "Commit: $SHA"
echo ""
echo "Verification URLs:"
for f in src/cffi/ocg_bindings.py src/cffi/engine_interface.py src/cffi/paths.py \
         src/cffi/combo_enumeration.py src/cffi/state_representation.py \
         src/cffi/transposition_table.py src/cffi/zobrist.py src/cffi/parallel_search.py \
         src/cffi/card_roles.py src/cffi/iterative_deepening.py src/cffi/ml_encoding.py \
         tests/unit/test_state.py tests/unit/test_zobrist.py \
         tests/unit/test_parallel.py tests/unit/test_card_roles.py \
         tests/unit/test_iterative_deepening.py tests/unit/test_ml_encoding.py \
         README.md CLAUDE.md docs/RESEARCH.md docs/IMPLEMENTATION_ROADMAP.md; do
  echo "https://raw.githubusercontent.com/fllubber12/ygo-combo-pipeline/$SHA/$f"
done
```

### Files to Audit

**Source (11 files):**
```
src/cffi/ocg_bindings.py
src/cffi/engine_interface.py
src/cffi/paths.py
src/cffi/combo_enumeration.py
src/cffi/state_representation.py
src/cffi/transposition_table.py
src/cffi/zobrist.py
src/cffi/parallel_search.py
src/cffi/card_roles.py
src/cffi/iterative_deepening.py
src/cffi/ml_encoding.py
```

**Tests (7 files):**
```
tests/unit/test_state.py
tests/unit/test_zobrist.py
tests/unit/test_parallel.py
tests/unit/test_card_roles.py
tests/unit/test_iterative_deepening.py
tests/unit/test_ml_encoding.py
tests/README.md
```

**Docs (4 files):**
```
README.md
CLAUDE.md
docs/RESEARCH.md
docs/IMPLEMENTATION_ROADMAP.md
```

**Config (2 files):**
```
config/locked_library.json
config/evaluation_config.json
```

### Fix Document Format

Each fix instruction includes:
- **Issue**: What's wrong
- **Location**: File and line numbers
- **Action**: Exact change (replace/add/remove)
- **Code**: Complete code block to use

This ensures fixes can be applied mechanically without ambiguity.

---

## Key Files

| File | Purpose |
|------|---------|
| `src/cffi/ocg_bindings.py` | CFFI bindings, MSG_*/QUERY_* constants |
| `src/cffi/engine_interface.py` | EngineContext, callbacks, parsing |
| `src/cffi/paths.py` | Centralized path configuration |
| `src/cffi/combo_enumeration.py` | Core DFS enumeration engine |
| `src/cffi/state_representation.py` | BoardSignature, IntermediateState, evaluation |
| `src/cffi/transposition_table.py` | Memoization cache with depth-preferred eviction |
| `src/cffi/zobrist.py` | O(1) incremental Zobrist hashing |
| `src/cffi/parallel_search.py` | Parallel enumeration across starting hands |
| `src/cffi/card_roles.py` | Card role classification for move ordering |
| `src/cffi/iterative_deepening.py` | Iterative deepening search wrapper |
| `src/cffi/ml_encoding.py` | ML-compatible state encoding (ygo-agent format) |
| `src/cffi/card_validator.py` | Verified card data validation (anti-hallucination) |
| `config/locked_library.json` | **LOCKED** - Crystal Beast Fiendsmith library (19 extra deck). DO NOT MODIFY without user approval. |
| `config/verified_cards.json` | **LOCKED** - Triple-verified card data (48 cards). Checksum-protected. DO NOT MODIFY without audit. |
| `config/card_roles.json` | Manual card role overrides |
| `config/evaluation_config.json` | Board evaluation weights |
| `scripts/setup_deck.py` | Card lookup and deck validation |
| `scripts/validate_engine.py` | Engine validation tests |
| `scripts/validate_verified_cards.py` | Pre-commit validation with integrity checksum |
| `scripts/validate_library_integrity.py` | Pre-commit library validation |
| `scripts/generate_lock_checksum.py` | Generate/update integrity checksum after audit |
| `docs/RESEARCH.md` | Game AI research report |
| `docs/IMPLEMENTATION_ROADMAP.md` | P0-P4 prioritized improvements |
| `docs/CB_FIENDSMITH_SETUP_GUIDE.md` | Crystal Beast Fiendsmith setup guide |

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
