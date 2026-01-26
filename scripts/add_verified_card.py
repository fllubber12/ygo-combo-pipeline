#!/usr/bin/env python3
"""
Add a card to verified_cards.json with proper validation.

Usage:
  python scripts/add_verified_card.py 12345678 --source "https://yugipedia.com/..."

This script:
  1. Queries cards.cdb for authoritative data
  2. Displays data for human verification
  3. Requires explicit confirmation
  4. Adds to verified_cards.json with audit trail
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
VERIFIED_PATH = PROJECT_ROOT / "config" / "verified_cards.json"
CDB_PATH = PROJECT_ROOT / "cards.cdb"

# Attribute mapping
ATTRIBUTES = {
    0x01: "EARTH",
    0x02: "WATER",
    0x04: "FIRE",
    0x08: "WIND",
    0x10: "LIGHT",
    0x20: "DARK",
    0x40: "DIVINE",
}

# Race/Type mapping (common ones)
RACES = {
    0x1: "Warrior",
    0x2: "Spellcaster",
    0x4: "Fairy",
    0x8: "Fiend",
    0x10: "Zombie",
    0x20: "Machine",
    0x40: "Aqua",
    0x80: "Pyro",
    0x100: "Rock",
    0x200: "Winged Beast",
    0x400: "Plant",
    0x800: "Insect",
    0x1000: "Thunder",
    0x2000: "Dragon",
    0x4000: "Beast",
    0x8000: "Beast-Warrior",
    0x10000: "Dinosaur",
    0x20000: "Fish",
    0x40000: "Sea Serpent",
    0x80000: "Reptile",
    0x100000: "Psychic",
    0x200000: "Divine-Beast",
    0x400000: "Creator God",
    0x800000: "Wyrm",
    0x1000000: "Cyberse",
    0x2000000: "Illusion",
}


def get_card_from_cdb(card_id: int) -> dict:
    """Query card data from CDB."""
    if not CDB_PATH.exists():
        print(f"ERROR: {CDB_PATH} not found")
        return None

    cdb = sqlite3.connect(CDB_PATH)
    row = cdb.execute(
        """SELECT d.level, d.atk, d.def, d.type, d.attribute, d.race, t.name, t.desc
           FROM datas d JOIN texts t ON d.id = t.id
           WHERE d.id = ?""",
        (card_id,)
    ).fetchone()
    cdb.close()

    if not row:
        return None

    level, atk, def_, type_, attr, race, name, desc = row

    # Determine card category
    is_link = bool(type_ & 0x4000000)
    is_xyz = bool(type_ & 0x800000)
    is_synchro = bool(type_ & 0x2000)
    is_fusion = bool(type_ & 0x40)
    is_spell = bool(type_ & 0x2)
    is_trap = bool(type_ & 0x4)
    is_effect = bool(type_ & 0x20)

    card_data = {"name": name}

    if is_spell:
        card_data["card_type"] = "Spell"
        # Determine spell type
        if type_ & 0x10000:
            card_data["spell_type"] = "Field"
        elif type_ & 0x20000:
            card_data["spell_type"] = "Equip"
        elif type_ & 0x40000:
            card_data["spell_type"] = "Continuous"
        elif type_ & 0x10000000:
            card_data["spell_type"] = "Quick-Play"
        elif type_ & 0x800:
            card_data["spell_type"] = "Ritual"
        else:
            card_data["spell_type"] = "Normal"
        card_data["is_main_deck"] = True
    elif is_trap:
        card_data["card_type"] = "Trap"
        if type_ & 0x40000:
            card_data["trap_type"] = "Continuous"
        elif type_ & 0x100000:
            card_data["trap_type"] = "Counter"
        else:
            card_data["trap_type"] = "Normal"
        card_data["is_main_deck"] = True
    else:
        # Monster
        attr_name = ATTRIBUTES.get(attr, "UNKNOWN")
        race_name = RACES.get(race, "Unknown")

        card_data["attribute"] = attr_name

        # Build type string
        type_parts = [race_name]
        if is_fusion:
            type_parts.append("Fusion")
        if is_synchro:
            type_parts.append("Synchro")
        if is_xyz:
            type_parts.append("Xyz")
        if is_link:
            type_parts.append("Link")
        if is_effect:
            type_parts.append("Effect")
        card_data["type"] = "/".join(type_parts)

        if is_link:
            card_data["link_rating"] = level & 0xFF
            card_data["atk"] = atk
            card_data["is_main_deck"] = False
        elif is_xyz:
            card_data["rank"] = level & 0xFF
            card_data["atk"] = atk
            card_data["def"] = def_
            card_data["is_main_deck"] = False
        else:
            card_data["level"] = level & 0xFF
            card_data["atk"] = atk
            card_data["def"] = def_
            card_data["is_main_deck"] = not (is_fusion or is_synchro)

    return card_data


def main():
    parser = argparse.ArgumentParser(description="Add verified card from CDB")
    parser.add_argument("card_id", type=int, help="Card passcode")
    parser.add_argument("--source", default="cards.cdb", help="Verification source URL or 'cards.cdb'")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    parser.add_argument("--notes", default="", help="Additional notes")
    args = parser.parse_args()

    # Get data from CDB
    card_data = get_card_from_cdb(args.card_id)
    if not card_data:
        print(f"ERROR: Card {args.card_id} not found in cards.cdb")
        return 1

    # Display for verification
    print("\n" + "=" * 60)
    print(f"CARD DATA FROM cards.cdb")
    print("=" * 60)
    print(f"ID:   {args.card_id}")
    for key, value in card_data.items():
        print(f"{key}: {value}")
    if args.notes:
        print(f"notes: {args.notes}")
    print(f"\nSource: {args.source}")
    print("=" * 60)

    # Check if already exists
    if VERIFIED_PATH.exists():
        verified = json.loads(VERIFIED_PATH.read_text())
        if str(args.card_id) in verified.get("cards", {}):
            print(f"\nWARNING: Card {args.card_id} already exists in verified_cards.json")
            if not args.yes:
                confirm = input("Overwrite? [y/N]: ")
                if confirm.lower() != 'y':
                    print("Aborted.")
                    return 0
    else:
        verified = {"metadata": {}, "cards": {}}

    # Confirm
    if not args.yes:
        confirm = input("\nAdd this card to verified_cards.json? [y/N]: ")
        if confirm.lower() != 'y':
            print("Aborted.")
            return 0

    # Add card
    card_data["verified"] = True
    card_data["verification_source"] = args.source
    card_data["verified_date"] = datetime.now().strftime("%Y-%m-%d")
    if args.notes:
        card_data["notes"] = args.notes

    verified["cards"][str(args.card_id)] = card_data

    # Save
    VERIFIED_PATH.write_text(json.dumps(verified, indent=2) + "\n")

    print(f"\n Added {args.card_id} ({card_data['name']}) to verified_cards.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
