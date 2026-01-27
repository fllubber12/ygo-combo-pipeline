# TODO Next Session

## Current State (Updated 2026-01-26)

### Repository Structure - COMPLETE
```
src/ygo_combo/
├── engine/           ✅ bindings, interface, state, paths
├── search/           ✅ iddfs, transposition, parallel (with checkpoints)
├── cards/            ✅ roles, validator, verification
├── encoding/         ✅ ml
├── utils/            ✅ hashing
├── enumeration/      ✅ parsers, responses, handlers
├── combo_enumeration.py  (923 lines - core dispatcher)
├── ranking.py        ✅ combo scoring system
├── sampling.py       ✅ stratified hand sampling
└── checkpoint.py     ✅ save/resume enumeration

scripts/
└── run_pipeline.py   ✅ end-to-end combo enumeration pipeline
```

### Test Status
- **Unit Tests:** 288 passing
- **Property Tests:** 20 tests (9 pass, 11 skip without engine)
- **Regression Tests:** Known-count tests implemented
- **Integration Tests:** Require engine (YGOPRO_SCRIPTS_PATH)

Total: **288 passed, 2 skipped** (engine-dependent)

### Completed Features
- ✅ CFFI engine integration
- ✅ Exhaustive combo enumeration (IDDFS)
- ✅ Transposition table with instrumentation
- ✅ Parallel search infrastructure
- ✅ Card role classification
- ✅ ML-compatible state encoding
- ✅ Checkpointing (save/resume) for single and parallel runs
- ✅ Combo ranking system
- ✅ Property-based testing with Hypothesis
- ✅ Known-count regression tests
- ✅ Stratified hand sampling (by role composition)
- ✅ End-to-end pipeline script

### Key Metrics
| Metric | Value |
|--------|-------|
| combo_enumeration.py | 923 lines (56% reduction from 2,096) |
| Test coverage | 288 tests |
| Property tests | 20 |
| Regression tests | 4 known-count hands |

## Next Steps (Priority Order)

### Short-Term
1. **Engine Integration Testing** - Set up YGOPRO_SCRIPTS_PATH for full test suite
2. **Gold Standard Combo Validation** - Verify A Bao A Qu + Caesar reachable
3. **Performance Benchmarking** - Measure throughput with sampling + parallel

### Medium-Term
1. **Differential Testing** - Build expert corpus for comparison
2. **Continue Monolith Decomposition** - Reduce combo_enumeration.py to ~300 lines

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
python3 -c "from src.ygo_combo import StratifiedSampler, ComboRanker, parallel_enumerate"

# Run pipeline (sampling → parallel enumeration → ranking)
python3 scripts/run_pipeline.py --samples 100 --workers 4

# Run pipeline with checkpointing
python3 scripts/run_pipeline.py --samples 500 --checkpoint-dir ./checkpoints

# Resume interrupted pipeline
python3 scripts/run_pipeline.py --checkpoint-dir ./checkpoints --resume
```

## Key Files

| File | Purpose |
|------|---------|
| `scripts/run_pipeline.py` | End-to-end pipeline (sampling → parallel → ranking) |
| `src/ygo_combo/combo_enumeration.py` | Core enumeration engine |
| `src/ygo_combo/ranking.py` | Combo scoring and ranking |
| `src/ygo_combo/sampling.py` | Stratified hand sampling |
| `src/ygo_combo/checkpoint.py` | Save/resume enumeration |
| `src/ygo_combo/search/parallel.py` | Parallel enumeration with checkpoints |
| `src/ygo_combo/search/transposition.py` | State memoization |
| `src/ygo_combo/search/iddfs.py` | Iterative deepening |
| `config/locked_library.json` | Card library (48 cards) |
| `CLAUDE.md` | Project guidelines |

## Reference Documents

| Document | Location |
|----------|----------|
| Architecture Overview | `docs/architecture/OVERVIEW.md` |
| Search Strategy | `docs/architecture/SEARCH_STRATEGY.md` |

## Recent Session (2026-01-26)

Implemented complete pipeline infrastructure:
1. **Stratified Sampling** (`sampling.py`) - Groups hands by role composition
2. **Parallel Checkpoints** (`search/parallel.py`) - Resume interrupted parallel runs
3. **Pipeline Script** (`scripts/run_pipeline.py`) - End-to-end workflow

```bash
git log --oneline -5
```
