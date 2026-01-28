#!/usr/bin/env python3
"""
Diagnostic 4: Gold Standard Combo Step-by-Step Validation

Compares enumeration output against gold_standard_combo.json checkpoints.

For each step in the gold standard, checks if that action appears
in any terminal's action sequence.

This identifies EXACTLY where the combo diverges.

Run from repo root:
    python3 scripts/diagnostics/04_gold_standard_step_check.py
"""

import sys
import os
import json
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo_combo.combo_enumeration import (
    EnumerationEngine, load_locked_library, get_deck_lists,
    load_library, init_card_database, set_lib
)


def load_gold_standard():
    """Load gold standard combo definition."""
    config_path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'config', 'gold_standard_combo.json'
    )
    with open(config_path) as f:
        return json.load(f)


def extract_checkpoints(gold_standard):
    """Extract key checkpoints from gold standard combo."""
    checkpoints = []
    for step in gold_standard['combo_steps']:
        checkpoints.append({
            'step': step['step'],
            'card_id': step.get('card_id'),
            'action': step['action'],
            'result': step.get('result', ''),
            # For Link/Xyz/Fusion summons, track the target
            'summon_target': step.get('fusion_target') or step.get('card_id'),
        })
    return checkpoints


def check_action_in_sequence(checkpoint, action_sequence):
    """Check if a checkpoint action appears in an action sequence."""
    card_id = checkpoint['card_id']
    
    for action in action_sequence:
        # Match by card code
        if action.card_code == card_id:
            return True
        
        # For summons, also check if the summoned monster appears
        if checkpoint.get('summon_target'):
            if action.card_code == checkpoint['summon_target']:
                return True
    
    return False


def find_deepest_checkpoint_reached(checkpoints, action_sequence):
    """Find how far into the gold standard combo a sequence got."""
    deepest = 0
    for cp in checkpoints:
        if check_action_in_sequence(cp, action_sequence):
            deepest = max(deepest, cp['step'])
    return deepest


def main():
    print("=" * 70)
    print("DIAGNOSTIC 4: Gold Standard Step-by-Step Validation")
    print("=" * 70)
    
    # Load gold standard
    try:
        gold_standard = load_gold_standard()
        print(f"Loaded gold standard: {gold_standard['metadata']['name']}")
    except FileNotFoundError:
        print("ERROR: config/gold_standard_combo.json not found")
        return 1
    
    checkpoints = extract_checkpoints(gold_standard)
    print(f"Combo has {len(checkpoints)} steps")
    
    # Initialize engine
    print("\nInitializing engine...")
    if not init_card_database():
        print("ERROR: Failed to load card database")
        return 1
    
    lib = load_library()
    set_lib(lib)
    
    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)
    
    # Key cards to prioritize (from gold standard)
    TRACT = 98567237
    LURRIE = 97651498
    REQUIEM = 2463794
    
    engine = EnumerationEngine(
        lib, main_deck, extra_deck,
        verbose=False,
        dedupe_boards=True,
        dedupe_intermediate=True,
        prioritize_cards=[TRACT, LURRIE, REQUIEM]
    )
    
    # Search parameters
    import ygo_combo.combo_enumeration as ce
    ce.MAX_DEPTH = 35
    ce.MAX_PATHS = 2000
    
    print(f"Running enumeration (max_depth=35, max_paths=2000)...")
    terminals = engine.enumerate_all()
    
    print(f"\nFound {len(terminals)} terminals")
    
    # Analyze each terminal's progress through gold standard
    print("\n" + "=" * 70)
    print("CHECKPOINT ANALYSIS:")
    print("=" * 70)
    
    checkpoint_hits = defaultdict(int)  # step -> count of terminals reaching it
    deepest_per_terminal = []
    
    for t in terminals:
        deepest = find_deepest_checkpoint_reached(checkpoints, t.action_sequence)
        deepest_per_terminal.append((deepest, t))
        
        # Count all checkpoints hit (not just deepest)
        for cp in checkpoints:
            if check_action_in_sequence(cp, t.action_sequence):
                checkpoint_hits[cp['step']] += 1
    
    # Print checkpoint coverage
    print("\nCheckpoint hit frequency (how many terminals reached each step):")
    print("-" * 70)
    
    for cp in checkpoints:
        step = cp['step']
        hits = checkpoint_hits.get(step, 0)
        pct = (hits / len(terminals) * 100) if terminals else 0
        
        bar_len = int(pct / 2)
        bar = "█" * bar_len
        
        if hits == 0:
            status = "✗ NEVER REACHED"
        elif hits == len(terminals):
            status = "✓ All terminals"
        else:
            status = f"{hits} terminals ({pct:.0f}%)"
        
        print(f"  Step {step:2}: {bar:50} {status}")
        print(f"          {cp['action'][:60]}")
    
    # Find first step that's never reached
    print("\n" + "=" * 70)
    print("DIVERGENCE POINT:")
    print("=" * 70)
    
    first_missed = None
    for cp in checkpoints:
        if checkpoint_hits.get(cp['step'], 0) == 0:
            first_missed = cp
            break
    
    if first_missed:
        print(f"\n✗ Combo FIRST diverges at Step {first_missed['step']}:")
        print(f"  Action: {first_missed['action']}")
        print(f"  Expected result: {first_missed['result']}")
        print(f"  Card ID: {first_missed['card_id']}")
        
        # Show what the best terminal DID do at that depth
        best = max(deepest_per_terminal, key=lambda x: x[0])
        print(f"\n  Best terminal reached step {best[0]} (depth {best[1].depth})")
    else:
        print("\n✓ All gold standard steps were reached by at least one terminal!")
        
        # Check if full combo was achieved
        full_combo_terminals = [
            t for d, t in deepest_per_terminal if d >= len(checkpoints)
        ]
        if full_combo_terminals:
            print(f"  {len(full_combo_terminals)} terminal(s) completed the full combo!")
    
    # Show the terminal that got furthest
    print("\n" + "=" * 70)
    print("BEST TERMINAL (furthest through gold standard):")
    print("=" * 70)
    
    if deepest_per_terminal:
        best_depth, best_terminal = max(deepest_per_terminal, key=lambda x: x[0])
        print(f"Reached checkpoint: {best_depth}/{len(checkpoints)}")
        print(f"Total actions: {best_terminal.depth}")
        print(f"\nAction sequence:")
        for i, action in enumerate(best_terminal.action_sequence[:25]):  # First 25
            print(f"  {i+1:2}. {action.description[:65]}")
        if len(best_terminal.action_sequence) > 25:
            print(f"  ... ({len(best_terminal.action_sequence) - 25} more)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
