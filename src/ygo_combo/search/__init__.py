"""
Search algorithms for combo enumeration.

This module provides:
- Iterative deepening search (iddfs.py)
- Transposition table for memoization (transposition.py)
- Parallel search across hands (parallel.py)
"""

from .iddfs import (
    SearchConfig,
    DepthResult,
    SearchResult,
    StoppingCondition,
    TargetScoreReached,
    TargetTierReached,
    TimeBudgetExhausted,
    PathBudgetExhausted,
    AnyTerminalFound,
    IterativeDeepeningSearch,
)

from .transposition import (
    TranspositionEntry,
    TranspositionTable,
)

from .parallel import (
    ParallelConfig,
    ComboResult,
    ParallelResult,
)

__all__ = [
    # IDDFS
    'SearchConfig',
    'DepthResult',
    'SearchResult',
    'StoppingCondition',
    'TargetScoreReached',
    'TargetTierReached',
    'TimeBudgetExhausted',
    'PathBudgetExhausted',
    'AnyTerminalFound',
    'IterativeDeepeningSearch',
    # Transposition
    'TranspositionEntry',
    'TranspositionTable',
    # Parallel
    'ParallelConfig',
    'ComboResult',
    'ParallelResult',
]
