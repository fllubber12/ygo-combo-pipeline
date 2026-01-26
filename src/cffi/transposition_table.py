"""
Transposition table for memoizing explored states.

Uses Zobrist hashing for O(1) incremental updates when available,
with fallback to string hashes for backwards compatibility.
"""

from typing import Dict, Optional, Union
from dataclasses import dataclass


@dataclass
class TranspositionEntry:
    """
    Cached result for an intermediate state.

    Note: Intentionally mutable (not frozen). The visit_count field is
    incremented on cache hits to track access frequency for eviction decisions.

    Attributes:
        state_hash: Hash of the intermediate state (int for Zobrist, str for MD5).
        best_terminal_hash: Hash of best terminal board reachable from here (if known).
        best_terminal_value: Evaluation score of best terminal (if known).
        creation_depth: The search depth at which this entry was created.
            Higher depth = closer to terminal = more valuable for eviction.
        visit_count: How many times we've seen this state (mutated on lookup).
    """
    state_hash: Union[int, str]
    best_terminal_hash: Union[int, str]
    best_terminal_value: float
    creation_depth: int
    visit_count: int


class TranspositionTable:
    """
    Hash table for caching explored game states.

    Key insight: If we reach the same IntermediateState via different
    action sequences, the optimal continuation is identical.

    Supports both integer (Zobrist) and string (MD5) hashes for flexibility
    during migration.

    Attributes:
        table: Dictionary mapping state hashes to TranspositionEntry
        max_size: Maximum number of entries before eviction
        hits: Number of successful lookups
        misses: Number of failed lookups
    """

    def __init__(self, max_size: int = 1_000_000):
        """
        Initialize the transposition table.

        Args:
            max_size: Maximum entries before eviction triggers.
                     Default 1M entries ≈ 100-200MB depending on entry size.
        """
        self.table: Dict[Union[int, str], TranspositionEntry] = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def lookup(self, state_hash: Union[int, str]) -> Optional[TranspositionEntry]:
        """
        Check if state has been explored.

        Args:
            state_hash: Zobrist hash (int) or MD5 hash (str) of the state.

        Returns:
            TranspositionEntry if found, None otherwise.
            Note: visit_count is incremented on hit.
        """
        entry = self.table.get(state_hash)
        if entry:
            self.hits += 1
            entry.visit_count += 1
            return entry
        self.misses += 1
        return None

    def store(self, state_hash: Union[int, str], entry: TranspositionEntry):
        """
        Store result for a state.

        Args:
            state_hash: Zobrist hash (int) or MD5 hash (str) of the state.
            entry: TranspositionEntry to store.
        """
        if len(self.table) >= self.max_size:
            self._evict()
        self.table[state_hash] = entry

    def _evict(self):
        """
        Remove least valuable entries when full.

        Strategy: Prioritize keeping entries with higher creation_depth
        (states discovered deeper in the search tree are closer to terminals
        and more valuable to cache for avoiding redundant exploration).
        Entries with high visit counts are also more valuable.

        Removes bottom 10% by (creation_depth, visit_count).
        """
        if not self.table:
            return

        # Sort by (creation_depth, visit_count) ascending
        # Remove shallow/low-visit entries first
        sorted_entries = sorted(
            self.table.items(),
            key=lambda x: (x[1].creation_depth, x[1].visit_count)
        )

        # Remove bottom 10%
        to_remove = max(1, len(sorted_entries) // 10)
        for key, _ in sorted_entries[:to_remove]:
            del self.table[key]

    def clear(self):
        """Clear all entries and reset statistics."""
        self.table.clear()
        self.hits = 0
        self.misses = 0

    def stats(self) -> dict:
        """
        Return cache statistics.

        Returns:
            Dictionary with size, hits, misses, hit_rate, and depth distribution.
        """
        total = self.hits + self.misses
        
        # Calculate depth distribution
        depth_counts: Dict[int, int] = {}
        for entry in self.table.values():
            depth = entry.creation_depth
            depth_counts[depth] = depth_counts.get(depth, 0) + 1
        
        return {
            "size": len(self.table),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / total if total > 0 else 0.0,
            "depth_distribution": depth_counts,
            "avg_depth": (
                sum(d * c for d, c in depth_counts.items()) / len(self.table)
                if self.table else 0.0
            ),
        }

    def __len__(self) -> int:
        """Return number of entries in the table."""
        return len(self.table)

    def __contains__(self, state_hash: Union[int, str]) -> bool:
        """Check if a hash exists in the table (without updating stats)."""
        return state_hash in self.table


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("TranspositionTable Tests")
    print("=" * 40)

    # Test 1: Basic store and lookup
    print("\n1. Basic store/lookup:")
    tt = TranspositionTable(max_size=100)

    entry = TranspositionEntry(
        state_hash=0x123456789ABCDEF0,
        best_terminal_hash=0xFEDCBA9876543210,
        best_terminal_value=85.0,
        creation_depth=5,
        visit_count=1,
    )
    tt.store(0x123456789ABCDEF0, entry)

    result = tt.lookup(0x123456789ABCDEF0)
    assert result is not None
    assert result.best_terminal_value == 85.0
    assert result.visit_count == 2  # Incremented on lookup
    print("   Store and lookup: ✓")

    # Test 2: Miss returns None
    print("\n2. Miss handling:")
    miss_result = tt.lookup(0xDEADBEEF)
    assert miss_result is None
    print("   Miss returns None: ✓")

    # Test 3: Stats tracking
    print("\n3. Stats tracking:")
    stats = tt.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1
    print(f"   Hits: {stats['hits']}, Misses: {stats['misses']}")
    print("   Stats tracking: ✓")

    # Test 4: Eviction (depth-preferred)
    print("\n4. Eviction strategy:")
    tt_small = TranspositionTable(max_size=10)

    # Add entries with varying depths
    for i in range(10):
        e = TranspositionEntry(
            state_hash=i,
            best_terminal_hash=0,
            best_terminal_value=0.0,
            creation_depth=i,  # Depth 0-9
            visit_count=1,
        )
        tt_small.store(i, e)

    assert len(tt_small) == 10

    # Add one more - should trigger eviction
    e = TranspositionEntry(
        state_hash=100,
        best_terminal_hash=0,
        best_terminal_value=0.0,
        creation_depth=10,
        visit_count=1,
    )
    tt_small.store(100, e)

    # Shallow entries (depth 0) should be evicted first
    assert 0 not in tt_small  # Depth 0 evicted
    assert 9 in tt_small  # Depth 9 kept
    assert 100 in tt_small  # New entry present
    print("   Depth-preferred eviction: ✓")

    # Test 5: String hash support (backwards compatibility)
    print("\n5. String hash support:")
    tt.store("abc123def456", TranspositionEntry(
        state_hash="abc123def456",
        best_terminal_hash="xyz789",
        best_terminal_value=50.0,
        creation_depth=3,
        visit_count=1,
    ))
    str_result = tt.lookup("abc123def456")
    assert str_result is not None
    assert str_result.best_terminal_value == 50.0
    print("   String hash support: ✓")

    print("\n" + "=" * 40)
    print("All tests passed! ✓")
