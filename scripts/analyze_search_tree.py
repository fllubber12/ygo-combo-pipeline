#!/usr/bin/env python3
"""
Analyze search tree shape and test shuffle mode.

Measures:
1. Branching factor at each depth
2. First-branch depth before backtracking
3. Action distribution at MSG_IDLE
4. Effect of shuffle on terminal discovery
"""

import os
import sys
from pathlib import Path
import random
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "ygo_combo"))

if not os.environ.get("YGOPRO_SCRIPTS_PATH"):
    os.environ["YGOPRO_SCRIPTS_PATH"] = "/Users/zacharyhartley/ygopro-scripts"


@dataclass
class TreeStats:
    """Statistics about search tree shape."""
    branching_factors: List[int]  # Actions available at each IDLE
    depths_visited: List[int]     # Depth when each terminal reached
    first_branch_depth: int       # How deep before first backtrack
    action_counts: Dict[str, int] # Action type distribution


def analyze_enumeration_results(results_file: str) -> TreeStats:
    """Analyze search tree from enumeration results."""
    with open(results_file) as f:
        data = json.load(f)

    branching = []
    depths = []
    action_counts = defaultdict(int)

    for terminal in data.get("terminals", []):
        depths.append(terminal.get("depth", 0))
        for action in terminal.get("action_sequence", []):
            action_counts[action.get("action_type", "UNKNOWN")] += 1

    return TreeStats(
        branching_factors=branching,
        depths_visited=depths,
        first_branch_depth=0,
        action_counts=dict(action_counts)
    )


def run_with_shuffle(seed: int, max_paths: int = 5000, max_depth: int = 30):
    """Run enumeration with shuffled action order."""
    from combo_enumeration import (
        EnumerationEngine, load_locked_library, get_deck_lists,
        init_card_database, MAX_DEPTH, MAX_PATHS
    )
    from engine_interface import load_library, set_lib

    print(f"\n{'='*60}")
    print(f"SHUFFLE RUN - Seed {seed}")
    print(f"{'='*60}")

    random.seed(seed)

    # Initialize
    init_card_database()
    lib = load_library()
    set_lib(lib)
    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)

    # Create engine with shuffle hook
    engine = EnumerationEngine(
        lib, main_deck, extra_deck,
        verbose=False,
        dedupe_boards=True,
        dedupe_intermediate=True
    )

    # Monkey-patch _handle_idle to shuffle actions
    original_handle_idle = engine._handle_idle

    def shuffled_handle_idle(duel, action_history, idle_data):
        # Shuffle activatable list
        if "activatable" in idle_data:
            random.shuffle(idle_data["activatable"])
        if "spsummon" in idle_data:
            random.shuffle(idle_data["spsummon"])
        if "summonable" in idle_data:
            random.shuffle(idle_data["summonable"])
        return original_handle_idle(duel, action_history, idle_data)

    engine._handle_idle = shuffled_handle_idle

    # Also patch _handle_select_card
    original_handle_select = engine._handle_select_card

    def shuffled_handle_select(duel, action_history, select_data):
        if "cards" in select_data:
            random.shuffle(select_data["cards"])
        return original_handle_select(duel, action_history, select_data)

    engine._handle_select_card = shuffled_handle_select

    # Run enumeration
    import combo_enumeration
    combo_enumeration.MAX_DEPTH = max_depth
    combo_enumeration.MAX_PATHS = max_paths

    terminals = engine.enumerate_all()

    # Collect unique board hashes
    board_hashes = set()
    for t in terminals:
        if t.board_hash:
            board_hashes.add(t.board_hash)

    print(f"Seed {seed}: {len(terminals)} terminals, {len(board_hashes)} unique boards")

    # Check for Tract usage
    tract_count = 0
    for t in terminals:
        for a in t.action_sequence:
            if a.card_code == 98567237:  # Tract
                tract_count += 1
                break
    print(f"  Terminals using Tract: {tract_count}")

    return board_hashes, terminals


def measure_branching_factor(max_paths: int = 1000):
    """Measure branching factor at each depth."""
    from combo_enumeration import (
        EnumerationEngine, load_locked_library, get_deck_lists,
        init_card_database
    )
    from engine_interface import load_library, set_lib
    import combo_enumeration

    print(f"\n{'='*60}")
    print("BRANCHING FACTOR ANALYSIS")
    print(f"{'='*60}")

    # Initialize
    init_card_database()
    lib = load_library()
    set_lib(lib)
    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)

    # Track branching at each depth
    branching_by_depth = defaultdict(list)
    first_backtrack_depth = None
    max_depth_first_branch = 0

    engine = EnumerationEngine(
        lib, main_deck, extra_deck,
        verbose=False,
        dedupe_boards=True,
        dedupe_intermediate=True
    )

    # Monkey-patch to track branching
    original_handle_idle = engine._handle_idle

    def tracking_handle_idle(duel, action_history, idle_data):
        nonlocal max_depth_first_branch
        depth = len(action_history)

        # Count available actions
        n_activate = len(idle_data.get("activatable", []))
        n_spsummon = len(idle_data.get("spsummon", []))
        n_summon = len(idle_data.get("summonable", []))
        n_pass = 1 if idle_data.get("to_ep") else 0
        total = n_activate + n_spsummon + n_summon + n_pass

        branching_by_depth[depth].append(total)

        # Track first branch depth
        if depth > max_depth_first_branch and len(branching_by_depth[depth]) == 1:
            max_depth_first_branch = depth

        return original_handle_idle(duel, action_history, idle_data)

    engine._handle_idle = tracking_handle_idle

    # Run limited enumeration
    combo_enumeration.MAX_DEPTH = 30
    combo_enumeration.MAX_PATHS = max_paths

    terminals = engine.enumerate_all()

    print(f"\nBranching factor by depth:")
    for depth in sorted(branching_by_depth.keys())[:20]:
        factors = branching_by_depth[depth]
        avg = sum(factors) / len(factors) if factors else 0
        print(f"  Depth {depth:2d}: avg={avg:.1f}, samples={len(factors)}, range={min(factors)}-{max(factors)}")

    print(f"\nFirst branch explored to depth: {max_depth_first_branch}")
    print(f"Total IDLE encounters: {sum(len(v) for v in branching_by_depth.values())}")

    return branching_by_depth


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analyze search tree")
    parser.add_argument("--branching", action="store_true", help="Measure branching factor")
    parser.add_argument("--shuffle", action="store_true", help="Test shuffle mode")
    parser.add_argument("--seeds", type=int, default=3, help="Number of shuffle seeds")
    parser.add_argument("--paths", type=int, default=5000, help="Max paths per run")
    args = parser.parse_args()

    if args.branching:
        measure_branching_factor(args.paths)

    if args.shuffle:
        all_boards = set()
        all_terminals = []

        for seed in range(args.seeds):
            boards, terminals = run_with_shuffle(seed, args.paths)
            all_boards.update(boards)
            all_terminals.extend(terminals)

        print(f"\n{'='*60}")
        print(f"SHUFFLE SUMMARY ({args.seeds} runs)")
        print(f"{'='*60}")
        print(f"Total unique boards discovered: {len(all_boards)}")

        # Check for gold standard cards
        abaoaqu = 4731783
        caesar = 79559912
        for t in all_terminals:
            monsters = [c.get("code") for c in t.board_state.get("player0", {}).get("monsters", [])]
            if abaoaqu in monsters and caesar in monsters:
                print(f"\n*** GOLD STANDARD FOUND! Depth {t.depth} ***")
                break

    if not args.branching and not args.shuffle:
        # Default: run both
        measure_branching_factor(2000)

        all_boards = set()
        for seed in range(3):
            boards, _ = run_with_shuffle(seed, 3000)
            all_boards.update(boards)
        print(f"\nTotal unique boards from 3 shuffle runs: {len(all_boards)}")


if __name__ == "__main__":
    main()
