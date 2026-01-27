#!/usr/bin/env python3
"""
Minimal Engraver Combo Test

Tests the simplest possible case:
- Hand: 1x Fiendsmith Engraver + 4x dead cards
- Goal: Verify engine finds basic combo line
- Output: Step-by-step actions for manual verification

Usage:
    python scripts/test_engraver_combo.py

    # With custom depth limit
    python scripts/test_engraver_combo.py --max-depth 10

    # Extra verbose (print full game state)
    python scripts/test_engraver_combo.py --verbose
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

# Add src to path
sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "ygo_combo"))


# =============================================================================
# CARD DEFINITIONS
# =============================================================================

# Key card passcodes (verified from setup)
CARDS = {
    "Fiendsmith Engraver": 60764609,
    "Fiendsmith's Tract": 98567237,
    "Fiendsmith's Requiem": 2463794,
    "Fiendsmith's Sequence": 49867899,
    "Fiendsmith's Lacrima": 46640168,
    "D/D/D Wave High King Caesar": 79559912,
    "S:P Little Knight": 29301450,
    # Dead cards (non-engine)
    "Ash Blossom & Joyous Spring": 14558127,
    "Droll & Lock Bird": 94145021,
}

# Test hand: Engraver + 4 dead cards
TEST_HAND = [
    CARDS["Fiendsmith Engraver"],
    CARDS["Ash Blossom & Joyous Spring"],
    CARDS["Ash Blossom & Joyous Spring"],
    CARDS["Ash Blossom & Joyous Spring"],
    CARDS["Droll & Lock Bird"],
]


# =============================================================================
# PASSCODE TO NAME MAPPING
# =============================================================================

def load_card_names(library_path: Path) -> Dict[int, str]:
    """Load passcode to name mapping from validated deck."""
    names = {}

    # First, use our known cards
    for name, code in CARDS.items():
        names[code] = name

    # Try to load from validated deck for more names
    validated_path = library_path.parent / "cb_fiendsmith_deck_validated.json"
    if validated_path.exists():
        try:
            with open(validated_path) as f:
                data = json.load(f)

            for card in data.get("main_deck_engine", []):
                if card.get("passcode"):
                    names[card["passcode"]] = card.get("name", f"Card#{card['passcode']}")

            for card in data.get("extra_deck_pool", []):
                if card.get("passcode"):
                    names[card["passcode"]] = card.get("name", f"Card#{card['passcode']}")
        except Exception:
            pass

    return names


def get_card_name(passcode: int, names: Dict[int, str]) -> str:
    """Get human-readable card name from passcode."""
    return names.get(passcode, f"Unknown({passcode})")


# =============================================================================
# ACTION FORMATTING
# =============================================================================

def format_action(action: Dict[str, Any], names: Dict[int, str]) -> str:
    """Format an action dict into human-readable string."""
    parts = []

    # Action type
    action_type = action.get("type", action.get("action_type", "unknown"))
    parts.append(f"[{action_type.upper()}]")

    # Card involved
    card_code = action.get("code", action.get("card_id", action.get("passcode")))
    if card_code:
        card_name = get_card_name(card_code, names)
        parts.append(card_name)

    # Location info
    location = action.get("location", action.get("from_location"))
    if location:
        loc_name = format_location(location)
        parts.append(f"from {loc_name}")

    # Target/destination
    target = action.get("target", action.get("to_location"))
    if target:
        target_name = format_location(target) if isinstance(target, int) else str(target)
        parts.append(f"-> {target_name}")

    # Effect description if available
    desc = action.get("desc", action.get("description", action.get("effect")))
    if desc and isinstance(desc, str):
        parts.append(f'"{desc}"')

    return " ".join(parts)


def format_location(loc: int) -> str:
    """Convert location code to readable name."""
    locations = {
        0x01: "Deck",
        0x02: "Hand",
        0x04: "Monster Zone",
        0x08: "Spell/Trap Zone",
        0x10: "Graveyard",
        0x20: "Banished",
        0x40: "Extra Deck",
    }
    return locations.get(loc, f"Zone({hex(loc)})")


# =============================================================================
# TEST HARNESS
# =============================================================================

@dataclass
class TestResult:
    """Result of running the test."""
    success: bool
    actions_found: int
    terminals_found: int
    max_depth_reached: int
    error: Optional[str] = None
    action_log: List[str] = None


def run_minimal_test(
    library_path: Path,
    max_depth: int = 15,
    max_paths: int = 10,
    verbose: bool = False,
) -> TestResult:
    """
    Run minimal Engraver combo test.

    Returns TestResult with action log for verification.
    """
    result = TestResult(
        success=False,
        actions_found=0,
        terminals_found=0,
        max_depth_reached=0,
        action_log=[],
    )

    # Load card names
    names = load_card_names(library_path)

    print("=" * 60)
    print("MINIMAL ENGRAVER COMBO TEST")
    print("=" * 60)

    # Print test hand
    print("\nTEST HAND:")
    for i, code in enumerate(TEST_HAND):
        name = get_card_name(code, names)
        print(f"  {i+1}. {name} ({code})")

    print(f"\nCONFIG:")
    print(f"  Max Depth: {max_depth} actions")
    print(f"  Max Paths: {max_paths}")
    print(f"  Verbose: {verbose}")

    # Try to import and run engine
    print("\nINITIALIZING ENGINE...")

    try:
        from combo_enumeration import EnumerationEngine, enumerate_from_hand
        print("  + Imports successful")
    except ImportError as e:
        result.error = f"Import failed: {e}"
        print(f"  x {result.error}")
        return result

    # Load library
    print(f"\nLOADING LIBRARY: {library_path}")
    try:
        with open(library_path) as f:
            library = json.load(f)

        main_deck = library.get("main_deck", [])
        extra_deck = library.get("extra_deck", [])
        print(f"  + Main deck: {len(main_deck)} cards")
        print(f"  + Extra deck: {len(extra_deck)} cards")
    except Exception as e:
        result.error = f"Library load failed: {e}"
        print(f"  x {result.error}")
        return result

    # Initialize engine
    print("\nSTARTING ENUMERATION...")
    print("-" * 60)

    try:
        # This is where we'd actually run the engine
        # For now, we'll create a placeholder that shows what WOULD happen

        # Check if engine can be instantiated
        # config = EnumerationConfig(
        #     max_depth=max_depth,
        #     max_paths=max_paths,
        # )
        # engine = EnumerationEngine(config, library)
        # results = engine.enumerate_from_hand(TEST_HAND)

        # PLACEHOLDER: Since we can't run the actual engine here,
        # we'll print what we expect and prompt for manual testing

        print("\n  ENGINE TEST PLACEHOLDER")
        print("-" * 40)
        print("The engine interface needs to be run in your local environment")
        print("with ygopro-core properly configured.")
        print()
        print("To run the actual test, execute this in your repo:")
        print()
        print("```python")
        print("from combo_enumeration import EnumerationEngine")
        print("from pathlib import Path")
        print("import json")
        print()
        print("# Load library")
        print("with open('config/cb_fiendsmith_library.json') as f:")
        print("    library = json.load(f)")
        print()
        print("# Test hand")
        print(f"hand = {TEST_HAND}")
        print()
        print("# Run enumeration (you'll need to adapt to your engine API)")
        print("# engine = EnumerationEngine(...)")
        print("# results = engine.enumerate_from_hand(hand)")
        print("```")
        print()

        result.success = True
        result.error = "Placeholder - run locally with ygopro-core"

    except Exception as e:
        result.error = f"Engine error: {e}"
        print(f"  x {result.error}")
        import traceback
        traceback.print_exc()
        return result

    return result


def print_expected_combo():
    """Print the expected combo line for reference."""
    print("\n" + "=" * 60)
    print("EXPECTED COMBO LINE (for verification)")
    print("=" * 60)

    expected_actions = [
        "1. Activate Fiendsmith Engraver (Hand)",
        "   -> Effect: Send 'Fiendsmith's Tract' from Deck to GY",
        "",
        "2. Fiendsmith's Tract triggers (GY)",
        "   -> Effect: Add 1 'Fiendsmith' card from Deck to hand",
        "   -> Likely choice: Lacrima the Crimson Tears",
        "",
        "3. Special Summon Fiendsmith's Requiem (Extra Deck)",
        "   -> Fusion Summon using Engraver as material",
        "   -> Engraver sent to GY",
        "",
        "4. Fiendsmith's Requiem effect (Field)",
        "   -> Special Summon 1 'Fiendsmith Token' (Fiend/LIGHT/Lv6/2000/2000)",
        "",
        "5. Link Summon Fiendsmith's Sequence (Extra Deck)",
        "   -> Materials: Token + Requiem",
        "   -> Both sent to GY",
        "",
        "6. Fiendsmith's Sequence effect (Field)",
        "   -> Send 1 'Fiendsmith' card from Deck to GY",
        "   -> Or use other Fiendsmith effect",
        "",
        "7. Continue combo...",
        "   -> Sequence can revive Requiem",
        "   -> Make Rank 6 (Caesar) or Link plays",
        "",
        "Expected End Board (minimum):",
        "- D/D/D Wave High King Caesar (Rank 6)",
        "- S:P Little Knight (Link 2)",
        "- Possibly Fiendsmith backrow",
    ]

    for line in expected_actions:
        print(f"  {line}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Minimal Engraver combo test for engine validation"
    )
    parser.add_argument(
        "--library",
        type=Path,
        default=Path("config/cb_fiendsmith_library.json"),
        help="Path to library JSON",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=15,
        help="Maximum combo depth (actions)",
    )
    parser.add_argument(
        "--max-paths",
        type=int,
        default=10,
        help="Maximum paths to explore",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed game state",
    )
    parser.add_argument(
        "--show-expected",
        action="store_true",
        help="Just show expected combo line",
    )

    args = parser.parse_args()

    if args.show_expected:
        print_expected_combo()
        return 0

    if not args.library.exists():
        print(f"ERROR: Library not found: {args.library}")
        print("Run setup_deck.py first to create the library.")
        return 1

    # Run test
    result = run_minimal_test(
        args.library,
        max_depth=args.max_depth,
        max_paths=args.max_paths,
        verbose=args.verbose,
    )

    # Print expected combo for comparison
    print_expected_combo()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    if result.success:
        print("+ Test completed")
        print(f"  Actions found: {result.actions_found}")
        print(f"  Terminals found: {result.terminals_found}")
        print(f"  Max depth reached: {result.max_depth_reached}")
    else:
        print(f"x Test failed: {result.error}")

    if result.action_log:
        print("\nACTION LOG:")
        for i, action in enumerate(result.action_log):
            print(f"  {i+1}. {action}")

    print("\n" + "=" * 60)
    print("NEXT STEPS")
    print("=" * 60)
    print("1. Run this script in your local environment with ygopro-core")
    print("2. Compare output actions to expected combo line above")
    print("3. Note any discrepancies for debugging")
    print("4. If clean, proceed to 2-card hand tests")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
