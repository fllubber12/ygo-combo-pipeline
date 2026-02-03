#!/usr/bin/env python3
"""
Random Hand Enumeration Script

Samples random 5-card hands from the deck and runs enumeration on each.
Designed to run overnight via nohup.

Usage:
    python scripts/random_hand_enumeration.py --max-hands 20 --max-depth 30 --max-paths 5000
"""

import argparse
import json
import logging
import os
import random
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger(__name__)

# Graceful shutdown flag
shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    logger.info("Shutdown signal received, will stop after current hand...")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def load_deck(library_path: Path) -> list[tuple[int, str]]:
    """Load deck from locked_library.json and expand to full card pool."""
    with open(library_path) as f:
        library = json.load(f)

    deck_pool = []
    for passcode, card_data in library["cards"].items():
        if card_data.get("is_extra_deck", False):
            continue  # Skip extra deck cards
        count = card_data.get("count", 1)
        name = card_data.get("name", f"Unknown ({passcode})")
        for _ in range(count):
            deck_pool.append((int(passcode), name))

    return deck_pool


def sample_hand(deck_pool: list[tuple[int, str]], hand_size: int = 5) -> list[tuple[int, str]]:
    """Sample a random hand from the deck pool."""
    return random.sample(deck_pool, hand_size)


def format_hand_for_cli(hand: list[tuple[int, str]]) -> str:
    """Format hand as comma-separated passcodes for --hand argument."""
    return ",".join(str(passcode) for passcode, _ in hand)


def hand_signature(hand: list[tuple[int, str]]) -> frozenset:
    """Create a signature for a hand (order-independent)."""
    return frozenset(passcode for passcode, _ in hand)


def run_enumeration(
    hand: list[tuple[int, str]],
    max_depth: int,
    max_paths: int,
    workers: int,
    output_dir: Path,
    scripts_dir: Path,
) -> dict:
    """Run enumeration for a single hand and return results."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"random_hand_{timestamp}.json"

    hand_str = format_hand_for_cli(hand)
    hand_names = [name for _, name in hand]

    logger.info(f"Starting enumeration for hand:")
    for i, (passcode, name) in enumerate(hand, 1):
        logger.info(f"  {i}. {name} ({passcode})")

    cmd = [
        sys.executable,
        str(scripts_dir / "run_pipeline.py"),
        "--hand", hand_str,
        "--max-depth", str(max_depth),
        "--max-paths", str(max_paths),
        "--workers", str(workers),
        "--output", str(output_file),
        "--verbose",
    ]

    start_time = datetime.now()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout per hand
        )
        duration = (datetime.now() - start_time).total_seconds()

        if result.returncode != 0:
            logger.error(f"Enumeration failed with code {result.returncode}")
            logger.error(f"stderr: {result.stderr[-500:]}")
            return {
                "hand": hand_names,
                "passcodes": [p for p, _ in hand],
                "status": "failed",
                "error": result.stderr[-500:],
                "duration": duration,
            }

        # Parse results from output file if it exists
        summary = {
            "hand": hand_names,
            "passcodes": [p for p, _ in hand],
            "status": "success",
            "duration": duration,
            "output_file": str(output_file),
        }

        if output_file.exists():
            try:
                with open(output_file) as f:
                    data = json.load(f)
                enumeration = data.get("enumeration", {})
                summary["paths_explored"] = enumeration.get("total_paths", 0)
                summary["terminals_found"] = enumeration.get("unique_terminals", 0)
                summary["max_depth_reached"] = enumeration.get("max_depth_reached", 0)
                summary["best_score"] = enumeration.get("best_score", 0)
            except Exception as e:
                logger.warning(f"Could not parse output file: {e}")

        return summary

    except subprocess.TimeoutExpired:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error("Enumeration timed out after 1 hour")
        return {
            "hand": hand_names,
            "passcodes": [p for p, _ in hand],
            "status": "timeout",
            "duration": duration,
        }
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        logger.error(f"Enumeration error: {e}")
        return {
            "hand": hand_names,
            "passcodes": [p for p, _ in hand],
            "status": "error",
            "error": str(e),
            "duration": duration,
        }


def main():
    parser = argparse.ArgumentParser(description="Random hand enumeration")
    parser.add_argument("--max-hands", type=int, default=20, help="Max hands to enumerate")
    parser.add_argument("--max-depth", type=int, default=30, help="Max depth per hand")
    parser.add_argument("--max-paths", type=int, default=5000, help="Max paths per hand")
    parser.add_argument("--workers", type=int, default=8, help="Worker processes")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    args = parser.parse_args()

    if args.seed:
        random.seed(args.seed)

    # Paths
    project_root = Path(__file__).parent.parent
    library_path = project_root / "config" / "locked_library.json"
    output_dir = project_root / "results"
    scripts_dir = project_root / "scripts"

    output_dir.mkdir(exist_ok=True)

    # Load deck
    logger.info("Loading deck from locked_library.json...")
    deck_pool = load_deck(library_path)
    logger.info(f"Deck pool: {len(deck_pool)} cards (main deck with duplicates)")

    # Track enumerated hands to avoid duplicates
    enumerated_hands = set()
    results = []

    logger.info("=" * 60)
    logger.info("RANDOM HAND ENUMERATION")
    logger.info("=" * 60)
    logger.info(f"Max hands: {args.max_hands}")
    logger.info(f"Max depth: {args.max_depth}")
    logger.info(f"Max paths: {args.max_paths}")
    logger.info(f"Workers: {args.workers}")
    logger.info("=" * 60)

    hands_completed = 0
    while hands_completed < args.max_hands and not shutdown_requested:
        # Sample a unique hand
        attempts = 0
        while attempts < 100:
            hand = sample_hand(deck_pool)
            sig = hand_signature(hand)
            if sig not in enumerated_hands:
                enumerated_hands.add(sig)
                break
            attempts += 1
        else:
            logger.warning("Could not find unique hand after 100 attempts, stopping")
            break

        logger.info(f"\n{'='*60}")
        logger.info(f"HAND {hands_completed + 1}/{args.max_hands}")
        logger.info(f"{'='*60}")

        result = run_enumeration(
            hand=hand,
            max_depth=args.max_depth,
            max_paths=args.max_paths,
            workers=args.workers,
            output_dir=output_dir,
            scripts_dir=scripts_dir,
        )
        results.append(result)
        hands_completed += 1

        # Log summary
        if result["status"] == "success":
            logger.info(f"Completed in {result['duration']:.1f}s")
            logger.info(f"  Paths: {result.get('paths_explored', '?')}")
            logger.info(f"  Terminals: {result.get('terminals_found', '?')}")
            logger.info(f"  Best score: {result.get('best_score', '?')}")
        else:
            logger.error(f"Hand failed: {result['status']}")

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Hands completed: {hands_completed}")

    successful = [r for r in results if r["status"] == "success"]
    if successful:
        total_terminals = sum(r.get("terminals_found", 0) for r in successful)
        total_paths = sum(r.get("paths_explored", 0) for r in successful)
        best_score = max(r.get("best_score", 0) for r in successful)
        logger.info(f"Total terminals: {total_terminals}")
        logger.info(f"Total paths: {total_paths}")
        logger.info(f"Best score across all hands: {best_score}")

    # Save summary
    summary_file = output_dir / f"random_enum_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(summary_file, "w") as f:
        json.dump({
            "config": vars(args),
            "hands_completed": hands_completed,
            "results": results,
        }, f, indent=2)
    logger.info(f"Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
