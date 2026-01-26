#!/usr/bin/env python3
"""
Approve a pending card verification.

This script is used by HUMANS ONLY to approve cards that Claude has submitted.
It verifies the card against cards.cdb and adds it to verified_cards.json.

Usage:
    python scripts/approve_pending.py 12345678
    python scripts/approve_pending.py 12345678 --notes "Custom notes"
"""

import json
import argparse
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Paths
CONFIG_DIR = Path(__file__).parent.parent / "config"
PENDING_PATH = CONFIG_DIR / "pending_verifications.json"
VERIFIED_PATH = CONFIG_DIR / "verified_cards.json"
CDB_PATH = Path(__file__).parent.parent / "cards.cdb"

# Card type flags for determining monster type
TYPE_MONSTER = 0x1
TYPE_SPELL = 0x2
TYPE_TRAP = 0x4
TYPE_FUSION = 0x40
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_LINK = 0x4000000

# Attribute mapping
ATTRIBUTES = {
    0x01: "EARTH",
    0x02: "WATER",
    0x04: "FIRE",
    0x08: "WIND",
    0x10: "LIGHT",
    0x20: "DARK",
    0x40: "DIVINE"
}

# Race/Type mapping
RACES = {
    0x1: "Warrior", 0x2: "Spellcaster", 0x4: "Fairy", 0x8: "Fiend",
    0x10: "Zombie", 0x20: "Machine", 0x40: "Aqua", 0x80: "Pyro",
    0x100: "Rock", 0x200: "Winged Beast", 0x400: "Plant", 0x800: "Insect",
    0x1000: "Thunder", 0x2000: "Dragon", 0x4000: "Beast", 0x8000: "Beast-Warrior",
    0x10000: "Dinosaur", 0x20000: "Fish", 0x40000: "Sea Serpent", 0x80000: "Reptile",
    0x100000: "Psychic", 0x200000: "Divine-Beast", 0x400000: "Creator God",
    0x800000: "Wyrm", 0x1000000: "Cyberse", 0x2000000: "Illusion"
}


def load_json(path: Path) -> dict:
    """Load JSON file."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    """Save JSON file with pretty formatting."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {path}")


def get_card_from_cdb(card_id: int) -> dict:
    """Get card data from cards.cdb."""
    if not CDB_PATH.exists():
        raise FileNotFoundError(f"cards.cdb not found at {CDB_PATH}")

    conn = sqlite3.connect(CDB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT d.id, t.name, d.type, d.level, d.atk, d.def, d.attribute, d.race
        FROM datas d
        JOIN texts t ON d.id = t.id
        WHERE d.id = ?
    """, (card_id,))

    result = cursor.fetchone()
    conn.close()

    if not result:
        return None

    card_id, name, card_type, level, atk, def_, attribute, race = result

    # Build card data
    card_data = {
        "name": name,
        "verified": True,
        "verification_source": "cards.cdb",
        "verified_date": datetime.now().strftime("%Y-%m-%d")
    }

    # Determine card category
    is_monster = card_type & TYPE_MONSTER
    is_spell = card_type & TYPE_SPELL
    is_trap = card_type & TYPE_TRAP

    if is_monster:
        # Monster card
        is_xyz = card_type & TYPE_XYZ
        is_link = card_type & TYPE_LINK
        is_synchro = card_type & TYPE_SYNCHRO
        is_fusion = card_type & TYPE_FUSION
        is_extra_deck = is_xyz or is_link or is_synchro or is_fusion

        card_data["is_main_deck"] = not is_extra_deck

        # Level/Rank/Link Rating
        if is_xyz:
            card_data["rank"] = level & 0xFF
        elif is_link:
            card_data["link_rating"] = level & 0xFF
        else:
            card_data["level"] = level & 0xFF

        card_data["atk"] = atk
        if not is_link:
            card_data["def"] = def_

        # Attribute
        if attribute in ATTRIBUTES:
            card_data["attribute"] = ATTRIBUTES[attribute]

        # Race/Type
        if race in RACES:
            card_data["type"] = RACES[race]

    elif is_spell:
        card_data["card_type"] = "Spell"
        card_data["is_main_deck"] = True
    elif is_trap:
        card_data["card_type"] = "Trap"
        card_data["is_main_deck"] = True

    return card_data


def main():
    parser = argparse.ArgumentParser(
        description="Approve a pending card verification (HUMAN USE ONLY)"
    )
    parser.add_argument("card_id", type=int, help="Card passcode/ID to approve")
    parser.add_argument(
        "--notes", "-n",
        type=str,
        default="",
        help="Additional notes about this card"
    )
    args = parser.parse_args()

    # Load data
    pending = load_json(PENDING_PATH)
    verified = load_json(VERIFIED_PATH)

    if "pending" not in pending:
        print("No pending verifications found.")
        sys.exit(1)

    # Find pending entry
    pending_entry = None
    pending_idx = None
    for i, entry in enumerate(pending["pending"]):
        if entry["card_id"] == args.card_id:
            pending_entry = entry
            pending_idx = i
            break

    if pending_entry is None:
        print(f"Card {args.card_id} is not in pending verifications.")
        print("\nPending cards:")
        for entry in pending["pending"]:
            print(f"  {entry['card_id']}: {entry['proposed_name']}")
        sys.exit(1)

    # Get card data from CDB
    print(f"\nVerifying card {args.card_id} against cards.cdb...")
    card_data = get_card_from_cdb(args.card_id)

    if card_data is None:
        print(f"\nERROR: Card {args.card_id} NOT FOUND in cards.cdb!")
        print("This card cannot be approved.")
        print("\nTo reject this pending entry, run:")
        print(f"  python scripts/reject_pending.py {args.card_id} --reason 'Not in CDB'")
        sys.exit(1)

    # Show verification
    print(f"\n{'='*60}")
    print("CARD DATA FROM cards.cdb:")
    print(f"{'='*60}")
    print(f"  ID: {args.card_id}")
    print(f"  Name: {card_data['name']}")
    if 'level' in card_data:
        print(f"  Level: {card_data['level']}")
    if 'rank' in card_data:
        print(f"  Rank: {card_data['rank']}")
    if 'link_rating' in card_data:
        print(f"  Link Rating: {card_data['link_rating']}")
    if 'atk' in card_data:
        print(f"  ATK: {card_data['atk']}")
    if 'def' in card_data:
        print(f"  DEF: {card_data['def']}")
    if 'attribute' in card_data:
        print(f"  Attribute: {card_data['attribute']}")
    if 'type' in card_data:
        print(f"  Type: {card_data['type']}")
    print(f"{'='*60}")

    print(f"\nProposed name: {pending_entry['proposed_name']}")
    print(f"CDB name: {card_data['name']}")

    if pending_entry['proposed_name'].lower() != card_data['name'].lower():
        print("\nWARNING: Name mismatch!")
        confirm = input("Continue anyway? (y/N): ")
        if confirm.lower() != 'y':
            print("Aborted.")
            sys.exit(1)

    # Add notes if provided
    if args.notes:
        card_data["notes"] = args.notes
    elif pending_entry.get("reason"):
        card_data["notes"] = f"Added for: {pending_entry['reason']}"

    # Add to verified
    card_id_str = str(args.card_id)
    verified[card_id_str] = card_data
    save_json(VERIFIED_PATH, verified)

    # Remove from pending
    pending["pending"].pop(pending_idx)
    save_json(PENDING_PATH, pending)

    print(f"\n{card_data['name']} ({args.card_id}) has been APPROVED and added to verified_cards.json")


if __name__ == "__main__":
    main()
