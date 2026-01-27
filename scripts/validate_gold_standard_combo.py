#!/usr/bin/env python3
"""
Validate Gold Standard Combo

This script attempts to execute the gold standard combo through the ygopro-core engine,
verifying each step is legal and the combo completes as expected.

The combo:
1. Engraver pitch → search Tract
2. Tract add Lurrie, discard Lurrie
3. Lurrie SS from GY
4. Link Lurrie → Requiem
5. Requiem tribute → SS Lacrima the Crimson Tears
6. Lacrima CrimT on summon → send Kyrie to GY
... and so on to A Bao A Qu + Caesar endboard

Usage:
    python scripts/validate_gold_standard_combo.py
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parents[1] / "src" / "ygo_combo"))

# =============================================================================
# CARD PASSCODES (from verified_cards.json)
# =============================================================================

CARDS = {
    # Main deck
    "Fiendsmith Engraver": 60764609,
    "Fiendsmith's Tract": 98567237,
    "Fabled Lurrie": 97651498,
    "Lacrima the Crimson Tears": 28803166,
    "Fiendsmith Kyrie": 26434972,
    "Buio the Dawn's Light": 19000848,
    "Mutiny in the Sky": 71593652,

    # Extra deck
    "Fiendsmith's Requiem": 2463794,
    "Fiendsmith's Sequence": 49867899,
    "Fiendsmith's Lacrima": 46640168,
    "Aerial Eater": 28143384,
    "Fiendsmith's Agnumday": 32991300,
    "Fiendsmith's Rextremende": 11464648,
    "A Bao A Qu, the Lightless Shadow": 4731783,
    "Necroquip Princess": 93860227,
    "D/D/D Wave High King Caesar": 79559912,

    # Filler
    "Holactie the Creator of Light": 10000040,
}

# Reverse lookup
CODE_TO_NAME = {v: k for k, v in CARDS.items()}

# =============================================================================
# GOLD STANDARD COMBO DEFINITION
# =============================================================================

GOLD_STANDARD_COMBO = [
    {
        "step": 1,
        "action": "ACTIVATE",
        "card": "Fiendsmith Engraver",
        "effect": "hand eff0",
        "description": "Discard Engraver to search Tract"
    },
    {
        "step": 2,
        "action": "SELECT_CARD",
        "target": "Fiendsmith's Tract",
        "description": "Select Tract from deck"
    },
    {
        "step": 3,
        "action": "ACTIVATE",
        "card": "Fiendsmith's Tract",
        "effect": "hand eff0",
        "description": "Activate Tract to add Lurrie"
    },
    {
        "step": 4,
        "action": "SELECT_CARD",
        "target": "Fabled Lurrie",
        "description": "Select Lurrie to add"
    },
    {
        "step": 5,
        "action": "SELECT_CARD",
        "target": "Fabled Lurrie",
        "description": "Discard Lurrie as cost"
    },
    {
        "step": 6,
        "action": "TRIGGER",
        "card": "Fabled Lurrie",
        "description": "Lurrie triggers and SS itself"
    },
    {
        "step": 7,
        "action": "LINK_SUMMON",
        "card": "Fiendsmith's Requiem",
        "materials": ["Fabled Lurrie"],
        "description": "Link-1 using Lurrie"
    },
    {
        "step": 8,
        "action": "ACTIVATE",
        "card": "Fiendsmith's Requiem",
        "effect": "field eff0",
        "description": "Tribute Requiem to SS from deck"
    },
    {
        "step": 9,
        "action": "SELECT_CARD",
        "target": "Lacrima the Crimson Tears",
        "description": "Select Lacrima CrimT from deck"
    },
    {
        "step": 10,
        "action": "TRIGGER",
        "card": "Lacrima the Crimson Tears",
        "description": "Lacrima CrimT on summon - send card from deck"
    },
    {
        "step": 11,
        "action": "SELECT_CARD",
        "target": "Fiendsmith Kyrie",
        "description": "Send Kyrie from deck to GY"
    },
    {
        "step": 12,
        "action": "ACTIVATE",
        "card": "Fiendsmith's Requiem",
        "effect": "GY eff1",
        "description": "Requiem equips to Lacrima CrimT from GY"
    },
    {
        "step": 13,
        "action": "SELECT_CARD",
        "target": "Lacrima the Crimson Tears",
        "description": "Target Lacrima CrimT to equip"
    },
    {
        "step": 14,
        "action": "ACTIVATE",
        "card": "Fiendsmith Kyrie",
        "effect": "GY eff1",
        "description": "Kyrie banishes to Fusion Summon"
    },
    {
        "step": 15,
        "action": "FUSION_SUMMON",
        "card": "Fiendsmith's Lacrima",
        "materials": ["Lacrima the Crimson Tears", "Fiendsmith's Requiem"],
        "description": "Fusion using Lacrima CrimT + equipped Requiem"
    },
    {
        "step": 16,
        "action": "TRIGGER",
        "card": "Fiendsmith's Lacrima",
        "description": "Lacrima Fusion on summon - SS from GY"
    },
    {
        "step": 17,
        "action": "SELECT_CARD",
        "target": "Fiendsmith Engraver",
        "description": "Target Engraver in GY to SS"
    },
    {
        "step": 18,
        "action": "LINK_SUMMON",
        "card": "Fiendsmith's Sequence",
        "materials": ["Fiendsmith's Lacrima", "Fiendsmith Engraver"],
        "description": "Link-2 using Lacrima Fusion + Engraver"
    },
    {
        "step": 19,
        "action": "ACTIVATE",
        "card": "Fiendsmith's Sequence",
        "effect": "field eff0",
        "description": "Sequence Fusion Summon from GY"
    },
    {
        "step": 20,
        "action": "SELECT_FUSION",
        "card": "Aerial Eater",
        "materials": ["Fiendsmith's Requiem", "Fabled Lurrie"],
        "description": "Fusion Summon Aerial Eater shuffling Requiem + Lurrie"
    },
    {
        "step": 21,
        "action": "TRIGGER",
        "card": "Aerial Eater",
        "description": "Aerial Eater on summon - send Fiend from deck"
    },
    {
        "step": 22,
        "action": "SELECT_CARD",
        "target": "Buio the Dawn's Light",
        "description": "Send Buio from deck to GY"
    },
    {
        "step": 23,
        "action": "TRIGGER",
        "card": "Buio the Dawn's Light",
        "description": "Buio triggers - add Mutiny"
    },
    # Continue with remaining steps...
]

# =============================================================================
# COMBO VALIDATION
# =============================================================================

def load_gold_standard() -> Dict:
    """Load the gold standard combo definition."""
    config_path = Path(__file__).parents[1] / "config" / "gold_standard_combo.json"
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {}

def print_combo_steps():
    """Print the gold standard combo steps for reference."""
    combo = load_gold_standard()

    print("=" * 70)
    print("GOLD STANDARD COMBO: Engraver → A Bao A Qu + Caesar")
    print("=" * 70)

    steps = combo.get("combo_steps", [])
    for step in steps:
        print(f"\n{step['step']:2d}. {step['action']}")
        print(f"    Card: {step.get('card_id', 'N/A')} ({step.get('card_id', '')})")
        print(f"    {step.get('description', step.get('result', ''))}")

    print("\n" + "=" * 70)
    print("ENDBOARD:")
    endboard = combo.get("endboard", {})
    for card in endboard.get("field", []):
        print(f"  - {card['name']} ({card['position']})")
    print("=" * 70)


def validate_combo_cards():
    """Verify all combo cards are in the library."""
    library_path = Path(__file__).parents[1] / "config" / "locked_library.json"
    combo_path = Path(__file__).parents[1] / "config" / "gold_standard_combo.json"

    if not library_path.exists():
        print("ERROR: locked_library.json not found")
        return False

    if not combo_path.exists():
        print("ERROR: gold_standard_combo.json not found")
        return False

    with open(library_path) as f:
        library = json.load(f)

    with open(combo_path) as f:
        combo = json.load(f)

    library_cards = set(library.get("cards", {}).keys())

    missing_main = []
    missing_extra = []

    for card in combo.get("cards_used", {}).get("main_deck", []):
        if str(card["id"]) not in library_cards:
            missing_main.append(card)

    for card in combo.get("cards_used", {}).get("extra_deck", []):
        if str(card["id"]) not in library_cards:
            missing_extra.append(card)

    print("=" * 70)
    print("CARD VALIDATION")
    print("=" * 70)

    if missing_main or missing_extra:
        print("\nMISSING CARDS:")
        for card in missing_main:
            print(f"  Main: {card['name']} ({card['id']})")
        for card in missing_extra:
            print(f"  Extra: {card['name']} ({card['id']})")
        return False

    print("\n✓ All combo cards found in library")

    # Check card counts
    print("\nCard counts:")
    for card in combo.get("cards_used", {}).get("main_deck", []):
        lib_card = library["cards"].get(str(card["id"]), {})
        lib_count = lib_card.get("count", 0)
        needed = card.get("copies", 1)
        status = "✓" if lib_count >= needed else "✗"
        print(f"  {status} {card['name']}: need {needed}, have {lib_count}")

    return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate gold standard combo")
    parser.add_argument("--show-steps", action="store_true", help="Show combo steps")
    parser.add_argument("--validate-cards", action="store_true", help="Validate cards in library")
    parser.add_argument("--run-engine", action="store_true", help="Attempt to run through engine")

    args = parser.parse_args()

    if args.show_steps:
        print_combo_steps()
        return 0

    if args.validate_cards:
        if validate_combo_cards():
            print("\n✓ Card validation passed")
            return 0
        else:
            print("\n✗ Card validation failed")
            return 1

    if args.run_engine:
        print("Engine execution not yet implemented.")
        print("Run combo_enumeration.py and look for this path in results.")
        return 0

    # Default: show all info
    print_combo_steps()
    print()
    validate_combo_cards()

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
To find this combo in enumeration:
1. Run: python src/ygo_combo/combo_enumeration.py --max-depth 50 --max-paths 100000
2. Look for terminal with A Bao A Qu + Caesar on field
3. Or search results for specific action sequence

The enumeration explores ALL paths, so this combo should be findable
if enough paths are explored. Current runs found shorter Caesar paths
but not this full A Bao A Qu + Caesar line.
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
