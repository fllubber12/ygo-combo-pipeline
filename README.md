# Yu-Gi-Oh! Combo Enumeration Pipeline

A research project for exhaustively enumerating combo paths in Yu-Gi-Oh! using the ygopro-core engine via CFFI bindings.

## Project Status

**Phase 1: Complete** ✅
- State representation (BoardSignature, IntermediateState)
- Transposition table with 39.3% hit rate
- Basic enumeration engine
- 26-card Fiendsmith library verified

**Phase 2: In Progress** 🔄
- Search strategy optimization
- State space analysis

## Quick Start

```bash
# Requires: Python 3.10+, ygopro-core built as libygo.dylib

cd src/cffi
python combo_enumeration.py --max-depth 25 --max-paths 1000
```

## Key Results

- Caesar (Rank 6 Xyz) found at depth 23
- S:P Little Knight found at depth 17+
- 150 unique terminal boards discovered
- Problem identified: DFS exhausts suboptimal branches first

## Documentation

- [Research Report](docs/RESEARCH.md) - Algorithm analysis, related work, design decisions
- [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP.md) - Prioritized improvements (P0-P4)
- [Roadmap](docs/COMBO_PIPELINE_ROADMAP.md) - Comprehensive project plan
- [Architecture Research](docs/ARCHITECTURE_RESEARCH.md) - Technical design notes
- [Project Inventory](docs/PROJECT_INVENTORY.md) - File structure reference

## Structure

```
├── src/cffi/                    # Core enumeration engine
│   ├── ocg_bindings.py              # CFFI bindings, constants
│   ├── engine_interface.py          # EngineContext, callbacks
│   ├── paths.py                     # Path configuration
│   ├── combo_enumeration.py         # Main DFS traversal
│   ├── state_representation.py      # Board hashing
│   ├── transposition_table.py       # Memoization cache
│   ├── zobrist.py                   # O(1) Zobrist hashing
│   ├── parallel_search.py           # Parallel enumeration
│   ├── card_roles.py                # Card role classification
│   └── iterative_deepening.py       # Depth-limited search
├── config/                      # Configuration files
│   ├── locked_library.json          # 26-card library
│   └── card_roles.json              # Card role overrides
├── docs/                        # Documentation
│   ├── RESEARCH.md                  # Algorithm research
│   └── IMPLEMENTATION_ROADMAP.md    # P0-P4 priorities
└── tests/                       # Test suite
    └── unit/
        ├── test_state.py            # State representation tests
        ├── test_zobrist.py          # Zobrist hashing tests
        ├── test_parallel.py         # Parallel search tests
        ├── test_card_roles.py       # Card role tests
        └── test_iterative_deepening.py  # Iterative deepening tests
```

## Dependencies

- Python 3.10+
- ygopro-core (edo9300 fork)
- cffi

## License

Research project - not for commercial use.
