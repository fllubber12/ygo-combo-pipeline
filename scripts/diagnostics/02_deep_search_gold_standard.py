#!/usr/bin/env python3
"""
Diagnostic 2: Deep search for gold standard endboard.

Searches up to depth 40 looking for terminals with:
- A Bao A Qu (4731783)
- D/D/D Wave High King Caesar (79559912)

Outputs:
- Best board found (by boss monster presence)
- Deepest path explored
- Where combo lines diverge

Run from repo root:
    python3 scripts/diagnostics/02_deep_search_gold_standard.py
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo_combo.combo_enumeration import (
    EnumerationEngine, load_locked_library, get_deck_lists,
    load_library, init_card_database, set_lib
)

# Target cards
A_BAO_A_QU = 4731783
CAESAR = 79559912
REXTREMENDE = 11464648
AGNUMDAY = 32991300
SEQUENCE = 49867899
LACRIMA_FUSION = 46640168
REQUIEM = 2463794
SP_LITTLE_KNIGHT = 29301450

# Prioritize Tract line
TRACT = 98567237
LURRIE = 97651498

BOSS_PRIORITY = [
    (A_BAO_A_QU, "A Bao A Qu (Link-4)"),
    (CAESAR, "Caesar (Rank-6 Xyz)"),
    (REXTREMENDE, "Rextremende (Fusion boss)"),
    (AGNUMDAY, "Agnumday (Link-3)"),
    (SEQUENCE, "Sequence (Link-2)"),
    (SP_LITTLE_KNIGHT, "S:P Little Knight (Link-2)"),
    (LACRIMA_FUSION, "Lacrima Fusion"),
    (REQUIEM, "Requiem (Link-1)"),
]


def score_terminal(terminal):
    """Score a terminal by boss monster presence."""
    monsters = terminal.board_state.get("player0", {}).get("monsters", [])
    codes = {m["code"] for m in monsters}
    
    score = 0
    bosses_found = []
    
    for i, (code, name) in enumerate(BOSS_PRIORITY):
        if code in codes:
            score += (len(BOSS_PRIORITY) - i) * 10  # Higher priority = more points
            bosses_found.append(name)
    
    # Bonus for having BOTH targets
    if A_BAO_A_QU in codes and CAESAR in codes:
        score += 1000
    
    return score, bosses_found


def main():
    print("=" * 70)
    print("DIAGNOSTIC 2: Deep Search for Gold Standard Endboard")
    print("=" * 70)
    print(f"Target: A Bao A Qu ({A_BAO_A_QU}) + Caesar ({CAESAR})")
    print()
    
    # Initialize
    print("Initializing engine...")
    if not init_card_database():
        print("ERROR: Failed to load card database")
        return 1
    
    lib = load_library()
    set_lib(lib)
    
    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)
    
    # Create engine with gold standard prioritization
    engine = EnumerationEngine(
        lib, main_deck, extra_deck,
        verbose=False,  # Quiet for speed
        dedupe_boards=True,
        dedupe_intermediate=True,
        prioritize_cards=[TRACT, LURRIE, REQUIEM, SEQUENCE, AGNUMDAY]
    )
    
    # Search parameters
    MAX_DEPTH = 40
    MAX_PATHS = 5000
    
    print(f"Search params: max_depth={MAX_DEPTH}, max_paths={MAX_PATHS}")
    print(f"Prioritizing: Tract → Lurrie → Requiem → Sequence → Agnumday")
    print()
    print("Running enumeration (this may take a few minutes)...")
    print("-" * 70)
    
    # Patch limits
    import ygo_combo.combo_enumeration as ce
    ce.MAX_DEPTH = MAX_DEPTH
    ce.MAX_PATHS = MAX_PATHS
    
    start_time = datetime.now()
    terminals = engine.enumerate_all()
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print("-" * 70)
    print(f"\nCompleted in {elapsed:.1f}s")
    print(f"Terminals found: {len(terminals)}")
    print(f"Paths explored: {engine.paths_explored}")
    print(f"Max depth seen: {engine.max_depth_seen}")
    
    if not terminals:
        print("\nERROR: No terminals found!")
        return 1
    
    # Score all terminals
    scored = [(score_terminal(t), t) for t in terminals]
    scored.sort(key=lambda x: x[0][0], reverse=True)
    
    # Report best terminals
    print("\n" + "=" * 70)
    print("TOP 5 TERMINALS BY BOSS MONSTERS:")
    print("=" * 70)
    
    gold_standard_found = False
    
    for i, ((score, bosses), terminal) in enumerate(scored[:5]):
        monsters = terminal.board_state.get("player0", {}).get("monsters", [])
        monster_names = [m.get("name", f"code:{m['code']}") for m in monsters]
        
        print(f"\n#{i+1} (score={score}, depth={terminal.depth}):")
        print(f"  Monsters: {monster_names}")
        print(f"  Bosses: {bosses if bosses else 'None'}")
        
        codes = {m["code"] for m in monsters}
        if A_BAO_A_QU in codes and CAESAR in codes:
            gold_standard_found = True
            print("  *** GOLD STANDARD FOUND! ***")
    
    # Check for targets specifically
    print("\n" + "=" * 70)
    print("TARGET CARD ANALYSIS:")
    print("=" * 70)
    
    terminals_with_caesar = []
    terminals_with_abaoaqu = []
    terminals_with_both = []
    
    for t in terminals:
        monsters = t.board_state.get("player0", {}).get("monsters", [])
        codes = {m["code"] for m in monsters}
        
        has_caesar = CAESAR in codes
        has_abaoaqu = A_BAO_A_QU in codes
        
        if has_caesar:
            terminals_with_caesar.append(t)
        if has_abaoaqu:
            terminals_with_abaoaqu.append(t)
        if has_caesar and has_abaoaqu:
            terminals_with_both.append(t)
    
    print(f"  Terminals with Caesar: {len(terminals_with_caesar)}")
    print(f"  Terminals with A Bao A Qu: {len(terminals_with_abaoaqu)}")
    print(f"  Terminals with BOTH: {len(terminals_with_both)}")
    
    if terminals_with_both:
        print("\n  ✓ GOLD STANDARD ACHIEVED!")
        best = terminals_with_both[0]
        print(f"    Shortest path: {best.depth} actions")
    elif terminals_with_caesar:
        print("\n  ⚠ Caesar found but not A Bao A Qu")
        print("    Issue: Combo stops before making Link-4")
    elif terminals_with_abaoaqu:
        print("\n  ⚠ A Bao A Qu found but not Caesar")
        print("    Issue: Xyz summon not happening (SELECT_SUM issue?)")
    else:
        print("\n  ✗ Neither target found")
        print("    Issue: Combo not reaching late game")
    
    # Depth distribution
    print("\n" + "=" * 70)
    print("DEPTH DISTRIBUTION:")
    print("=" * 70)
    
    depth_counts = {}
    for t in terminals:
        d = t.depth
        depth_counts[d] = depth_counts.get(d, 0) + 1
    
    for d in sorted(depth_counts.keys()):
        bar = "█" * min(depth_counts[d], 50)
        print(f"  Depth {d:2}: {depth_counts[d]:4} {bar}")
    
    # Save detailed results
    results = {
        "timestamp": datetime.now().isoformat(),
        "params": {"max_depth": MAX_DEPTH, "max_paths": MAX_PATHS},
        "stats": {
            "terminals": len(terminals),
            "paths_explored": engine.paths_explored,
            "max_depth_seen": engine.max_depth_seen,
            "elapsed_seconds": elapsed,
        },
        "targets": {
            "caesar_found": len(terminals_with_caesar),
            "abaoaqu_found": len(terminals_with_abaoaqu),
            "both_found": len(terminals_with_both),
            "gold_standard_achieved": gold_standard_found,
        },
        "depth_distribution": depth_counts,
    }
    
    output_path = "diagnostic_02_results.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to: {output_path}")
    
    return 0 if gold_standard_found else 1

if __name__ == "__main__":
    sys.exit(main())
