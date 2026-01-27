#!/usr/bin/env python3
"""
Debug script for Engraver combo - traces every action to find where engine fails.

This script runs the Engraver combo with maximum verbosity to identify:
1. What actions are being offered at each step
2. What actions the engine is taking
3. Where the combo stops and why
4. Whether expected cards (Caesar, Lacrima, Agnumday, Rextremende) appear

Expected Engraver 1-card combo end board:
- D/D/D Wave High King Caesar (Rank 6) on field
- Graveyard: Lacrima, Agnumday, Rextremende, Requiem, Sequence, etc.
- Potentially more disruption

Usage:
    python scripts/debug_engraver.py
    
    # Show all available actions at each step
    python scripts/debug_engraver.py --show-all-actions
    
    # Trace a specific path
    python scripts/debug_engraver.py --trace-path 0
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "ygo_combo"))


# =============================================================================
# CARD DATABASE
# =============================================================================

CARD_NAMES = {
    # Fiendsmith Main Deck
    60764609: "Fiendsmith Engraver",
    12805772: "Fiendsmith's Tract",
    53932291: "Fiendsmith's Sanct",
    28822133: "Lacrima the Crimson Tears",
    93920420: "Fiendsmith Kyrie",
    44709035: "Fiendsmith in Paradise",
    
    # Fiendsmith Extra Deck
    2463794: "Fiendsmith's Requiem",
    49867899: "Fiendsmith's Sequence",
    61395536: "Fiendsmith's Lacrima",
    82135803: "Fiendsmith's Desirae",
    32991300: "Fiendsmith's Agnumday",
    11464648: "Fiendsmith's Rextremende",
    35552986: "Fiendsmith Token",
    
    # Other Extra Deck
    79559912: "D/D/D Wave High King Caesar",
    29301450: "S:P Little Knight",
    60417395: "Cherubini, Ebon Angel",
    27552504: "Beatrice, Lady of the Eternal",
    4731783: "A Bao A Qu",
    
    # Crystal Beast
    7093411: "Crystal Beast Sapphire Pegasus",
    32710364: "Crystal Beast Ruby Carbuncle",
    79856792: "Rainbow Dragon",
    
    # Speedroid
    81275020: "Speedroid Terrortop",
    8591267: "Speedroid Taketomborg",
    
    # Dead cards
    14558127: "Ash Blossom",
    94145021: "Droll & Lock Bird",
    10000040: "Holactie",
}


def get_card_name(code: int) -> str:
    """Get human-readable card name."""
    return CARD_NAMES.get(code, f"Unknown({code})")


# =============================================================================
# LOCATION/POSITION HELPERS
# =============================================================================

LOCATIONS = {
    0x01: "Deck",
    0x02: "Hand",
    0x04: "Monster Zone",
    0x08: "Spell/Trap Zone",
    0x10: "Graveyard",
    0x20: "Banished",
    0x40: "Extra Deck",
}


def get_location_name(loc: int) -> str:
    """Get location name from code."""
    return LOCATIONS.get(loc, f"Loc({hex(loc)})")


# =============================================================================
# DEBUG TRACER
# =============================================================================

@dataclass
class ActionRecord:
    """Record of a single action taken."""
    depth: int
    action_type: str
    card_code: int
    card_name: str
    from_location: str
    description: str
    available_actions: int


class ComboTracer:
    """Traces combo execution step by step."""
    
    def __init__(self):
        self.actions: List[ActionRecord] = []
        self.action_counts = defaultdict(int)
        self.cards_seen = set()
        self.max_depth = 0
        self.terminal_boards = []
    
    def record_action(
        self,
        depth: int,
        action: Dict[str, Any],
        available_count: int,
    ):
        """Record an action being taken."""
        code = action.get("code", action.get("card_id", 0))
        
        record = ActionRecord(
            depth=depth,
            action_type=action.get("type", action.get("action_type", "unknown")),
            card_code=code,
            card_name=get_card_name(code),
            from_location=get_location_name(action.get("location", 0)),
            description=str(action.get("desc", action.get("description", ""))),
            available_actions=available_count,
        )
        
        self.actions.append(record)
        self.action_counts[record.card_name] += 1
        self.cards_seen.add(code)
        self.max_depth = max(self.max_depth, depth)
    
    def record_terminal(self, board_state: Dict[str, Any]):
        """Record a terminal board state."""
        self.terminal_boards.append(board_state)
    
    def print_trace(self):
        """Print the full action trace."""
        print("\n" + "=" * 70)
        print("ACTION TRACE")
        print("=" * 70)
        
        for i, action in enumerate(self.actions):
            indent = "  " * action.depth
            print(f"{indent}[{action.depth}] {action.action_type}: {action.card_name}")
            print(f"{indent}     From: {action.from_location}")
            if action.description:
                print(f"{indent}     Desc: {action.description}")
            print(f"{indent}     (had {action.available_actions} choices)")
    
    def print_summary(self):
        """Print summary statistics."""
        print("\n" + "=" * 70)
        print("DEBUG SUMMARY")
        print("=" * 70)
        
        print(f"\n📊 Statistics:")
        print(f"  Total actions: {len(self.actions)}")
        print(f"  Max depth reached: {self.max_depth}")
        print(f"  Unique cards used: {len(self.cards_seen)}")
        print(f"  Terminal boards: {len(self.terminal_boards)}")
        
        print(f"\n🃏 Cards Used (by frequency):")
        for card, count in sorted(self.action_counts.items(), key=lambda x: -x[1]):
            print(f"  {count}x {card}")
        
        # Check for expected cards
        print(f"\n🎯 Expected Combo Pieces:")
        expected = [
            (60764609, "Fiendsmith Engraver", "Starter"),
            (12805772, "Fiendsmith's Tract", "Send to GY"),
            (2463794, "Fiendsmith's Requiem", "Fusion"),
            (35552986, "Fiendsmith Token", "From Requiem"),
            (49867899, "Fiendsmith's Sequence", "Link"),
            (79559912, "D/D/D Wave High King Caesar", "End board"),
            (61395536, "Fiendsmith's Lacrima", "GY resource"),
            (32991300, "Fiendsmith's Agnumday", "GY resource"),
            (11464648, "Fiendsmith's Rextremende", "GY negate"),
        ]
        
        for code, name, role in expected:
            status = "✓" if code in self.cards_seen else "✗ MISSING"
            print(f"  {status} {name} ({role})")


# =============================================================================
# MAIN DEBUG FUNCTION  
# =============================================================================

def run_debug_enumeration(show_all_actions: bool = False):
    """Run enumeration with full debugging."""

    # Import engine components
    try:
        from engine_interface import init_card_database, load_library, set_lib
        from combo_enumeration import (
            EnumerationEngine,
            load_locked_library,
            get_deck_lists,
            ENGRAVER,
            HOLACTIE,
        )
        import combo_enumeration
    except ImportError as e:
        print(f"ERROR: Import failed: {e}")
        return

    # Initialize engine
    print("Initializing card database...")
    if not init_card_database():
        print("ERROR: Failed to initialize card database")
        return

    lib = load_library()
    set_lib(lib)

    # Load library
    library_path = Path("config/locked_library.json")
    print(f"Loading library from {library_path}...")

    try:
        library = load_locked_library()
        main_deck, extra_deck = get_deck_lists(library)
    except Exception as e:
        print(f"ERROR: Could not load library: {e}")
        return

    print(f"  Main deck: {len(main_deck)} cards")
    print(f"  Extra deck: {len(extra_deck)} cards")

    # Show extra deck contents
    print(f"\n Extra Deck Contents:")
    for code in extra_deck:
        print(f"  - {get_card_name(code)} ({code})")

    # Test hand
    hand = [ENGRAVER, HOLACTIE, HOLACTIE, HOLACTIE, HOLACTIE]
    print(f"\n Test Hand:")
    for code in hand:
        print(f"  - {get_card_name(code)} ({code})")

    # Set config with high limits
    combo_enumeration.MAX_DEPTH = 30
    combo_enumeration.MAX_PATHS = 500

    print(f"\n Config:")
    print(f"  max_depth: {combo_enumeration.MAX_DEPTH}")
    print(f"  max_paths: {combo_enumeration.MAX_PATHS}")

    # Create tracer
    tracer = ComboTracer()

    # Run enumeration
    print(f"\n Starting enumeration...")
    print("=" * 70)

    try:
        # Create engine
        engine = EnumerationEngine(lib, main_deck, extra_deck, verbose=True)
        
        # Run with hand
        terminals = engine.enumerate_from_hand(hand)
        
        print(f"\n✓ Enumeration complete")
        print(f"  Paths explored: {engine.paths_explored}")
        print(f"  Terminals found: {len(terminals)}")
        
        # Analyze terminals
        if terminals:
            print(f"\n🏆 Terminal Board Analysis:")
            for i, term in enumerate(terminals[:10]):
                print(f"\n  Terminal {i+1}:")
                print(f"    Depth: {getattr(term, 'depth', '?')}")
                print(f"    Score: {getattr(term, 'score', '?')}")
                
                # Try to get board state
                board = getattr(term, 'board', None) or getattr(term, 'board_signature', None)
                if board:
                    monsters = getattr(board, 'monsters', [])
                    gy = getattr(board, 'graveyard', [])
                    
                    if monsters:
                        print(f"    Monsters: {[get_card_name(c) for c in monsters]}")
                    if gy:
                        print(f"    GY: {[get_card_name(c) for c in gy[:5]]}...")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Analysis
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    
    print("""
Expected Engraver 1-card combo:
1. Activate Engraver → Send Tract to GY
2. Tract triggers → Search Fiendsmith (usually Lacrima main deck)
3. Fusion Summon Requiem (banish Engraver from GY)
4. Requiem → Summon Token
5. Link Summon Sequence (Token + Requiem)
6. Sequence → Send Fiendsmith to GY (e.g., Lacrima ED or Paradise)
7. Sequence revives Requiem
8. Requiem makes another Token
9. Overlay 2 Level 6s → Caesar
10. Caesar detach → Special from GY
...continuing to build more board

If engine stops before Caesar, check:
- Is Caesar in the extra deck?
- Are Level 6 monsters being made?
- Is the Xyz summon action being offered?
    """)
    
    # Check if Caesar was found
    caesar_code = 79559912
    caesar_found = False
    
    for term in terminals:
        board = getattr(term, 'board', None) or getattr(term, 'board_signature', None)
        if board:
            monsters = getattr(board, 'monsters', [])
            if caesar_code in monsters:
                caesar_found = True
                break
    
    if caesar_found:
        print("✓ Caesar WAS found in at least one terminal")
    else:
        print("✗ Caesar was NOT found in any terminal!")
        print("  This suggests the engine is stopping before the Xyz summon")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Debug Engraver combo")
    parser.add_argument("--show-all-actions", action="store_true", 
                       help="Show all available actions at each step")
    
    args = parser.parse_args()
    
    run_debug_enumeration(show_all_actions=args.show_all_actions)


if __name__ == "__main__":
    main()
