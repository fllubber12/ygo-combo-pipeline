#!/usr/bin/env python3
"""
Test different starting hands after applying the configurable hand patch.

Usage:
    # Test Engraver only (baseline)
    python scripts/test_hands.py --hand engraver
    
    # Test Engraver + Terrortop
    python scripts/test_hands.py --hand engraver-terrortop
    
    # Test custom hand by passcodes
    python scripts/test_hands.py --codes 60764609,81275020,14558127,14558127,14558127
    
    # List available preset hands
    python scripts/test_hands.py --list
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "cffi"))


# =============================================================================
# CARD PASSCODES
# =============================================================================

CARDS = {
    # Fiendsmith
    "engraver": 60764609,
    "tract": 12805772,
    "sanct": 53932291,
    "requiem": 2463794,
    "sequence": 49867899,
    "lacrima_ed": 61395536,
    "lacrima_main": 28822133,  # Lacrima the Crimson Tears (main deck)
    
    # Crystal Beast
    "sapphire": 7093411,
    "ruby": 32710364,
    "rainbow_dragon": 79856792,
    
    # Speedroid
    "terrortop": 81275020,
    "taketomborg": 8591267,
    
    # Spells
    "crystal_bond": 2700673,
    "rainbow_bridge": 25355315,
    "golden_rule": 22460605,
    "foolish_goods": 35726888,
    
    # Dead cards
    "ash": 14558127,
    "droll": 94145021,
    "holactie": 10000040,
}


# =============================================================================
# PRESET HANDS
# =============================================================================

PRESET_HANDS = {
    "engraver": {
        "name": "Engraver + 4 Dead",
        "cards": ["engraver", "ash", "ash", "ash", "droll"],
        "description": "Baseline 1-card starter test",
    },
    "engraver-terrortop": {
        "name": "Engraver + Terrortop",
        "cards": ["engraver", "terrortop", "ash", "ash", "ash"],
        "description": "2 starters - should combo harder",
    },
    "terrortop-only": {
        "name": "Terrortop + 4 Dead",
        "cards": ["terrortop", "ash", "ash", "ash", "droll"],
        "description": "Test Speedroid line alone",
    },
    "crystal-bond": {
        "name": "Crystal Bond + 4 Dead",
        "cards": ["crystal_bond", "ash", "ash", "ash", "droll"],
        "description": "Test Crystal Beast line",
    },
    "double-starter": {
        "name": "Engraver + Crystal Bond",
        "cards": ["engraver", "crystal_bond", "ash", "ash", "ash"],
        "description": "Fiendsmith + Crystal Beast together",
    },
    "triple-starter": {
        "name": "Engraver + Terrortop + Crystal Bond",
        "cards": ["engraver", "terrortop", "crystal_bond", "ash", "ash"],
        "description": "3 starters - maximum combo potential",
    },
    "god-hand": {
        "name": "5 Starters",
        "cards": ["engraver", "terrortop", "crystal_bond", "rainbow_bridge", "foolish_goods"],
        "description": "Theoretical best hand",
    },
    "brick": {
        "name": "All Dead Cards",
        "cards": ["ash", "ash", "ash", "droll", "droll"],
        "description": "Should find 0 combos (validation test)",
    },
}


def get_hand_passcodes(hand_name: str) -> List[int]:
    """Convert preset hand name to list of passcodes."""
    if hand_name not in PRESET_HANDS:
        raise ValueError(f"Unknown hand preset: {hand_name}")
    
    preset = PRESET_HANDS[hand_name]
    passcodes = []
    
    for card_key in preset["cards"]:
        if card_key not in CARDS:
            raise ValueError(f"Unknown card: {card_key}")
        passcodes.append(CARDS[card_key])
    
    return passcodes


def list_presets():
    """Print available preset hands."""
    print("Available hand presets:\n")
    
    for key, preset in PRESET_HANDS.items():
        print(f"  {key}")
        print(f"    Name: {preset['name']}")
        print(f"    Cards: {', '.join(preset['cards'])}")
        print(f"    Description: {preset['description']}")
        print()


def run_hand_test(hand: List[int], max_depth: int = 25, verbose: bool = False):
    """Run enumeration with specific hand."""

    # Import engine
    try:
        from engine_interface import init_card_database, load_library, set_lib
        from combo_enumeration import EnumerationEngine, load_locked_library, get_deck_lists
        import combo_enumeration
    except ImportError as e:
        print(f"ERROR: Could not import engine: {e}")
        return None

    # Initialize engine
    print("Initializing card database...")
    if not init_card_database():
        print("ERROR: Failed to initialize card database")
        return None

    lib = load_library()
    set_lib(lib)

    # Load library
    library_path = Path("config/locked_library.json")
    if not library_path.exists():
        print(f"ERROR: Library not found: {library_path}")
        return None

    print("=" * 60)
    print("HAND TEST")
    print("=" * 60)

    # Show hand
    print("\n Starting Hand:")
    for i, code in enumerate(hand):
        name = next((k for k, v in CARDS.items() if v == code), f"Unknown({code})")
        print(f"  {i+1}. {name} ({code})")

    # Load deck
    print(f"\n Loading library from {library_path}...")
    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)
    print(f"  Main deck: {len(main_deck)} cards")
    print(f"  Extra deck: {len(extra_deck)} cards")

    # Set limits
    combo_enumeration.MAX_DEPTH = max_depth
    combo_enumeration.MAX_PATHS = 1000

    # Create engine
    print(f"\n Running enumeration (max_depth={max_depth})...")
    engine = EnumerationEngine(lib, main_deck, extra_deck, verbose=verbose)
    
    # Run with specific hand
    try:
        terminals = engine.enumerate_from_hand(hand)
    except NotImplementedError:
        print("\n❌ ERROR: enumerate_from_hand() not implemented!")
        print("   Run: python scripts/patch_configurable_hand.py --apply")
        return None
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Results
    print(f"\n📊 Results:")
    print(f"  Paths explored: {engine.paths_explored}")
    print(f"  Unique terminals: {len(terminals)}")
    print(f"  Transposition hits: {engine.transposition_table.hits}")
    
    if terminals:
        print(f"\n🏆 Terminal Boards Found:")
        for i, term in enumerate(terminals[:5]):  # Show first 5
            depth = getattr(term, 'depth', '?')
            score = getattr(term, 'score', '?')
            print(f"  {i+1}. Depth {depth}, Score {score}")
        
        if len(terminals) > 5:
            print(f"  ... and {len(terminals) - 5} more")
    else:
        print("\n  No terminal boards found (brick hand?)")
    
    return terminals


def main():
    parser = argparse.ArgumentParser(description="Test different starting hands")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--hand", type=str, help="Preset hand name (e.g., 'engraver-terrortop')")
    group.add_argument("--codes", type=str, help="Comma-separated passcodes")
    group.add_argument("--list", action="store_true", help="List available presets")
    
    parser.add_argument("--max-depth", type=int, default=25, help="Max combo depth")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if args.list:
        list_presets()
        return 0
    
    # Get hand
    if args.hand:
        try:
            hand = get_hand_passcodes(args.hand)
            print(f"Using preset: {args.hand}")
        except ValueError as e:
            print(f"ERROR: {e}")
            print("Use --list to see available presets")
            return 1
    else:
        # Parse comma-separated codes
        try:
            hand = [int(x.strip()) for x in args.codes.split(",")]
        except ValueError:
            print("ERROR: --codes must be comma-separated integers")
            return 1
    
    # Validate hand size
    if len(hand) < 1:
        print("ERROR: Hand must have at least 1 card")
        return 1
    
    if len(hand) > 5:
        print(f"WARNING: Hand has {len(hand)} cards, truncating to 5")
        hand = hand[:5]
    
    # Pad to 5 with Holactie
    while len(hand) < 5:
        hand.append(CARDS["holactie"])
    
    # Run test
    result = run_hand_test(hand, args.max_depth, args.verbose)
    
    return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
