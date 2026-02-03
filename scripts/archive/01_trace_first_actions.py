#!/usr/bin/env python3
"""
Diagnostic 1: Trace first 10 actions to verify Tract line is prioritized.

Expected gold standard opening:
1. Activate Engraver hand effect → search Tract
2. Activate Tract → add Lurrie, discard Lurrie
3. Lurrie triggers → SS to field
4. Link Summon Requiem

If we see Sanct activation before Tract, prioritization isn't working.

Run from repo root:
    python3 scripts/diagnostics/01_trace_first_actions.py
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from ygo_combo.combo_enumeration import (
    EnumerationEngine, load_locked_library, get_deck_lists,
    load_library, init_card_database, set_lib, ENGRAVER, HOLACTIE
)

# Card codes for reference
TRACT = 98567237
SANCT = 35552985
LURRIE = 97651498
REQUIEM = 2463794

CARD_NAMES = {
    60764609: "Engraver",
    98567237: "Tract", 
    35552985: "Sanct",
    97651498: "Lurrie",
    2463794: "Requiem",
    28803166: "Lacrima (main)",
    46640168: "Lacrima (fusion)",
    49867899: "Sequence",
    32991300: "Agnumday",
    4731783: "A Bao A Qu",
    79559912: "Caesar",
    10000040: "Holactie",
}

def main():
    print("=" * 60)
    print("DIAGNOSTIC 1: First 10 Actions Trace")
    print("=" * 60)
    
    # Initialize
    print("\nInitializing...")
    if not init_card_database():
        print("ERROR: Failed to load card database")
        return 1
    
    lib = load_library()
    set_lib(lib)
    
    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)
    
    print(f"Main deck: {len(main_deck)} cards")
    print(f"Extra deck: {len(extra_deck)} cards")
    
    # Create engine with Tract prioritization
    engine = EnumerationEngine(
        lib, main_deck, extra_deck,
        verbose=True,
        dedupe_boards=True,
        dedupe_intermediate=True,
        prioritize_cards=[TRACT, LURRIE, REQUIEM]  # Prioritize gold standard line
    )
    
    # Override limits for diagnostic
    engine.max_depth = 10
    engine.max_paths = 1  # Just trace the FIRST path taken
    
    print("\n" + "=" * 60)
    print("TRACING FIRST PATH (depth 10, prioritizing Tract)")
    print("=" * 60)
    
    # Capture the first terminal
    terminals = engine.enumerate_all()
    
    if terminals:
        t = terminals[0]
        print("\n" + "=" * 60)
        print("FIRST PATH ACTION SEQUENCE:")
        print("=" * 60)
        for i, action in enumerate(t.action_sequence):
            card_name = CARD_NAMES.get(action.card_code, action.card_name or "?")
            print(f"  {i+1:2}. [{action.action_type:15}] {card_name}: {action.description}")
        
        print("\n" + "=" * 60)
        print("ANALYSIS:")
        print("=" * 60)
        
        # Check if Tract was activated early
        tract_seen = False
        sanct_seen = False
        for i, action in enumerate(t.action_sequence[:5]):
            if action.card_code == TRACT:
                tract_seen = True
                print(f"✓ Tract activated at step {i+1} (GOOD)")
            if action.card_code == SANCT:
                sanct_seen = True
                print(f"✗ Sanct activated at step {i+1} (BAD - wrong line)")
        
        if not tract_seen and not sanct_seen:
            print("? Neither Tract nor Sanct in first 5 actions")
        
        # Check for Lurrie
        lurrie_seen = any(a.card_code == LURRIE for a in t.action_sequence)
        if lurrie_seen:
            print("✓ Lurrie appeared in path (expected from Tract line)")
        else:
            print("✗ Lurrie NOT seen - Tract line may not be working")
    else:
        print("ERROR: No terminals found")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
