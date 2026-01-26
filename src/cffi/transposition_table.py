"""
Transposition table for memoizing explored states.
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class TranspositionEntry:
    """
    Cached result for an intermediate state.

    Note: Intentionally mutable (not frozen). The visit_count field is
    incremented on cache hits to track access frequency for eviction decisions.

    Attributes:
        state_hash: Hash of the intermediate state.
        best_terminal_hash: Hash of best terminal board reachable from here (if known).
        best_terminal_value: Evaluation score of best terminal (if known).
        creation_depth: The search depth at which this entry was created.
            Higher depth = closer to terminal = more valuable for eviction.
        visit_count: How many times we've seen this state (mutated on lookup).
    """
    state_hash: str
    best_terminal_hash: str     # Best board reachable from here
    best_terminal_value: float  # Evaluation score (once we have it)
    creation_depth: int         # Depth at which this state was first seen
    visit_count: int            # How many times we've seen this state (mutated on lookup)


class TranspositionTable:
    """
    Hash table for caching explored game states.

    Key insight: If we reach the same IntermediateState via different
    action sequences, the optimal continuation is identical.
    """

    def __init__(self, max_size: int = 1_000_000):
        self.table: Dict[str, TranspositionEntry] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def lookup(self, state_hash: str) -> Optional[TranspositionEntry]:
        """Check if state has been explored."""
        entry = self.table.get(state_hash)
        if entry:
            self.hits += 1
            entry.visit_count += 1
            return entry
        self.misses += 1
        return None

    def store(self, state_hash: str, entry: TranspositionEntry):
        """Store result for a state."""
        if len(self.table) >= self.max_size:
            self._evict()
        self.table[state_hash] = entry

    def _evict(self):
        """Remove least valuable entries when full.

        Strategy: Prioritize keeping entries with higher creation_depth
        (states discovered deeper in the search tree are closer to terminals
        and more valuable to cache for avoiding redundant exploration).
        Entries with high visit counts are also more valuable.
        """
        if not self.table:
            return

        # Sort by (creation_depth, visit_count) ascending - remove shallow/low-visit entries first
        sorted_entries = sorted(
            self.table.items(),
            key=lambda x: (x[1].creation_depth, x[1].visit_count)
        )

        # Remove bottom 10%
        to_remove = max(1, len(sorted_entries) // 10)
        for key, _ in sorted_entries[:to_remove]:
            del self.table[key]

    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "size": len(self.table),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0,
        }
