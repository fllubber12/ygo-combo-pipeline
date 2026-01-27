# TODO Next Session

## Current State (Updated 2026-01-26)

### Repository Structure - COMPLETE
```
src/ygo_combo/
├── engine/           ✅ bindings, interface, state, paths
├── search/           ✅ iddfs, transposition, parallel
├── cards/            ✅ roles, validator, verification
├── encoding/         ✅ ml
├── utils/            ✅ hashing
├── enumeration/      ✅ parsers, responses, handlers
├── combo_enumeration.py  (923 lines - core dispatcher)
├── ranking.py        ✅ combo scoring system
└── checkpoint.py     ✅ save/resume enumeration
```

### Test Status
- **Unit Tests:** 200+ passing
- **Property Tests:** 20 tests (9 pass, 11 skip without engine)
- **Regression Tests:** Known-count tests implemented
- **Integration Tests:** Require engine (YGOPRO_SCRIPTS_PATH)

Total: **236 passed, 33 skipped** (engine-dependent)

### Completed Features
- ✅ CFFI engine integration
- ✅ Exhaustive combo enumeration (IDDFS)
- ✅ Transposition table with instrumentation
- ✅ Parallel search infrastructure
- ✅ Card role classification
- ✅ ML-compatible state encoding
- ✅ Checkpointing (save/resume)
- ✅ Combo ranking system
- ✅ Property-based testing with Hypothesis
- ✅ Known-count regression tests

### Key Metrics
| Metric | Value |
|--------|-------|
| combo_enumeration.py | 923 lines (56% reduction from 2,096) |
| Test coverage | 236 tests |
| Property tests | 20 |
| Regression tests | 4 known-count hands |

## Next Steps (Priority Order)

### Short-Term
1. **Engine Integration Testing** - Set up YGOPRO_SCRIPTS_PATH for full test suite
2. **Gold Standard Combo Validation** - Verify A Bao A Qu + Caesar reachable

### Medium-Term
1. **Sampling Strategy** - Design approach for 1.7M hand coverage
2. **Differential Testing** - Build expert corpus for comparison

### Long-Term
1. **Production Deployment** - Full deck enumeration at scale
2. **ML Training Data** - Generate training data from enumeration results

## Quick Commands

```bash
# Run all tests (unit, property, regression)
python3 -m pytest tests/unit/ tests/property/ tests/regression/ -v

# Run with engine (requires YGOPRO_SCRIPTS_PATH)
export YGOPRO_SCRIPTS_PATH=/path/to/ygopro-core/script
python3 -m pytest tests/ -v

# Check imports
python3 -c "from src.ygo_combo import ComboEnumerator, ComboRanker"

# Run enumeration
python3 -m src.ygo_combo.combo_enumeration --max-depth 25 --max-paths 1000
```

## Key Files

| File | Purpose |
|------|---------|
| `src/ygo_combo/combo_enumeration.py` | Core enumeration engine |
| `src/ygo_combo/ranking.py` | Combo scoring and ranking |
| `src/ygo_combo/checkpoint.py` | Save/resume enumeration |
| `src/ygo_combo/search/transposition.py` | State memoization |
| `src/ygo_combo/search/iddfs.py` | Iterative deepening |
| `config/locked_library.json` | Card library (48 cards) |
| `CLAUDE.md` | Project guidelines |

## Reference Documents

| Document | Location |
|----------|----------|
| Master Plan | `/tmp/select_sum_fix/MASTER_PLAN.md` |
| Architecture Overview | `docs/architecture/OVERVIEW.md` |
| Search Strategy | `docs/architecture/SEARCH_STRATEGY.md` |

## Recent Commits

```bash
git log --oneline -5
```
