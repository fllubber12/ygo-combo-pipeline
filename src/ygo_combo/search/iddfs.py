#!/usr/bin/env python3
"""
Iterative deepening wrapper for combo enumeration.

Searches at increasing depth limits to find shortest combos first.
Each iteration warms up the transposition table for the next.

Usage:
    from iterative_deepening import IterativeDeepeningSearch, SearchConfig

    config = SearchConfig(
        max_depth=25,
        target_score=100,  # Stop when S-tier board found
        time_budget=60.0,  # Or stop after 60 seconds
    )

    search = IterativeDeepeningSearch(engine, config)
    result = search.run()

    # Result contains best combo found at each depth
    print(f"Shortest combo: {result.shortest_combo}")
    print(f"Best board: {result.best_terminal}")

Architecture:
    For depth 1, 2, 3, ... max_depth:
        1. Set engine depth limit
        2. Run enumeration
        3. Collect terminals found at exactly this depth
        4. Check stopping conditions (target found, timeout, etc.)
        5. If not stopped, continue to next depth

    Transposition table persists across iterations, providing:
    - Faster re-exploration of shallow states
    - Pruning of already-explored branches
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Set
from pathlib import Path
import time
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SearchConfig:
    """
    Configuration for iterative deepening search.

    Attributes:
        max_depth: Maximum depth to search (absolute limit).
        min_depth: Starting depth (default 1).
        depth_step: Depth increment per iteration (default 1).
        target_score: Stop if terminal with this score found (None = no target).
        target_tier: Stop if terminal with this tier found (None = no target).
        time_budget: Maximum seconds to search (None = no limit).
        path_budget: Maximum total paths to explore (None = no limit).
        terminals_per_depth: Max terminals to keep per depth (memory limit).
        require_boss: Only count terminals with boss monsters.
        early_stop_on_any: Stop on first terminal at any depth.
        verbose: Print progress updates.
    """
    max_depth: int = 25
    min_depth: int = 1
    depth_step: int = 1
    target_score: Optional[float] = None
    target_tier: Optional[str] = None  # "S", "A", "B", "C"
    time_budget: Optional[float] = None
    path_budget: Optional[int] = None
    terminals_per_depth: int = 1000
    require_boss: bool = False
    early_stop_on_any: bool = False
    verbose: bool = True


@dataclass
class DepthResult:
    """
    Results from searching at a specific depth.

    Attributes:
        depth: The depth limit used.
        terminals_found: Number of terminals found at exactly this depth.
        terminals_total: Cumulative terminals found up to this depth.
        best_score: Best terminal score at this depth.
        best_tier: Best terminal tier at this depth.
        paths_explored: Paths explored in this iteration.
        duration_seconds: Time spent on this depth.
        new_terminals: List of new terminal hashes found.
    """
    depth: int
    terminals_found: int
    terminals_total: int
    best_score: float
    best_tier: str
    paths_explored: int
    duration_seconds: float
    new_terminals: List[str] = field(default_factory=list)


@dataclass
class SearchResult:
    """
    Complete results from iterative deepening search.

    Attributes:
        depths_searched: Number of depth iterations completed.
        total_terminals: Total unique terminals found.
        total_paths: Total paths explored across all iterations.
        total_duration: Total search time in seconds.
        best_score: Best terminal score found.
        best_tier: Best terminal tier found.
        best_depth: Depth at which best terminal was found.
        shortest_combo_depth: Depth of shortest successful combo.
        stopped_reason: Why search stopped (max_depth, target, timeout, etc.)
        depth_results: Per-depth statistics.
        best_terminals: Top terminals by score.
    """
    depths_searched: int
    total_terminals: int
    total_paths: int
    total_duration: float
    best_score: float
    best_tier: str
    best_depth: int
    shortest_combo_depth: Optional[int]
    stopped_reason: str
    depth_results: List[DepthResult] = field(default_factory=list)
    best_terminals: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# STOPPING CONDITIONS
# =============================================================================

class StoppingCondition:
    """Base class for search stopping conditions."""

    def should_stop(self, search_state: Dict[str, Any]) -> bool:
        """Check if search should stop."""
        raise NotImplementedError

    def reason(self) -> str:
        """Return reason for stopping."""
        raise NotImplementedError


class TargetScoreReached(StoppingCondition):
    """Stop when target score is reached."""

    def __init__(self, target_score: float):
        self.target_score = target_score
        self._reached = False

    def should_stop(self, state: Dict[str, Any]) -> bool:
        if state.get("best_score", 0) >= self.target_score:
            self._reached = True
            return True
        return False

    def reason(self) -> str:
        return f"target_score_reached ({self.target_score})"


class TargetTierReached(StoppingCondition):
    """Stop when target tier is reached."""

    TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "brick": 4}

    def __init__(self, target_tier: str):
        self.target_tier = target_tier
        self._reached = False

    def should_stop(self, state: Dict[str, Any]) -> bool:
        best_tier = state.get("best_tier", "brick")
        if self.TIER_ORDER.get(best_tier, 99) <= self.TIER_ORDER.get(self.target_tier, 99):
            self._reached = True
            return True
        return False

    def reason(self) -> str:
        return f"target_tier_reached ({self.target_tier})"


class TimeBudgetExhausted(StoppingCondition):
    """Stop when time budget is exhausted."""

    def __init__(self, budget_seconds: float):
        self.budget = budget_seconds
        self.start_time = time.perf_counter()

    def should_stop(self, state: Dict[str, Any]) -> bool:
        elapsed = time.perf_counter() - self.start_time
        return elapsed >= self.budget

    def reason(self) -> str:
        return f"time_budget_exhausted ({self.budget}s)"


class PathBudgetExhausted(StoppingCondition):
    """Stop when path budget is exhausted."""

    def __init__(self, budget_paths: int):
        self.budget = budget_paths

    def should_stop(self, state: Dict[str, Any]) -> bool:
        return state.get("total_paths", 0) >= self.budget

    def reason(self) -> str:
        return f"path_budget_exhausted ({self.budget})"


class AnyTerminalFound(StoppingCondition):
    """Stop when any terminal is found (for quick validation)."""

    def __init__(self, require_boss: bool = False):
        self.require_boss = require_boss

    def should_stop(self, state: Dict[str, Any]) -> bool:
        if self.require_boss:
            return state.get("terminals_with_boss", 0) > 0
        return state.get("total_terminals", 0) > 0

    def reason(self) -> str:
        return "any_terminal_found"


# =============================================================================
# ITERATIVE DEEPENING SEARCH
# =============================================================================

class IterativeDeepeningSearch:
    """
    Iterative deepening search wrapper for combo enumeration.

    Wraps an EnumerationEngine and runs it at increasing depth limits.
    The transposition table is preserved across iterations for efficiency.
    """

    def __init__(
        self,
        engine_factory: Callable[[], Any],  # Returns EnumerationEngine
        config: SearchConfig,
    ):
        """
        Initialize iterative deepening search.

        Args:
            engine_factory: Callable that creates a fresh EnumerationEngine.
                           Called once; engine is reused across depths.
            config: SearchConfig with search parameters.
        """
        self.engine_factory = engine_factory
        self.config = config

        # Build stopping conditions
        self.stopping_conditions: List[StoppingCondition] = []
        if config.target_score is not None:
            self.stopping_conditions.append(TargetScoreReached(config.target_score))
        if config.target_tier is not None:
            self.stopping_conditions.append(TargetTierReached(config.target_tier))
        if config.time_budget is not None:
            self.stopping_conditions.append(TimeBudgetExhausted(config.time_budget))
        if config.path_budget is not None:
            self.stopping_conditions.append(PathBudgetExhausted(config.path_budget))
        if config.early_stop_on_any:
            self.stopping_conditions.append(AnyTerminalFound(config.require_boss))

        # State
        self.engine = None
        self.all_terminal_hashes: Set[str] = set()
        self.best_terminals: List[Dict[str, Any]] = []
        self.depth_results: List[DepthResult] = []

    def run(self) -> SearchResult:
        """
        Run iterative deepening search.

        Returns:
            SearchResult with all findings and statistics.
        """
        start_time = time.perf_counter()

        # Create engine (transposition table will persist)
        self.engine = self.engine_factory()

        total_paths = 0
        best_score = 0.0
        best_tier = "brick"
        best_depth = 0
        shortest_combo_depth = None
        stopped_reason = "max_depth_reached"

        # Iterate through depths
        for depth in range(self.config.min_depth, self.config.max_depth + 1, self.config.depth_step):
            if self.config.verbose:
                logger.info(f"Searching depth {depth}...")

            depth_start = time.perf_counter()

            # Run enumeration at this depth
            depth_result = self._search_at_depth(depth)

            depth_duration = time.perf_counter() - depth_start
            depth_result.duration_seconds = depth_duration
            self.depth_results.append(depth_result)

            total_paths += depth_result.paths_explored

            # Update best
            if depth_result.best_score > best_score:
                best_score = depth_result.best_score
                best_tier = depth_result.best_tier
                best_depth = depth

            # Track shortest combo
            if shortest_combo_depth is None and depth_result.terminals_found > 0:
                if not self.config.require_boss or self._has_boss_terminal(depth):
                    shortest_combo_depth = depth

            if self.config.verbose:
                logger.info(
                    f"  Depth {depth}: {depth_result.terminals_found} new terminals, "
                    f"best={depth_result.best_tier} ({depth_result.best_score:.0f}), "
                    f"{depth_result.paths_explored} paths, {depth_duration:.1f}s"
                )

            # Check stopping conditions
            search_state = {
                "depth": depth,
                "best_score": best_score,
                "best_tier": best_tier,
                "total_terminals": len(self.all_terminal_hashes),
                "terminals_with_boss": self._count_boss_terminals(),
                "total_paths": total_paths,
            }

            for condition in self.stopping_conditions:
                if condition.should_stop(search_state):
                    stopped_reason = condition.reason()
                    if self.config.verbose:
                        logger.info(f"  Stopping: {stopped_reason}")
                    break
            else:
                continue  # No condition triggered, continue to next depth
            break  # Condition triggered, exit loop

        total_duration = time.perf_counter() - start_time

        return SearchResult(
            depths_searched=len(self.depth_results),
            total_terminals=len(self.all_terminal_hashes),
            total_paths=total_paths,
            total_duration=total_duration,
            best_score=best_score,
            best_tier=best_tier,
            best_depth=best_depth,
            shortest_combo_depth=shortest_combo_depth,
            stopped_reason=stopped_reason,
            depth_results=self.depth_results,
            best_terminals=self.best_terminals[:10],  # Top 10
        )

    def _search_at_depth(self, depth: int) -> DepthResult:
        """
        Run enumeration at a specific depth limit.

        The engine's transposition table is preserved, so previously
        explored states will be skipped (hit in cache).
        """
        pre_terminal_count = len(self.all_terminal_hashes)
        pre_paths = getattr(self.engine, 'paths_explored', 0)

        # Run enumeration with depth limit
        terminals = self._run_engine_at_depth(depth)

        post_paths = getattr(self.engine, 'paths_explored', 0)

        # Process results
        new_terminals = []
        best_score = 0.0
        best_tier = "brick"

        for terminal in terminals:
            # Skip if already seen
            terminal_hash = terminal.get("board_hash")
            if terminal_hash is None:
                terminal_hash = terminal.get("state_hash", "")
            if terminal_hash in self.all_terminal_hashes:
                continue

            # Only count terminals at exactly this depth
            if terminal.get("depth", 0) != depth:
                continue

            self.all_terminal_hashes.add(terminal_hash)
            new_terminals.append(terminal_hash)

            # Track best
            score = terminal.get("score", 0)
            tier = terminal.get("tier", "brick")
            if score > best_score:
                best_score = score
                best_tier = tier

            # Add to best terminals list
            self.best_terminals.append(terminal)

        # Sort and trim best terminals
        self.best_terminals.sort(key=lambda t: t.get("score", 0), reverse=True)
        self.best_terminals = self.best_terminals[:self.config.terminals_per_depth]

        return DepthResult(
            depth=depth,
            terminals_found=len(new_terminals),
            terminals_total=len(self.all_terminal_hashes),
            best_score=best_score,
            best_tier=best_tier,
            paths_explored=post_paths - pre_paths,
            duration_seconds=0.0,  # Filled in by caller
            new_terminals=new_terminals,
        )

    def _run_engine_at_depth(self, depth: int) -> List[Dict[str, Any]]:
        """
        Run the enumeration engine at a specific depth.

        This method calls the engine's enumerate_with_depth_limit if available,
        otherwise falls back to setting max_depth and running enumerate_all.
        """
        # Try the preferred method first
        if hasattr(self.engine, 'enumerate_with_depth_limit'):
            terminals = self.engine.enumerate_with_depth_limit(depth)
            return [t.to_dict() if hasattr(t, 'to_dict') else t for t in terminals]

        # Fallback: set max_depth and run
        if hasattr(self.engine, 'max_depth'):
            old_depth = self.engine.max_depth
            self.engine.max_depth = depth

            # Clear terminals but preserve transposition table
            if hasattr(self.engine, 'terminals'):
                self.engine.terminals = []
            if hasattr(self.engine, 'paths_explored'):
                self.engine.paths_explored = 0

            # Run enumeration
            if hasattr(self.engine, 'enumerate_all'):
                self.engine.enumerate_all()
            elif hasattr(self.engine, '_enumerate_recursive'):
                self.engine._enumerate_recursive([])

            self.engine.max_depth = old_depth

            terminals = getattr(self.engine, 'terminals', [])
            return [t.to_dict() if hasattr(t, 'to_dict') else t for t in terminals]

        # No compatible interface found
        raise NotImplementedError(
            "Engine must have enumerate_with_depth_limit() or max_depth attribute. "
            "See combo_enumeration.py for required interface."
        )

    def _has_boss_terminal(self, depth: int) -> bool:
        """Check if any terminal at this depth has a boss monster."""
        for terminal in self.best_terminals:
            if terminal.get("depth") == depth and terminal.get("has_boss", False):
                return True
        return False

    def _count_boss_terminals(self) -> int:
        """Count terminals with boss monsters."""
        return sum(1 for t in self.best_terminals if t.get("has_boss", False))


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def iterative_search(
    engine_factory: Callable[[], Any],
    max_depth: int = 25,
    target_tier: str = "A",
    time_budget: float = None,
    verbose: bool = True,
) -> SearchResult:
    """
    Convenience function for iterative deepening search.

    Args:
        engine_factory: Callable that creates EnumerationEngine.
        max_depth: Maximum depth to search.
        target_tier: Stop when this tier is reached.
        time_budget: Maximum seconds (None = no limit).
        verbose: Print progress.

    Returns:
        SearchResult with findings.
    """
    config = SearchConfig(
        max_depth=max_depth,
        target_tier=target_tier,
        time_budget=time_budget,
        verbose=verbose,
    )
    search = IterativeDeepeningSearch(engine_factory, config)
    return search.run()


def find_shortest_combo(
    engine_factory: Callable[[], Any],
    max_depth: int = 25,
    require_boss: bool = True,
) -> Optional[int]:
    """
    Find the shortest combo that produces a boss monster.

    Args:
        engine_factory: Callable that creates EnumerationEngine.
        max_depth: Maximum depth to search.
        require_boss: Require boss monster on final board.

    Returns:
        Depth of shortest combo, or None if not found.
    """
    config = SearchConfig(
        max_depth=max_depth,
        early_stop_on_any=True,
        require_boss=require_boss,
        verbose=False,
    )
    search = IterativeDeepeningSearch(engine_factory, config)
    result = search.run()
    return result.shortest_combo_depth


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================

def create_depth_limited_engine(
    lib,
    main_deck: List[int],
    extra_deck: List[int],
    max_depth: int,
    transposition_table=None,
) -> Any:
    """
    Create an EnumerationEngine with specific depth limit.

    This is a helper for integration with combo_enumeration.py.
    The transposition table can be passed in to preserve state
    across iterations.

    Args:
        lib: OCG library handle.
        main_deck: Main deck card list.
        extra_deck: Extra deck card list.
        max_depth: Maximum search depth.
        transposition_table: Optional existing TranspositionTable.

    Returns:
        Configured EnumerationEngine.
    """
    # Import here to avoid circular dependency
    from ..combo_enumeration import EnumerationEngine
    from .transposition import TranspositionTable

    engine = EnumerationEngine(
        lib=lib,
        main_deck=main_deck,
        extra_deck=extra_deck,
        verbose=False,
        dedupe_boards=True,
        dedupe_intermediate=True,
    )

    # Override max depth
    engine.max_depth = max_depth

    # Use provided transposition table if given
    if transposition_table is not None:
        engine.transposition_table = transposition_table

    return engine


# =============================================================================
# TESTS
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Iterative Deepening Tests")
    print("=" * 60)

    # Test 1: SearchConfig defaults
    print("\n1. SearchConfig:")
    config = SearchConfig()
    print(f"   max_depth: {config.max_depth}")
    print(f"   min_depth: {config.min_depth}")
    print(f"   depth_step: {config.depth_step}")
    assert config.max_depth == 25
    assert config.min_depth == 1

    # Test 2: Stopping conditions
    print("\n2. Stopping conditions:")

    # Target score
    cond = TargetScoreReached(100.0)
    assert not cond.should_stop({"best_score": 50})
    assert cond.should_stop({"best_score": 100})
    print("   TargetScoreReached: OK")

    # Target tier
    cond = TargetTierReached("A")
    assert not cond.should_stop({"best_tier": "B"})
    assert cond.should_stop({"best_tier": "A"})
    assert cond.should_stop({"best_tier": "S"})
    print("   TargetTierReached: OK")

    # Path budget
    cond = PathBudgetExhausted(1000)
    assert not cond.should_stop({"total_paths": 500})
    assert cond.should_stop({"total_paths": 1000})
    print("   PathBudgetExhausted: OK")

    # Any terminal
    cond = AnyTerminalFound()
    assert not cond.should_stop({"total_terminals": 0})
    assert cond.should_stop({"total_terminals": 1})
    print("   AnyTerminalFound: OK")

    # Test 3: DepthResult
    print("\n3. DepthResult:")
    result = DepthResult(
        depth=5,
        terminals_found=10,
        terminals_total=25,
        best_score=85.0,
        best_tier="A",
        paths_explored=1000,
        duration_seconds=1.5,
    )
    assert result.depth == 5
    assert result.terminals_found == 10
    print(f"   Created result for depth {result.depth}: OK")

    # Test 4: SearchResult
    print("\n4. SearchResult:")
    result = SearchResult(
        depths_searched=10,
        total_terminals=50,
        total_paths=5000,
        total_duration=30.0,
        best_score=100.0,
        best_tier="S",
        best_depth=8,
        shortest_combo_depth=5,
        stopped_reason="target_tier_reached",
    )
    assert result.best_tier == "S"
    assert result.shortest_combo_depth == 5
    print(f"   Best tier: {result.best_tier}, shortest: {result.shortest_combo_depth}: OK")

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
