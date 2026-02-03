#!/usr/bin/env python3
"""
Export Action Traces for Pattern Mining

Runs enumeration on specified hands and exports full action traces
for pattern mining analysis. Unlike the normal pipeline, this captures
the complete action sequence for each terminal, not just hashes.

Usage:
    # Single hand with card codes
    python scripts/export_traces.py --hand "60764609,81275020,14558127,14558127,14558127"

    # Single hand with card names
    python scripts/export_traces.py --hand "Fiendsmith Engraver,Speedroid Terrortop,Ash Blossom,Ash Blossom,Ash Blossom"

    # Random hands for sampling
    python scripts/export_traces.py --random 10 --output traces_sample.json

    # With path/depth limits
    python scripts/export_traces.py --hand "..." --max-paths 5000 --max-depth 30
"""

import argparse
import json
import logging
import random
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)


def lookup_card_by_name(name: str, db_path: Path) -> Optional[int]:
    """Look up a card's passcode by its name in the card database."""
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


def get_card_name(code: int, db_path: Path) -> str:
    """Get a card's name from its passcode."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM texts WHERE id = ?",
            (code,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
    except sqlite3.Error:
        pass
    return f"Unknown ({code})"


def resolve_hand_spec(hand_spec: str, db_path: Path) -> Tuple[List[int], List[str]]:
    """Resolve a hand specification to card codes and names."""
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
            name = get_card_name(code, db_path)
            codes.append(code)
            names.append(name)
            continue
        except ValueError:
            pass

        # Try as card name
        code = lookup_card_by_name(item, db_path)
        if code:
            codes.append(code)
            names.append(item)
        else:
            errors.append(f'Card not found: "{item}"')

    if errors:
        raise ValueError("\n".join(errors))

    return codes, names


def load_deck_pool(library_path: Path) -> List[Tuple[int, str]]:
    """Load main deck cards from locked_library.json."""
    with open(library_path) as f:
        library = json.load(f)

    deck_pool = []
    for passcode, card_data in library["cards"].items():
        if card_data.get("is_extra_deck", False):
            continue
        count = card_data.get("count", 1)
        name = card_data.get("name", f"Unknown ({passcode})")
        for _ in range(count):
            deck_pool.append((int(passcode), name))

    return deck_pool


def export_traces_for_hand(
    hand_codes: List[int],
    hand_names: List[str],
    max_depth: int,
    max_paths: int,
) -> Dict[str, Any]:
    """Run enumeration and export full action traces."""
    from ygo_combo.combo_enumeration import enumerate_from_hand

    logger.info(f"Enumerating hand with trace export:")
    for i, (code, name) in enumerate(zip(hand_codes, hand_names), 1):
        logger.info(f"  {i}. {name} ({code})")

    logger.info(f"Max depth: {max_depth}, Max paths: {max_paths}")

    # Run enumeration with trace export
    result = enumerate_from_hand(
        hand=tuple(hand_codes),
        max_depth=max_depth,
        max_paths=max_paths,
        include_traces=True,
    )

    logger.info(f"Paths explored: {result['paths_explored']}")
    logger.info(f"Unique terminals: {len(result['terminal_hashes'])}")
    logger.info(f"Best score: {result['best_score']}")
    if 'action_traces' in result:
        logger.info(f"Action traces captured: {len(result['action_traces'])}")

    return {
        "starting_hand": {
            "codes": hand_codes,
            "names": hand_names,
        },
        "enumeration": {
            "paths_explored": result["paths_explored"],
            "max_depth_reached": result["max_depth_reached"],
            "unique_terminals": len(result["terminal_hashes"]),
            "best_score": result["best_score"],
        },
        "action_traces": result.get("action_traces", []),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Export action traces for pattern mining",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Hand specification
    hand_group = parser.add_mutually_exclusive_group(required=True)
    hand_group.add_argument(
        "--hand",
        type=str,
        help="Comma-separated card codes or names for a fixed hand",
    )
    hand_group.add_argument(
        "--random",
        type=int,
        metavar="N",
        help="Sample N random hands from the deck",
    )

    # Enumeration parameters
    parser.add_argument(
        "--max-depth",
        type=int,
        default=30,
        help="Maximum search depth (default: 30)",
    )
    parser.add_argument(
        "--max-paths",
        type=int,
        default=5000,
        help="Maximum paths per hand (default: 5000)",
    )

    # Output
    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output JSON file (default: results/traces_<timestamp>.json)",
    )

    # Seed for reproducibility
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducible sampling",
    )

    args = parser.parse_args()

    # Setup paths
    project_root = Path(__file__).parents[1]
    db_path = project_root / "cards.cdb"
    library_path = project_root / "config" / "locked_library.json"
    results_dir = project_root / "results"

    # Ensure output directory exists
    results_dir.mkdir(exist_ok=True)

    # Default output path
    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.output = results_dir / f"traces_{timestamp}.json"

    # Collect results
    all_results = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "max_depth": args.max_depth,
            "max_paths": args.max_paths,
        },
        "hands": [],
    }

    if args.hand:
        # Single fixed hand
        try:
            hand_codes, hand_names = resolve_hand_spec(args.hand, db_path)
        except ValueError as e:
            logger.error(f"Error resolving hand:\n{e}")
            return 1

        if len(hand_codes) != 5:
            logger.error(f"Hand must have exactly 5 cards, got {len(hand_codes)}")
            return 1

        result = export_traces_for_hand(
            hand_codes, hand_names, args.max_depth, args.max_paths
        )
        all_results["hands"].append(result)
        all_results["metadata"]["mode"] = "fixed_hand"

    else:
        # Random sampling
        if args.seed is not None:
            random.seed(args.seed)
            all_results["metadata"]["seed"] = args.seed

        deck_pool = load_deck_pool(library_path)
        logger.info(f"Loaded deck pool: {len(deck_pool)} cards")

        all_results["metadata"]["mode"] = "random_sampling"
        all_results["metadata"]["num_hands"] = args.random

        seen_hands = set()
        for i in range(args.random):
            # Sample unique hands
            for _ in range(100):  # Max attempts
                hand = random.sample(deck_pool, 5)
                signature = frozenset(code for code, _ in hand)
                if signature not in seen_hands:
                    seen_hands.add(signature)
                    break
            else:
                logger.warning("Could not find unique hand after 100 attempts")
                continue

            hand_codes = [code for code, _ in hand]
            hand_names = [name for _, name in hand]

            logger.info(f"\n{'='*60}")
            logger.info(f"Hand {i+1}/{args.random}")
            logger.info(f"{'='*60}")

            result = export_traces_for_hand(
                hand_codes, hand_names, args.max_depth, args.max_paths
            )
            all_results["hands"].append(result)

    # Compute summary statistics
    total_traces = sum(len(h["action_traces"]) for h in all_results["hands"])
    high_score_traces = sum(
        1 for h in all_results["hands"]
        for t in h["action_traces"]
        if t.get("score", 0) >= 50
    )

    all_results["summary"] = {
        "total_hands": len(all_results["hands"]),
        "total_traces": total_traces,
        "high_score_traces": high_score_traces,
        "avg_traces_per_hand": total_traces / len(all_results["hands"]) if all_results["hands"] else 0,
    }

    # Save results
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(all_results, f, indent=2)

    logger.info(f"\n{'='*60}")
    logger.info("TRACE EXPORT COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Hands processed: {len(all_results['hands'])}")
    logger.info(f"Total traces: {total_traces}")
    logger.info(f"High-score traces (>=50): {high_score_traces}")
    logger.info(f"Output saved to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
