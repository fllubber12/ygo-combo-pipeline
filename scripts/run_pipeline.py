#!/usr/bin/env python3
"""
End-to-end combo enumeration pipeline.

Connects sampling → parallel enumeration → ranking into a single workflow.

Usage:
    python scripts/run_pipeline.py --samples 100 --workers 4
    python scripts/run_pipeline.py --deck config/my_deck.json --samples 500
    python scripts/run_pipeline.py --resume  # Resume from checkpoint

Example workflow:
    1. Load deck from locked_library.json (or custom deck file)
    2. Classify cards by role (starter, extender, payoff, garnet)
    3. Sample representative hands using stratified sampling
    4. Run parallel enumeration across sampled hands
    5. Rank discovered combos by quality
    6. Output summary report
"""

import argparse
import json
import logging
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from ygo_combo.sampling import (
    StratifiedSampler,
    SamplingConfig,
    SamplingResult,
    HandComposition,
)
from ygo_combo.cards.roles import CardRoleClassifier, CardRole
from ygo_combo.search.parallel import (
    ParallelConfig,
    ParallelResult,
    parallel_enumerate,
)
from ygo_combo.ranking import ComboRanker, ComboScore, rank_terminals
from ygo_combo.types import TerminalState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class PipelineConfig:
    """Configuration for the combo enumeration pipeline."""
    # Deck source
    deck_path: Optional[Path] = None
    roles_path: Optional[Path] = None

    # Fixed hand (skips sampling)
    fixed_hand: Optional[str] = None

    # Sampling
    total_samples: int = 100
    min_per_stratum: int = 1
    prioritize_playable: bool = True
    sample_seed: Optional[int] = None

    # Enumeration
    num_workers: Optional[int] = None
    max_depth: int = 25
    max_paths_per_hand: int = 0

    # Checkpointing
    checkpoint_dir: Optional[Path] = None
    checkpoint_interval: int = 50
    resume: bool = False

    # Output
    output_path: Optional[Path] = None
    top_k: int = 10
    verbose: bool = False


@dataclass
class PipelineResult:
    """Results from running the pipeline."""
    # Sampling stats
    total_hand_space: int
    hands_sampled: int
    strata_count: int
    playable_fraction: float

    # Enumeration stats
    hands_processed: int
    unique_terminals: int
    total_paths: int
    enumeration_time: float

    # Ranking stats
    top_combos: List[ComboScore]
    tier_distribution: Dict[str, int]

    # Timing
    total_time: float


# =============================================================================
# DECK LOADING
# =============================================================================

def load_deck(deck_path: Optional[Path] = None) -> Tuple[List[int], List[int]]:
    """Load deck from JSON file.

    Args:
        deck_path: Path to deck JSON. If None, uses locked_library.json.

    Returns:
        Tuple of (main_deck, extra_deck) as lists of passcodes.
    """
    if deck_path is None:
        # Use default locked library
        default_path = Path(__file__).parents[1] / "config" / "locked_library.json"
        if not default_path.exists():
            raise FileNotFoundError(
                f"Default deck not found at {default_path}. "
                "Please specify --deck or create locked_library.json"
            )
        deck_path = default_path

    with open(deck_path) as f:
        data = json.load(f)

    # Handle different deck formats
    if "main_deck" in data:
        # Standard format: {"main_deck": [...], "extra_deck": [...]}
        main_deck = [int(c) for c in data["main_deck"]]
        extra_deck = [int(c) for c in data.get("extra_deck", [])]
    elif "cards" in data:
        # Locked library format: {"cards": {"passcode": {...}, ...}}
        cards = data["cards"]
        main_deck = []
        extra_deck = []
        for code_str, card_data in cards.items():
            code = int(code_str)
            count = card_data.get("count", 1)
            is_extra = card_data.get("is_extra_deck", False)
            for _ in range(count):
                if is_extra:
                    extra_deck.append(code)
                else:
                    main_deck.append(code)
    else:
        raise ValueError(f"Unknown deck format in {deck_path}")

    logger.info(f"Loaded deck: {len(main_deck)} main, {len(extra_deck)} extra")
    return main_deck, extra_deck


def load_classifier(roles_path: Optional[Path] = None) -> CardRoleClassifier:
    """Load card role classifier.

    Args:
        roles_path: Path to roles JSON. If None, uses default card_roles.json.

    Returns:
        Configured CardRoleClassifier.
    """
    if roles_path is None:
        default_path = Path(__file__).parents[1] / "config" / "card_roles.json"
        if default_path.exists():
            roles_path = default_path

    if roles_path and roles_path.exists():
        classifier = CardRoleClassifier.from_config(roles_path)
        logger.info(f"Loaded {len(classifier._classifications)} card classifications")
    else:
        classifier = CardRoleClassifier()
        logger.warning("No card roles file found. Using heuristic classification.")

    return classifier


# =============================================================================
# CARD LOOKUP
# =============================================================================

def lookup_card_by_name(name: str, db_path: Path) -> Optional[int]:
    """Look up a card's passcode by its name in the card database.

    Args:
        name: Card name to search for.
        db_path: Path to cards.cdb database.

    Returns:
        Card passcode if found, None otherwise.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT id FROM texts WHERE name = ? COLLATE NOCASE",
            (name,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
    except sqlite3.Error:
        pass
    return None


def lookup_card_by_name_fuzzy(name: str, db_path: Path) -> List[Tuple[int, str]]:
    """Fuzzy search for cards by name.

    Args:
        name: Partial card name to search for.
        db_path: Path to cards.cdb database.

    Returns:
        List of (passcode, name) tuples that match.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT id, name FROM texts WHERE name LIKE ? COLLATE NOCASE LIMIT 10",
            (f"%{name}%",)
        )
        results = cursor.fetchall()
        conn.close()
        return results
    except sqlite3.Error:
        return []


def resolve_hand_spec(hand_spec: str, db_path: Path) -> Tuple[List[int], List[str]]:
    """Resolve a hand specification to card codes.

    Args:
        hand_spec: Comma-separated list of card codes or names.
        db_path: Path to cards.cdb database.

    Returns:
        Tuple of (resolved_codes, resolved_names).

    Raises:
        ValueError: If any card cannot be resolved.
    """
    items = [item.strip() for item in hand_spec.split(",")]
    codes = []
    names = []
    errors = []

    for item in items:
        if not item:
            continue

        # Try as integer passcode first
        try:
            code = int(item)
            # Verify it exists in DB
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                "SELECT name FROM texts WHERE id = ?", (code,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                codes.append(code)
                names.append(row[0])
            else:
                errors.append(f"Unknown card code: {code}")
            continue
        except ValueError:
            pass

        # Try as card name
        code = lookup_card_by_name(item, db_path)
        if code:
            codes.append(code)
            names.append(item)
        else:
            # Try fuzzy match for suggestions
            matches = lookup_card_by_name_fuzzy(item, db_path)
            if matches:
                suggestions = ", ".join(f'"{m[1]}"' for m in matches[:3])
                errors.append(f'Card not found: "{item}". Did you mean: {suggestions}?')
            else:
                errors.append(f'Card not found: "{item}"')

    if errors:
        raise ValueError("\n".join(errors))

    return codes, names


# =============================================================================
# FIXED HAND ENUMERATION
# =============================================================================

def run_fixed_hand(
    hand_codes: List[int],
    hand_names: List[str],
    deck: List[int],
    config: PipelineConfig,
) -> PipelineResult:
    """Run enumeration for a specific fixed hand.

    Args:
        hand_codes: List of card passcodes for the hand.
        hand_names: List of card names (for display).
        deck: Full deck list.
        config: Pipeline configuration.

    Returns:
        PipelineResult with enumeration results.
    """
    start_time = time.perf_counter()

    logger.info("=" * 60)
    logger.info("FIXED HAND ENUMERATION")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Print resolved hand
    logger.info("\nResolved hand:")
    for i, (code, name) in enumerate(zip(hand_codes, hand_names), 1):
        logger.info(f"  {i}. {name} ({code})")

    # Determine checkpoint path
    checkpoint_path = None
    if config.checkpoint_dir:
        config.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = config.checkpoint_dir / "fixed_hand_checkpoint"

    # Create parallel config for single hand
    parallel_config = ParallelConfig(
        deck=deck,
        hand_size=len(hand_codes),
        num_workers=config.num_workers,
        max_depth=config.max_depth,
        max_paths_per_hand=config.max_paths_per_hand,
        checkpoint_path=checkpoint_path,
        checkpoint_interval=config.checkpoint_interval,
        resume=config.resume,
        fixed_hands=[tuple(hand_codes)],  # Only enumerate this hand
    )

    logger.info(f"\nEnumerating fixed hand with {parallel_config.num_workers} workers")
    logger.info(f"Max depth: {config.max_depth}, Max paths: {config.max_paths_per_hand or 'unlimited'}")

    if checkpoint_path:
        logger.info(f"Checkpoints: {checkpoint_path}")

    # Run enumeration
    logger.info("\n=== Enumeration ===")
    enum_result = parallel_enumerate(parallel_config)

    logger.info(f"Hands processed: {enum_result.total_hands:,}")
    logger.info(f"Unique terminals: {enum_result.total_terminals:,}")
    logger.info(f"Total paths explored: {enum_result.total_paths:,}")
    logger.info(f"Duration: {enum_result.duration_seconds:.1f}s")

    if enum_result.best_hand:
        logger.info(f"\nBest hand found: {enum_result.best_hand}")
        logger.info(f"Best score: {enum_result.best_score:.1f}")

    total_time = time.perf_counter() - start_time

    # Build result
    result = PipelineResult(
        total_hand_space=1,  # Fixed hand = 1 hand
        hands_sampled=1,
        strata_count=1,
        playable_fraction=1.0,
        hands_processed=enum_result.total_hands,
        unique_terminals=enum_result.total_terminals,
        total_paths=enum_result.total_paths,
        enumeration_time=enum_result.duration_seconds,
        top_combos=[],
        tier_distribution={},
        total_time=total_time,
    )

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("FIXED HAND ENUMERATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total time: {total_time:.1f}s")
    logger.info(f"Unique terminals: {result.unique_terminals:,}")
    logger.info(f"Total paths: {result.total_paths:,}")

    # Save output if requested
    if config.output_path:
        save_report(result, config.output_path)
        logger.info(f"Report saved to: {config.output_path}")

    return result


# =============================================================================
# PIPELINE STAGES
# =============================================================================

def run_sampling(
    deck: List[int],
    classifier: CardRoleClassifier,
    config: PipelineConfig,
) -> SamplingResult:
    """Run stratified sampling on the hand space.

    Args:
        deck: List of card passcodes.
        classifier: Card role classifier.
        config: Pipeline configuration.

    Returns:
        SamplingResult with selected hands.
    """
    logger.info("=== Stage 1: Sampling ===")

    sampler = StratifiedSampler(
        deck=deck,
        classifier=classifier,
        hand_size=5,
    )

    sampling_config = SamplingConfig(
        total_samples=config.total_samples,
        min_per_stratum=config.min_per_stratum,
        prioritize_playable=config.prioritize_playable,
        seed=config.sample_seed,
    )

    result = sampler.sample(sampling_config)

    # Calculate playable fraction
    playable_count = sum(
        1 for h in result.hands
        if sampler._classify_hand(h).is_playable()
    )
    playable_fraction = playable_count / len(result.hands) if result.hands else 0

    logger.info(f"Total hand space: {sampler.total_hands:,}")
    logger.info(f"Strata discovered: {len(sampler.strata)}")
    logger.info(f"Hands sampled: {len(result.hands)}")
    logger.info(f"Playable hands: {playable_count} ({100*playable_fraction:.1f}%)")

    if config.verbose:
        # Show strata breakdown
        summary = sampler.get_strata_summary()
        logger.info("\nTop strata by size:")
        sorted_strata = sorted(
            summary.items(),
            key=lambda x: x[1]["count"],
            reverse=True,
        )[:5]
        for key, stats in sorted_strata:
            logger.info(
                f"  {stats['composition']}: {stats['count']} hands "
                f"(quality={stats['quality_score']:.1f})"
            )

    return result


def run_enumeration(
    hands: List[Tuple[int, ...]],
    deck: List[int],
    config: PipelineConfig,
) -> ParallelResult:
    """Run parallel enumeration across sampled hands.

    Args:
        hands: List of starting hands to enumerate.
        deck: Full deck list (for worker initialization).
        config: Pipeline configuration.

    Returns:
        ParallelResult with enumeration statistics.
    """
    logger.info("=== Stage 2: Enumeration ===")

    # Determine checkpoint path
    checkpoint_path = None
    if config.checkpoint_dir:
        config.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_path = config.checkpoint_dir / "pipeline_checkpoint"

    # Create a custom deck list for enumeration
    # (hands are already selected, so we enumerate each one)
    parallel_config = ParallelConfig(
        deck=deck,
        hand_size=5,
        num_workers=config.num_workers,
        max_depth=config.max_depth,
        max_paths_per_hand=config.max_paths_per_hand,
        checkpoint_path=checkpoint_path,
        checkpoint_interval=config.checkpoint_interval,
        resume=config.resume,
    )

    logger.info(f"Enumerating {len(hands)} hands with {parallel_config.num_workers} workers")
    logger.info(f"Max depth: {config.max_depth}, Max paths/hand: {config.max_paths_per_hand or 'unlimited'}")

    if checkpoint_path:
        logger.info(f"Checkpoints: {checkpoint_path}")

    # Note: parallel_enumerate processes all C(n,k) hands from deck.
    # For sampled hands, we need a different approach.
    # For now, we'll run the full parallel enumerate but this could be optimized
    # to only process the sampled hands.

    result = parallel_enumerate(parallel_config)

    logger.info(f"Hands processed: {result.total_hands:,}")
    logger.info(f"Unique terminals: {result.total_terminals:,}")
    logger.info(f"Total paths explored: {result.total_paths:,}")
    logger.info(f"Duration: {result.duration_seconds:.1f}s")
    logger.info(f"Rate: {result.total_hands / result.duration_seconds:.1f} hands/sec")

    return result


def run_ranking(
    terminals: List[TerminalState],
    config: PipelineConfig,
) -> Tuple[List[ComboScore], Dict[str, int]]:
    """Rank discovered combos by quality.

    Args:
        terminals: List of terminal states from enumeration.
        config: Pipeline configuration.

    Returns:
        Tuple of (top_k_combos, tier_distribution).
    """
    logger.info("=== Stage 3: Ranking ===")

    if not terminals:
        logger.warning("No terminals to rank")
        return [], {}

    ranker = ComboRanker()

    # Score all terminals
    scores = rank_terminals(terminals, ranker)

    # Get tier distribution
    tier_dist: Dict[str, int] = {}
    for score in scores:
        tier_dist[score.tier] = tier_dist.get(score.tier, 0) + 1

    # Get top K
    top_k = scores[:config.top_k]

    logger.info(f"Ranked {len(scores)} terminals")
    logger.info(f"Tier distribution: {tier_dist}")

    if top_k:
        logger.info(f"\nTop {len(top_k)} combos:")
        for i, score in enumerate(top_k, 1):
            logger.info(
                f"  {i}. Tier {score.tier} | "
                f"Score: {score.overall:.1f} | "
                f"Depth: {score.depth} | "
                f"Power: {score.board_power:.1f}"
            )

    return top_k, tier_dist


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Run the complete combo enumeration pipeline.

    Args:
        config: Pipeline configuration.

    Returns:
        PipelineResult with all statistics.
    """
    start_time = time.perf_counter()

    logger.info("=" * 60)
    logger.info("COMBO ENUMERATION PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load deck and classifier
    main_deck, extra_deck = load_deck(config.deck_path)
    full_deck = main_deck + extra_deck
    classifier = load_classifier(config.roles_path)

    # Stage 1: Sampling
    sampling_result = run_sampling(full_deck, classifier, config)

    # Stage 2: Enumeration
    # Note: Currently enumerates all hands. Future optimization could
    # enumerate only the sampled hands.
    enum_result = run_enumeration(
        hands=sampling_result.hands,
        deck=full_deck,
        config=config,
    )

    # Stage 3: Ranking
    # Note: We don't have actual TerminalState objects from parallel enumeration yet.
    # The parallel result only contains hashes. Full ranking would require
    # storing terminal states or re-evaluating from hashes.
    top_combos: List[ComboScore] = []
    tier_dist: Dict[str, int] = {}

    if enum_result.best_hand:
        logger.info(f"\nBest hand found: {enum_result.best_hand}")
        logger.info(f"Best score: {enum_result.best_score:.1f}")

    total_time = time.perf_counter() - start_time

    # Build result
    sampler = StratifiedSampler(deck=full_deck, classifier=classifier, hand_size=5)
    playable_count = sum(
        1 for h in sampling_result.hands
        if sampler._classify_hand(h).is_playable()
    )

    result = PipelineResult(
        total_hand_space=sampler.total_hands,
        hands_sampled=len(sampling_result.hands),
        strata_count=len(sampler.strata),
        playable_fraction=playable_count / len(sampling_result.hands) if sampling_result.hands else 0,
        hands_processed=enum_result.total_hands,
        unique_terminals=enum_result.total_terminals,
        total_paths=enum_result.total_paths,
        enumeration_time=enum_result.duration_seconds,
        top_combos=top_combos,
        tier_distribution=tier_dist,
        total_time=total_time,
    )

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total time: {total_time:.1f}s")
    logger.info(f"Hand space: {result.total_hand_space:,}")
    logger.info(f"Hands sampled: {result.hands_sampled:,} ({100*result.hands_sampled/result.total_hand_space:.2f}%)")
    logger.info(f"Unique terminals: {result.unique_terminals:,}")
    logger.info(f"Total paths: {result.total_paths:,}")

    # Save output if requested
    if config.output_path:
        save_report(result, config.output_path)
        logger.info(f"Report saved to: {config.output_path}")

    return result


def save_report(result: PipelineResult, path: Path):
    """Save pipeline results to JSON file."""
    report = {
        "timestamp": datetime.now().isoformat(),
        "sampling": {
            "total_hand_space": result.total_hand_space,
            "hands_sampled": result.hands_sampled,
            "strata_count": result.strata_count,
            "playable_fraction": result.playable_fraction,
        },
        "enumeration": {
            "hands_processed": result.hands_processed,
            "unique_terminals": result.unique_terminals,
            "total_paths": result.total_paths,
            "duration_seconds": result.enumeration_time,
        },
        "ranking": {
            "top_combos": [
                {
                    "tier": c.tier,
                    "overall_score": c.overall,
                    "board_power": c.board_power,
                    "depth": c.depth,
                }
                for c in result.top_combos
            ],
            "tier_distribution": result.tier_distribution,
        },
        "total_time_seconds": result.total_time,
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2)


# =============================================================================
# CLI
# =============================================================================

def main():
    """Command-line interface for the pipeline."""
    parser = argparse.ArgumentParser(
        description="Run the combo enumeration pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Deck options
    parser.add_argument(
        "--deck", "-d",
        type=Path,
        help="Path to deck JSON file (default: config/locked_library.json)",
    )
    parser.add_argument(
        "--roles",
        type=Path,
        help="Path to card roles JSON (default: config/card_roles.json)",
    )

    # Fixed hand option (skips sampling)
    parser.add_argument(
        "--hand",
        type=str,
        help="Comma-separated card codes or names for a fixed starting hand "
             "(e.g., 'Engraver of the Mark,Ash Blossom,Ash Blossom,Ash Blossom,Droll & Lock Bird'). "
             "Skips random sampling when provided.",
    )

    # Sampling options
    parser.add_argument(
        "--samples", "-n",
        type=int,
        default=100,
        help="Number of hands to sample (default: 100)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducible sampling",
    )

    # Enumeration options
    parser.add_argument(
        "--workers", "-w",
        type=int,
        help="Number of worker processes (default: CPU count)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=25,
        help="Maximum search depth (default: 25)",
    )
    parser.add_argument(
        "--max-paths",
        type=int,
        default=0,
        help="Maximum paths per hand, 0=unlimited (default: 0)",
    )

    # Checkpoint options
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        help="Directory for checkpoint files",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing checkpoint",
    )

    # Output options
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Path for output report JSON",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of top combos to report (default: 10)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    config = PipelineConfig(
        deck_path=args.deck,
        roles_path=args.roles,
        fixed_hand=args.hand,
        total_samples=args.samples,
        sample_seed=args.seed,
        num_workers=args.workers,
        max_depth=args.max_depth,
        max_paths_per_hand=args.max_paths,
        checkpoint_dir=args.checkpoint_dir,
        resume=args.resume,
        output_path=args.output,
        top_k=args.top_k,
        verbose=args.verbose,
    )

    try:
        # Use fixed hand mode or standard pipeline
        if config.fixed_hand:
            # Resolve the hand specification
            db_path = Path(__file__).parents[1] / "cards.cdb"
            if not db_path.exists():
                logger.error(f"Card database not found at {db_path}")
                return 1

            try:
                hand_codes, hand_names = resolve_hand_spec(config.fixed_hand, db_path)
            except ValueError as e:
                logger.error(f"Error resolving hand:\n{e}")
                return 1

            # Validate hand size
            if len(hand_codes) != 5:
                logger.error(f"Hand must have exactly 5 cards, got {len(hand_codes)}")
                return 1

            # Load deck for enumeration
            main_deck, extra_deck = load_deck(config.deck_path)
            full_deck = main_deck + extra_deck

            result = run_fixed_hand(hand_codes, hand_names, full_deck, config)
        else:
            result = run_pipeline(config)
        return 0
    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
