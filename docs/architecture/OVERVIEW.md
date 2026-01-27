# Architecture Overview

## System Components

```
+---------------------------------------------------------------------------+
|                          YGO-COMBO-PIPELINE                                |
+---------------------------------------------------------------------------+

                            EXTERNAL DEPENDENCIES
+--------------------+  +------------------+  +-----------------------------+
|  ygopro-core       |  |  ygopro-scripts  |  |  cards.cdb (SQLite)         |
|  (C++ Engine)      |  |  (~13K Lua files)|  |  - Card data                |
+--------+-----------+  +--------+---------+  +--------------+--------------+
         +---------------------------+---------------------------+
                                 |
                    +------------v------------+
                    |     ENGINE LAYER        |
                    |  - CFFI bindings        |
                    |  - Message parsing      |
                    |  - State representation |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |     SEARCH LAYER        |
                    |  - DFS / IDDFS          |
                    |  - Transposition table  |
                    |  - Backtracking         |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |   ENUMERATION LAYER     |
                    |  - Action enumeration   |
                    |  - Message handlers     |
                    |  - Terminal recording   |
                    +------------+------------+
                                 |
                    +------------v------------+
                    |     OUTPUT LAYER        |
                    |  - Combo sequences      |
                    |  - ML encoding          |
                    +-------------------------+
```

## Data Flow

1. **Input:** Starting hand (5 card codes)
2. **Engine:** Create duel, set up decks, draw hand
3. **Search:** DFS/IDDFS explores action space
4. **Enumeration:** Handle MSG_* messages, enumerate choices
5. **Output:** List of terminal states with action sequences

## Key Design Decisions

See [Decision Log](DECISION_LOG.md) for detailed rationale.

- **IDDFS over MCTS:** We need complete enumeration, not optimization
- **Transposition tables:** Avoid re-exploring duplicate states
- **Failed choice tracking:** Proper backtracking on SELECT_SUM_CANCEL
- **Zobrist hashing:** O(1) incremental state hashing

## Module Hierarchy

```
ocg_bindings.py     -> Constants & CFFI (canonical source)
       |
paths.py            -> Centralized path configuration
       |
engine_interface.py -> Callbacks, parsing, EngineContext
       |
combo_enumeration.py, state_representation.py, transposition_table.py
```

## Key Files

| File | Purpose |
|------|---------|
| `src/cffi/ocg_bindings.py` | CFFI bindings, MSG_*/QUERY_* constants |
| `src/cffi/engine_interface.py` | EngineContext, callbacks, parsing |
| `src/cffi/combo_enumeration.py` | Core DFS enumeration engine |
| `src/cffi/state_representation.py` | BoardSignature, IntermediateState |
| `src/cffi/transposition_table.py` | Memoization cache |
| `src/cffi/zobrist.py` | O(1) incremental hashing |
| `src/cffi/iterative_deepening.py` | IDDFS search wrapper |
| `src/cffi/ml_encoding.py` | ML-compatible state encoding |
