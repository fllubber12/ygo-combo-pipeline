#!/usr/bin/env python3
"""
Exhaustive path enumeration from a starting state.

Unlike beam search (which prunes), this explores EVERY legal action sequence
up to a maximum depth, building a complete decision tree.
"""

import json
import sys
from pathlib import Path
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sim.state import GameState
from sim.actions import generate_actions, apply_action, Action
from sim.effects.registry import enumerate_effect_actions, apply_effect_action
from sim.effects.types import EffectAction
from sim.errors import IllegalActionError
from combos.endboard_evaluator import evaluate_endboard
from sim.convert import game_state_to_endboard_snapshot


def enumerate_all_paths(
    state: GameState,
    max_depth: int = 10,
    current_path: list = None,
    all_paths: list = None,
    seen_states: set = None,
    verbose: bool = False,
) -> list:
    """
    Recursively enumerate ALL legal action sequences.

    Returns list of paths, where each path is:
    {
        "actions": [action1, action2, ...],
        "final_state": GameState,
        "evaluation": {"rank_key": ..., "summary": ...},
        "depth": int
    }
    """
    if current_path is None:
        current_path = []
    if all_paths is None:
        all_paths = []
    if seen_states is None:
        seen_states = set()

    # Base case: max depth reached
    if len(current_path) >= max_depth:
        snapshot = game_state_to_endboard_snapshot(state)
        evaluation = evaluate_endboard(snapshot)
        all_paths.append({
            "actions": list(current_path),
            "evaluation": evaluation,
            "depth": len(current_path),
            "stopped_reason": "max_depth"
        })
        return all_paths

    # Get all legal actions
    effect_actions = list(enumerate_effect_actions(state))
    core_actions = generate_actions(state, ["normal_summon", "extra_deck_summon"])
    all_actions = effect_actions + core_actions

    # If no actions available, this is a terminal state
    if not all_actions:
        snapshot = game_state_to_endboard_snapshot(state)
        evaluation = evaluate_endboard(snapshot)
        all_paths.append({
            "actions": list(current_path),
            "evaluation": evaluation,
            "depth": len(current_path),
            "stopped_reason": "no_actions"
        })
        return all_paths

    # Try each action
    found_valid_action = False
    for action in all_actions:
        try:
            # Apply action
            if isinstance(action, Action):
                new_state = apply_action(state, action)
                action_desc = f"{action.action_type}: {action.params}"
            else:
                new_state = apply_effect_action(state, action)
                action_desc = f"{action.name} [{action.cid}] {action.effect_id}"

            # Create state hash to avoid revisiting
            state_hash = hash_state(new_state)
            if state_hash in seen_states:
                continue
            seen_states.add(state_hash)

            found_valid_action = True

            if verbose and len(current_path) < 2:
                print(f"  {'  ' * len(current_path)}Exploring: {action_desc[:60]}...")

            # Recurse
            current_path.append(action_desc)
            enumerate_all_paths(new_state, max_depth, current_path, all_paths, seen_states, verbose)
            current_path.pop()

        except IllegalActionError:
            continue

    # If no valid actions found (all failed or all seen), record terminal state
    if not found_valid_action:
        snapshot = game_state_to_endboard_snapshot(state)
        evaluation = evaluate_endboard(snapshot)
        all_paths.append({
            "actions": list(current_path),
            "evaluation": evaluation,
            "depth": len(current_path),
            "stopped_reason": "all_actions_failed_or_seen"
        })

    return all_paths


def hash_state(state: GameState) -> str:
    """Create a hashable representation of game state."""
    # Simplified hash - just key zones
    hand = tuple(sorted(c.cid for c in state.hand))
    gy = tuple(sorted(c.cid for c in state.gy))
    field = tuple(c.cid if c else None for c in state.field.mz + state.field.emz)
    extra = tuple(sorted(c.cid for c in state.extra))
    opt = tuple(sorted(state.opt_used.items()))
    return str((hand, gy, field, extra, opt))


def print_path_tree(all_paths: list):
    """Print summary of all paths found."""
    print(f"\n{'='*70}")
    print(f"TOTAL PATHS FOUND: {len(all_paths)}")
    print(f"{'='*70}")

    # Group by evaluation
    by_tier = {"S": [], "A": [], "B": [], "none": []}
    for path in all_paths:
        rank = path["evaluation"]["rank_key"]
        if rank[0] > 0:  # S-tier
            by_tier["S"].append(path)
        elif rank[1] > 0:  # A-tier
            by_tier["A"].append(path)
        elif rank[2] > 0:  # B-tier
            by_tier["B"].append(path)
        else:
            by_tier["none"].append(path)

    print(f"\nPaths by tier:")
    print(f"  S-tier: {len(by_tier['S'])}")
    print(f"  A-tier: {len(by_tier['A'])}")
    print(f"  B-tier: {len(by_tier['B'])}")
    print(f"  No tier: {len(by_tier['none'])}")

    # Path depth distribution
    depths = [p["depth"] for p in all_paths]
    print(f"\nPath depths: min={min(depths)}, max={max(depths)}, avg={sum(depths)/len(depths):.1f}")

    # Print best paths for each tier
    for tier in ["S", "A", "B"]:
        if by_tier[tier]:
            print(f"\n{'='*70}")
            print(f"SHORTEST {tier}-TIER PATH ({len(by_tier[tier])} total):")
            print(f"{'='*70}")
            best = min(by_tier[tier], key=lambda p: p["depth"])
            for i, action in enumerate(best["actions"], 1):
                print(f"  {i}. {action}")
            print(f"\n  Evaluation: {best['evaluation']['summary']}")
            print(f"  Depth: {best['depth']}")
            print(f"  Stopped: {best['stopped_reason']}")

    # Print sample of no-tier paths
    if by_tier["none"]:
        print(f"\n{'='*70}")
        print(f"SAMPLE NO-TIER PATH ({len(by_tier['none'])} total):")
        print(f"{'='*70}")
        sample = by_tier["none"][0]
        for i, action in enumerate(sample["actions"], 1):
            print(f"  {i}. {action}")
        print(f"\n  Stopped: {sample['stopped_reason']}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Exhaustive path enumeration")
    parser.add_argument("--fixture", default="tests/fixtures/combo_scenarios/fixture_engraver_only_minimal.json")
    parser.add_argument("--depth", type=int, default=8, help="Maximum search depth")
    parser.add_argument("--verbose", action="store_true", help="Show exploration progress")
    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    if not fixture_path.exists():
        print(f"Fixture not found: {fixture_path}")
        return 1

    fixture = json.loads(fixture_path.read_text())
    state = GameState.from_snapshot(fixture["state"])

    print("=" * 70)
    print("EXHAUSTIVE PATH ENUMERATION")
    print("=" * 70)
    print(f"\nFixture: {fixture['name']}")
    print(f"Max depth: {args.depth}")
    print(f"\nStarting state:")
    print(f"  Hand: {[c.name for c in state.hand]}")
    print(f"  Deck: {[c.name for c in state.deck]}")
    print(f"  Extra: {[c.name for c in state.extra]}")

    print("\nEnumerating all paths...")
    all_paths = enumerate_all_paths(state, max_depth=args.depth, verbose=args.verbose)
    print_path_tree(all_paths)

    return 0


if __name__ == "__main__":
    sys.exit(main())
