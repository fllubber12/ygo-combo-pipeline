#!/usr/bin/env python3
"""
test_engraver_max_depth.py - Test single Engraver combo at maximum depth

Run from project root:
    python scripts/test_engraver_max_depth.py
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "cffi"))

from combo_enumeration import (
    EnumerationEngine,
    load_locked_library,
    get_deck_lists,
    init_card_database,
    load_library,
    set_lib,
    MAX_DEPTH,
    MAX_PATHS,
)

# Card codes
ENGRAVER = 60764609
HOLACTIE = 10000040  # Dead card placeholder

# Target cards to look for
TARGETS = {
    79559912: "Caesar",
    82135803: "Desirae",
    49867899: "Sequence",
    61395536: "Lacrima",
    11464648: "Rextremende",
    32991300: "Agnumday",
    2463794: "Requiem",
    29301450: "S:P Little Knight",
}

CARD_NAMES = {
    ENGRAVER: "Engraver",
    HOLACTIE: "Holactie (dead)",
    **TARGETS
}


def run_test():
    print("=" * 70)
    print("ENGRAVER COMBO MAX DEPTH TEST")
    print("=" * 70)

    # Load deck
    library_path = Path("config/locked_library.json")
    if not library_path.exists():
        print(f"ERROR: Library not found at {library_path}")
        print("Make sure you're running from the project root directory.")
        return False

    # Initialize card database
    print("Loading card database...")
    if not init_card_database():
        print("ERROR: Failed to load card database")
        return False

    # Load the ygopro-core library
    print("Loading ygopro-core library...")
    lib = load_library()
    set_lib(lib)

    # Load locked library and get deck lists
    print("Loading locked library...")
    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)
    print(f"Loaded: {len(main_deck)} main deck, {len(extra_deck)} extra deck")

    # Test hand: 1 Engraver + 4 dead cards
    hand = [ENGRAVER, HOLACTIE, HOLACTIE, HOLACTIE, HOLACTIE]
    print(f"\nTest hand: {[CARD_NAMES.get(c, c) for c in hand]}")

    # Use default limits from combo_enumeration
    print(f"\nConfig: max_depth={MAX_DEPTH}, max_paths={MAX_PATHS}")
    print("\n" + "=" * 70)
    print("Starting enumeration...")
    print("=" * 70 + "\n")

    start_time = time.time()

    try:
        engine = EnumerationEngine(
            lib, main_deck, extra_deck,
            verbose=False,  # Set True for step-by-step output
            dedupe_boards=True,
            dedupe_intermediate=True,
        )
        terminals = engine.enumerate_from_hand(hand)

        elapsed = time.time() - start_time

        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)
        print(f"Time elapsed: {elapsed:.2f}s")
        print(f"Paths explored: {engine.paths_explored}")
        print(f"Max depth reached: {engine.max_depth_seen}")
        print(f"Terminal boards: {len(terminals)}")

        if not terminals:
            print("\nNo terminal boards found!")
            return False

        # Analyze terminals
        target_counts = {code: 0 for code in TARGETS}
        best_depth = 999
        deepest_depth = 0

        for term in terminals:
            depth = term.depth
            deepest_depth = max(deepest_depth, depth)
            best_depth = min(best_depth, depth)

            # Check for key cards on board
            board = term.board_state
            if board:
                p0 = board.get("player0", {})
                monsters = p0.get("monsters", [])
                for monster in monsters:
                    code = monster.get("code", 0)
                    if code in TARGETS:
                        target_counts[code] += 1

        print(f"\nTerminal depth range: {best_depth} - {deepest_depth}")

        print("\n--- Key Cards Found ---")
        for code, name in TARGETS.items():
            count = target_counts[code]
            status = "found" if count > 0 else "not found"
            print(f"  {status}: {name}: {count} terminals")

        # Show sample terminal boards
        print("\n" + "-" * 70)
        print("SAMPLE TERMINAL BOARDS (first 5)")
        print("-" * 70)

        for i, term in enumerate(terminals[:5]):
            print(f"\nTerminal {i+1}:")
            print(f"  Depth: {term.depth}")

            board = term.board_state
            if board:
                p0 = board.get("player0", {})
                monsters = p0.get("monsters", [])
                if monsters:
                    names = [m.get("name", str(m.get("code"))) for m in monsters]
                    print(f"  Monsters: {names}")

                gy = p0.get("graveyard", [])
                if gy:
                    names = [g.get("name", str(g.get("code"))) for g in gy[:5]]
                    suffix = f"... (+{len(gy)-5} more)" if len(gy) > 5 else ""
                    print(f"  GY: {names}{suffix}")

        print("\n" + "=" * 70)
        print("TEST PASSED")
        print("=" * 70)
        return True

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\nERROR after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()

        # Check for specific error types
        error_str = str(e).lower()
        if "unknown message" in error_str or "unhandled" in error_str:
            print("\n" + "=" * 70)
            print("MISSING MESSAGE HANDLER DETECTED")
            print("=" * 70)
            print("Check the error message above for the message type number.")
            print("This needs to be implemented in combo_enumeration.py")

        return False


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
