#!/usr/bin/env python3
"""
Parallel combo enumeration across starting hands.

Distributes work across multiple processes for near-linear speedup.
Each worker independently enumerates combos from a subset of starting hands.

Usage:
    from parallel_search import parallel_enumerate, ParallelConfig

    config = ParallelConfig(
        deck=deck_list,
        hand_size=5,
        num_workers=8,
        max_depth=25,
    )
    results = parallel_enumerate(config)

Architecture:
    Main Process:
        - Generates all C(n,k) starting hands
        - Distributes hands to worker pool
        - Merges results from all workers

    Worker Process:
        - Receives batch of starting hands
        - For each hand: run DFS enumeration
        - Returns list of discovered combos
"""

import multiprocessing as mp
from multiprocessing import Pool, Manager
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional, FrozenSet, Callable
from itertools import combinations
from pathlib import Path
import time
import json
import logging

# Configure logging for main process
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(processName)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ParallelConfig:
    """Configuration for parallel combo enumeration.

    Attributes:
        deck: List of card passcodes in the deck (main + extra).
        hand_size: Number of cards to draw (default 5).
        num_workers: Number of parallel processes (default: CPU count).
        max_depth: Maximum search depth per hand.
        max_paths_per_hand: Maximum combo paths to find per hand (0 = unlimited).
        output_dir: Directory for worker result files (optional).
        batch_size: Hands per worker batch (default: auto-calculated).
        progress_interval: Seconds between progress updates (default: 10).
    """
    deck: List[int]
    hand_size: int = 5
    num_workers: Optional[int] = None
    max_depth: int = 25
    max_paths_per_hand: int = 0
    output_dir: Optional[Path] = None
    batch_size: Optional[int] = None
    progress_interval: float = 10.0

    def __post_init__(self):
        if self.num_workers is None:
            self.num_workers = mp.cpu_count()
        if self.batch_size is None:
            # Auto-calculate: aim for ~100 batches per worker for good load balancing
            total_hands = self._calculate_total_hands()
            self.batch_size = max(1, total_hands // (self.num_workers * 100))

    def _calculate_total_hands(self) -> int:
        """Calculate total number of unique starting hands."""
        from math import comb
        return comb(len(self.deck), self.hand_size)

    def total_hands(self) -> int:
        """Return total number of unique starting hands."""
        return self._calculate_total_hands()


@dataclass
class ComboResult:
    """Result from enumerating a single starting hand.

    Attributes:
        hand: The starting hand (tuple of passcodes).
        terminal_boards: List of unique terminal board hashes reached.
        best_score: Highest board evaluation score found.
        paths_explored: Number of action paths explored.
        depth_reached: Maximum depth reached during search.
        duration_ms: Time spent on this hand in milliseconds.
    """
    hand: Tuple[int, ...]
    terminal_boards: List[str]
    best_score: float
    paths_explored: int
    depth_reached: int
    duration_ms: float


@dataclass
class ParallelResult:
    """Aggregated results from parallel enumeration.

    Attributes:
        total_hands: Number of starting hands processed.
        total_terminals: Number of unique terminal boards found.
        total_paths: Total action paths explored across all hands.
        best_hand: Hand that produced the highest-scoring board.
        best_score: Highest board evaluation score.
        duration_seconds: Total wall-clock time.
        worker_stats: Per-worker statistics.
        terminal_distribution: Count of terminals per hand (histogram).
    """
    total_hands: int
    total_terminals: int
    total_paths: int
    best_hand: Optional[Tuple[int, ...]]
    best_score: float
    duration_seconds: float
    worker_stats: Dict[int, Dict[str, Any]]
    terminal_distribution: Dict[int, int] = field(default_factory=dict)


# =============================================================================
# WORKER FUNCTION
# =============================================================================

# Global worker state (initialized per-process)
_worker_deck: List[int] = []
_worker_max_depth: int = 25
_worker_max_paths: int = 0
_worker_engine_initialized: bool = False
_worker_lib = None
_worker_ffi = None
_worker_card_db_initialized: bool = False


def _worker_init(deck: List[int], max_depth: int, max_paths: int):
    """Initialize worker process with shared configuration.

    Called once per worker at pool creation time.
    Stores configuration in global variables accessible to worker function.
    """
    global _worker_deck, _worker_max_depth, _worker_max_paths
    global _worker_engine_initialized

    _worker_deck = deck
    _worker_max_depth = max_depth
    _worker_max_paths = max_paths
    _worker_engine_initialized = False


def _init_worker_engine():
    """Lazily initialize the engine in worker process.

    Called on first enumeration task to avoid import overhead at pool creation.
    """
    global _worker_engine_initialized, _worker_lib, _worker_ffi
    global _worker_card_db_initialized

    if _worker_engine_initialized:
        return

    # Import engine components
    from ..engine.interface import init_card_database, load_library, ffi, set_lib

    # Initialize card database (read-only, shared via copy-on-write)
    _worker_card_db_initialized = init_card_database()

    # Load library
    _worker_lib = load_library()
    _worker_ffi = ffi
    set_lib(_worker_lib)

    _worker_engine_initialized = True


def _enumerate_hand(hand: Tuple[int, ...]) -> ComboResult:
    """Enumerate all combos from a single starting hand.

    This is the core worker function. It initializes the engine if needed,
    then runs DFS enumeration from the given hand.

    Args:
        hand: Tuple of card passcodes representing the starting hand.

    Returns:
        ComboResult with discovered terminals and statistics.
    """
    import time
    start_time = time.perf_counter()

    # Lazy engine initialization
    _init_worker_engine()

    try:
        # Import enumeration logic
        from combo_enumeration import enumerate_from_hand

        # Run enumeration
        result = enumerate_from_hand(
            hand=hand,
            deck=_worker_deck,
            max_depth=_worker_max_depth,
            max_paths=_worker_max_paths,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000

        return ComboResult(
            hand=hand,
            terminal_boards=result.get("terminal_hashes", []),
            best_score=result.get("best_score", 0.0),
            paths_explored=result.get("paths_explored", 0),
            depth_reached=result.get("max_depth_reached", 0),
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(f"Error enumerating hand {hand}: {e}")
        return ComboResult(
            hand=hand,
            terminal_boards=[],
            best_score=0.0,
            paths_explored=0,
            depth_reached=0,
            duration_ms=duration_ms,
        )


def _worker_batch(hands: List[Tuple[int, ...]]) -> List[ComboResult]:
    """Process a batch of hands in a single worker.

    Args:
        hands: List of starting hands to enumerate.

    Returns:
        List of ComboResult for each hand.
    """
    return [_enumerate_hand(hand) for hand in hands]


# =============================================================================
# MAIN PARALLEL ENUMERATION
# =============================================================================

def generate_all_hands(deck: List[int], hand_size: int) -> List[Tuple[int, ...]]:
    """Generate all unique starting hands from deck.

    Args:
        deck: List of card passcodes.
        hand_size: Number of cards per hand.

    Returns:
        List of all C(n,k) unique hands as tuples.
    """
    # Sort deck for consistent ordering
    sorted_deck = sorted(deck)
    return list(combinations(sorted_deck, hand_size))


def parallel_enumerate(config: ParallelConfig) -> ParallelResult:
    """Run parallel combo enumeration across all starting hands.

    Args:
        config: ParallelConfig with deck, workers, depth settings.

    Returns:
        ParallelResult with aggregated statistics and discoveries.
    """
    start_time = time.perf_counter()

    # Generate all starting hands
    logger.info(f"Generating starting hands (deck size: {len(config.deck)}, hand size: {config.hand_size})")
    all_hands = generate_all_hands(config.deck, config.hand_size)
    total_hands = len(all_hands)
    logger.info(f"Total hands to process: {total_hands:,}")

    # Split into batches
    batches = []
    for i in range(0, total_hands, config.batch_size):
        batches.append(all_hands[i:i + config.batch_size])
    logger.info(f"Split into {len(batches):,} batches of ~{config.batch_size} hands")

    # Create process pool with initializer
    logger.info(f"Starting {config.num_workers} worker processes")

    all_results: List[ComboResult] = []
    worker_stats: Dict[int, Dict[str, Any]] = {}

    with Pool(
        processes=config.num_workers,
        initializer=_worker_init,
        initargs=(config.deck, config.max_depth, config.max_paths_per_hand),
    ) as pool:

        # Submit all batches
        async_results = []
        for batch in batches:
            async_results.append(pool.apply_async(_worker_batch, (batch,)))

        # Collect results with progress tracking
        completed = 0
        last_progress = time.perf_counter()

        for async_result in async_results:
            batch_results = async_result.get()  # Blocks until batch complete
            all_results.extend(batch_results)
            completed += len(batch_results)

            # Progress update
            now = time.perf_counter()
            if now - last_progress >= config.progress_interval:
                elapsed = now - start_time
                rate = completed / elapsed
                eta = (total_hands - completed) / rate if rate > 0 else 0
                logger.info(
                    f"Progress: {completed:,}/{total_hands:,} hands "
                    f"({100*completed/total_hands:.1f}%) - "
                    f"Rate: {rate:.1f} hands/sec - "
                    f"ETA: {eta:.0f}s"
                )
                last_progress = now

    # Aggregate results
    duration = time.perf_counter() - start_time

    # Find unique terminals across all hands
    all_terminals: set = set()
    total_paths = 0
    best_hand = None
    best_score = 0.0
    terminal_counts: Dict[int, int] = {}

    for result in all_results:
        all_terminals.update(result.terminal_boards)
        total_paths += result.paths_explored

        # Track best hand
        if result.best_score > best_score:
            best_score = result.best_score
            best_hand = result.hand

        # Histogram of terminals per hand
        count = len(result.terminal_boards)
        terminal_counts[count] = terminal_counts.get(count, 0) + 1

    logger.info(f"Completed {total_hands:,} hands in {duration:.1f}s")
    logger.info(f"Unique terminals: {len(all_terminals):,}")
    logger.info(f"Total paths explored: {total_paths:,}")
    logger.info(f"Best score: {best_score:.1f}")

    return ParallelResult(
        total_hands=total_hands,
        total_terminals=len(all_terminals),
        total_paths=total_paths,
        best_hand=best_hand,
        best_score=best_score,
        duration_seconds=duration,
        worker_stats=worker_stats,
        terminal_distribution=terminal_counts,
    )


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def enumerate_deck_parallel(
    deck: List[int],
    num_workers: Optional[int] = None,
    max_depth: int = 25,
    hand_size: int = 5,
) -> ParallelResult:
    """Convenience function for parallel enumeration with sensible defaults.

    Args:
        deck: List of card passcodes.
        num_workers: Number of workers (default: CPU count).
        max_depth: Maximum search depth.
        hand_size: Cards per starting hand.

    Returns:
        ParallelResult with all discoveries.
    """
    config = ParallelConfig(
        deck=deck,
        hand_size=hand_size,
        num_workers=num_workers,
        max_depth=max_depth,
    )
    return parallel_enumerate(config)


def estimate_runtime(
    deck_size: int,
    hand_size: int = 5,
    num_workers: int = 8,
    ms_per_hand: float = 100.0,
) -> Dict[str, Any]:
    """Estimate runtime for parallel enumeration.

    Args:
        deck_size: Number of cards in deck.
        hand_size: Cards per starting hand.
        num_workers: Number of parallel workers.
        ms_per_hand: Estimated milliseconds per hand (varies by deck).

    Returns:
        Dict with total_hands, estimated_seconds, estimated_hours.
    """
    from math import comb

    total_hands = comb(deck_size, hand_size)
    total_ms = total_hands * ms_per_hand
    parallel_ms = total_ms / num_workers
    seconds = parallel_ms / 1000
    hours = seconds / 3600

    return {
        "total_hands": total_hands,
        "estimated_seconds": seconds,
        "estimated_minutes": seconds / 60,
        "estimated_hours": hours,
        "hands_per_second": num_workers * (1000 / ms_per_hand),
    }


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Command-line interface for parallel enumeration."""
    import argparse
    import json
    from ..engine.paths import LOCKED_LIBRARY_PATH

    parser = argparse.ArgumentParser(
        description="Parallel combo enumeration across starting hands"
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=None,
        help="Number of worker processes (default: CPU count)"
    )
    parser.add_argument(
        "--max-depth", "-d",
        type=int,
        default=25,
        help="Maximum search depth (default: 25)"
    )
    parser.add_argument(
        "--hand-size", "-k",
        type=int,
        default=5,
        help="Cards per starting hand (default: 5)"
    )
    parser.add_argument(
        "--estimate",
        action="store_true",
        help="Only estimate runtime, don't run enumeration"
    )
    parser.add_argument(
        "--deck-file",
        type=Path,
        default=LOCKED_LIBRARY_PATH,
        help="Path to deck JSON file"
    )

    args = parser.parse_args()

    # Load deck
    with open(args.deck_file) as f:
        deck_data = json.load(f)

    deck = [int(code) for code in deck_data.get("cards", {}).keys()]
    logger.info(f"Loaded deck with {len(deck)} cards")

    if args.estimate:
        # Just estimate
        estimate = estimate_runtime(
            deck_size=len(deck),
            hand_size=args.hand_size,
            num_workers=args.workers or mp.cpu_count(),
        )
        print(f"\nRuntime Estimate:")
        print(f"  Total hands: {estimate['total_hands']:,}")
        print(f"  Workers: {args.workers or mp.cpu_count()}")
        print(f"  Estimated time: {estimate['estimated_minutes']:.1f} minutes")
        print(f"  Hands/second: {estimate['hands_per_second']:.1f}")
        return

    # Run enumeration
    result = enumerate_deck_parallel(
        deck=deck,
        num_workers=args.workers,
        max_depth=args.max_depth,
        hand_size=args.hand_size,
    )

    # Print summary
    print(f"\n{'='*60}")
    print("PARALLEL ENUMERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Hands processed:    {result.total_hands:,}")
    print(f"Unique terminals:   {result.total_terminals:,}")
    print(f"Total paths:        {result.total_paths:,}")
    print(f"Best score:         {result.best_score:.1f}")
    print(f"Duration:           {result.duration_seconds:.1f}s")
    print(f"Rate:               {result.total_hands/result.duration_seconds:.1f} hands/sec")

    if result.best_hand:
        print(f"\nBest hand: {result.best_hand}")


if __name__ == "__main__":
    main()
