#!/usr/bin/env python3
"""
Command-line interface for combo enumeration.

Usage:
    python -m ygo_combo.cli --max-depth 25 --max-paths 1000
    python -m ygo_combo.cli --verbose --output results.json
"""

import json
import signal
import argparse
import logging
from datetime import datetime
from pathlib import Path

from .combo_enumeration import (
    EnumerationEngine,
    MAX_DEPTH,
    MAX_PATHS,
    _signal_handler,
)
from .engine.interface import init_card_database, load_library, set_lib
from .engine.duel_factory import load_locked_library, get_deck_lists

logger = logging.getLogger(__name__)


def main():
    """Main entry point for combo enumeration CLI."""
    import ygo_combo.combo_enumeration as ce

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    parser = argparse.ArgumentParser(description="Exhaustive combo enumeration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH, help="Max actions per path")
    parser.add_argument("--max-paths", type=int, default=MAX_PATHS, help="Max paths to explore")
    parser.add_argument("--output", "-o", type=str, default="enumeration_results.json",
                        help="Output file")
    parser.add_argument("--no-dedupe", action="store_true",
                        help="Disable terminal board state deduplication")
    parser.add_argument("--no-dedupe-intermediate", action="store_true",
                        help="Disable intermediate state pruning")
    parser.add_argument("--prioritize-cards", type=str, default="",
                        help="Comma-separated list of card passcodes to explore first during SELECT_CARD")
    args = parser.parse_args()

    # Parse prioritized cards
    prioritize_cards = []
    if args.prioritize_cards:
        prioritize_cards = [int(x.strip()) for x in args.prioritize_cards.split(",") if x.strip()]
        if prioritize_cards:
            print(f"Card prioritization enabled: {prioritize_cards}")

    # Update limits
    ce.MAX_DEPTH = args.max_depth
    ce.MAX_PATHS = args.max_paths

    # Initialize
    logger.info("Loading card database...")
    if not init_card_database():
        logger.error("Failed to load card database")
        return 1

    print("Loading library...")
    lib = load_library()

    # Set the library reference for callbacks in engine_interface
    set_lib(lib)

    print("Loading locked library...")
    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)

    print(f"Main deck: {len(main_deck)} cards")
    print(f"Extra deck: {len(extra_deck)} cards")

    # Run enumeration
    dedupe_terminals = not args.no_dedupe
    dedupe_intermediate = not args.no_dedupe_intermediate
    engine = EnumerationEngine(
        lib, main_deck, extra_deck,
        verbose=args.verbose,
        dedupe_boards=dedupe_terminals,
        dedupe_intermediate=dedupe_intermediate,
        prioritize_cards=prioritize_cards if prioritize_cards else None
    )
    terminals = engine.enumerate_all()

    # Save results
    output_path = Path(args.output)
    tt_stats = engine.transposition_table.stats()
    results = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "max_depth": ce.MAX_DEPTH,
            "max_paths": ce.MAX_PATHS,
            "paths_explored": engine.paths_explored,
            "terminals_found": len(terminals),
            "unique_board_signatures": len(engine.terminal_boards),
            "duplicate_boards_skipped": engine.duplicate_boards_skipped,
            "intermediate_states_pruned": engine.intermediate_states_pruned,
            "transposition_table_size": tt_stats["size"],
            "transposition_hit_rate": tt_stats["hit_rate"],
            "dedupe_terminals_enabled": dedupe_terminals,
            "dedupe_intermediate_enabled": dedupe_intermediate,
            "prioritize_cards": prioritize_cards if prioritize_cards else [],
            "max_depth_seen": engine.max_depth_seen,
        },
        "terminals": [t.to_dict() for t in terminals],
        "board_groups": {k: len(v) for k, v in engine.terminal_boards.items()},
    }

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    by_reason = {}
    by_depth = {}
    for t in terminals:
        by_reason[t.termination_reason] = by_reason.get(t.termination_reason, 0) + 1
        by_depth[t.depth] = by_depth.get(t.depth, 0) + 1

    print("\nBy termination reason:")
    for reason, count in sorted(by_reason.items()):
        print(f"  {reason}: {count}")

    print("\nBy depth:")
    for depth in sorted(by_depth.keys()):
        print(f"  Depth {depth}: {by_depth[depth]}")

    return 0


if __name__ == "__main__":
    exit(main())
