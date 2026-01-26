#!/usr/bin/env python3
"""
Convert CB Fiendsmith library to locked_library.json format.

The combo_enumeration.py expects:
{
  "cards": {
    "12345678": {"is_extra_deck": false, "name": "Card Name"},
    ...
  }
}

But cb_fiendsmith_library.json has:
{
  "main_deck": [12345678, ...],
  "extra_deck": [87654321, ...]
}

This script converts between formats.

Usage:
    python scripts/convert_library_format.py
    
    # Or specify paths
    python scripts/convert_library_format.py \
        --input config/cb_fiendsmith_library.json \
        --output config/locked_library.json \
        --names config/cb_fiendsmith_deck_validated.json
"""

import json
import argparse
from pathlib import Path
from typing import Dict, List, Any
from collections import Counter


def load_card_names(validated_path: Path) -> Dict[int, str]:
    """Load card names from validated deck JSON."""
    names = {}
    
    if not validated_path.exists():
        return names
    
    try:
        with open(validated_path) as f:
            data = json.load(f)
        
        for card in data.get("main_deck_engine", []):
            if card.get("passcode"):
                names[card["passcode"]] = card.get("name", f"Card#{card['passcode']}")
        
        for card in data.get("main_deck_non_engine", []):
            if card.get("passcode"):
                names[card["passcode"]] = card.get("name", f"Card#{card['passcode']}")
        
        for card in data.get("extra_deck_pool", []):
            if card.get("passcode"):
                names[card["passcode"]] = card.get("name", f"Card#{card['passcode']}")
    
    except Exception as e:
        print(f"Warning: Could not load names from {validated_path}: {e}")
    
    return names


def convert_to_locked_format(
    input_path: Path,
    names_path: Path = None,
) -> Dict[str, Any]:
    """
    Convert list-based library to locked_library.json format.
    
    Args:
        input_path: Path to cb_fiendsmith_library.json
        names_path: Optional path to validated deck JSON for card names
        
    Returns:
        Dictionary in locked_library.json format
    """
    # Load input
    with open(input_path) as f:
        lib = json.load(f)
    
    main_deck = lib.get("main_deck", [])
    extra_deck = lib.get("extra_deck", [])
    
    # Load names if available
    names = {}
    if names_path:
        names = load_card_names(names_path)
    
    # Build cards dict
    cards = {}
    
    # Track counts for main deck (can have multiples)
    main_counts = Counter(main_deck)
    
    for passcode in set(main_deck):
        cards[str(passcode)] = {
            "is_extra_deck": False,
            "name": names.get(passcode, f"Card#{passcode}"),
            "count": main_counts[passcode],
        }
    
    # Extra deck (1 of each)
    for passcode in extra_deck:
        cards[str(passcode)] = {
            "is_extra_deck": True,
            "name": names.get(passcode, f"Card#{passcode}"),
            "count": 1,
        }
    
    # Build output structure
    output = {
        "name": lib.get("name", "CB Fiendsmith Library"),
        "description": "Crystal Beast Fiendsmith deck for combo analysis",
        "cards": cards,
        "_meta": {
            "main_deck_total": len(main_deck),
            "main_deck_unique": len(set(main_deck)),
            "extra_deck_total": len(extra_deck),
            "converted_from": str(input_path),
        }
    }
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Convert CB Fiendsmith library to locked_library.json format"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("config/cb_fiendsmith_library.json"),
        help="Input library (list format)",
    )
    parser.add_argument(
        "--output", 
        type=Path,
        default=Path("config/locked_library.json"),
        help="Output library (locked format)",
    )
    parser.add_argument(
        "--names",
        type=Path,
        default=Path("config/cb_fiendsmith_deck_validated.json"),
        help="Validated deck JSON for card names",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Backup existing locked_library.json before overwriting",
    )
    
    args = parser.parse_args()
    
    # Check input exists
    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}")
        return 1
    
    # Backup existing if requested
    if args.backup and args.output.exists():
        backup_path = args.output.with_suffix(".json.bak")
        print(f"Backing up {args.output} to {backup_path}")
        import shutil
        shutil.copy(args.output, backup_path)
    
    # Convert
    print(f"Converting {args.input} to locked_library format...")
    
    names_path = args.names if args.names.exists() else None
    converted = convert_to_locked_format(args.input, names_path)
    
    # Write output
    with open(args.output, 'w') as f:
        json.dump(converted, f, indent=2)
    
    # Summary
    meta = converted.get("_meta", {})
    cards = converted.get("cards", {})
    
    main_cards = [c for c in cards.values() if not c["is_extra_deck"]]
    extra_cards = [c for c in cards.values() if c["is_extra_deck"]]
    
    print(f"\n✓ Created {args.output}")
    print(f"  Main deck: {meta.get('main_deck_total', '?')} cards ({len(main_cards)} unique)")
    print(f"  Extra deck: {len(extra_cards)} cards")
    print(f"  Total entries: {len(cards)}")
    
    # Show a few card names
    print(f"\nSample cards:")
    for i, (code, info) in enumerate(list(cards.items())[:5]):
        deck_type = "ED" if info["is_extra_deck"] else "MD"
        print(f"  [{deck_type}] {info['name']} ({code})")
    if len(cards) > 5:
        print(f"  ... and {len(cards) - 5} more")
    
    return 0


if __name__ == "__main__":
    exit(main())
