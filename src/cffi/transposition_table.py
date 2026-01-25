"""
Transposition table for memoizing explored states.
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class TranspositionEntry:
    """Cached result for an intermediate state."""
    state_hash: str
    best_terminal_hash: str     # Best board reachable from here
    best_terminal_value: float  # Evaluation score (once we have it)
    depth_to_terminal: int      # How many actions to reach best terminal
    visit_count: int            # How many times we've seen this state


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
        """Remove least valuable entries when full."""
        # Simple strategy: remove oldest (FIFO)
        # Could improve: LRU, or prioritize by depth
        keys = list(self.table.keys())
        for key in keys[:len(keys)//10]:  # Remove 10%
            del self.table[key]

    def stats(self) -> dict:
        """Return cache statistics."""
        return {
            "size": len(self.table),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0,
        }
