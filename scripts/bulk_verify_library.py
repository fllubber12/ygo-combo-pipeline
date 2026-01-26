#!/usr/bin/env python3
"""
Bulk verify all cards from locked_library.json using cards.cdb data.

This script:
1. Reads all card IDs from locked_library.json
2. Queries cards.cdb for each card's authoritative data
3. Adds/updates entries in verified_cards.json
4. Preserves existing notes and metadata
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
LIBRARY_PATH = PROJECT_ROOT / "config" / "locked_library.json"
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

# Race/Type mapping
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


def get_card_from_cdb(cdb: sqlite3.Connection, card_id: int) -> dict:
    """Query card data from CDB."""
    row = cdb.execute(
        """SELECT d.level, d.atk, d.def, d.type, d.attribute, d.race, t.name
           FROM datas d JOIN texts t ON d.id = t.id
           WHERE d.id = ?""",
        (card_id,)
    ).fetchone()

    if not row:
        return None

    level, atk, def_, type_, attr, race, name = row

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
    # Load existing data
    library = json.loads(LIBRARY_PATH.read_text())

    if VERIFIED_PATH.exists():
        verified = json.loads(VERIFIED_PATH.read_text())
    else:
        verified = {
            "metadata": {
                "source": "cards.cdb (authoritative)",
                "audit_date": datetime.now().strftime("%Y-%m-%d"),
                "verified_by": "bulk_verify_library.py script"
            },
            "cards": {}
        }

    cdb = sqlite3.connect(CDB_PATH)

    library_cards = library.get("cards", {})
    added = 0
    updated = 0
    failed = []

    print(f"Processing {len(library_cards)} cards from locked_library.json...")

    for card_id_str, lib_info in library_cards.items():
        card_id = int(card_id_str)
        card_data = get_card_from_cdb(cdb, card_id)

        if not card_data:
            failed.append((card_id, lib_info.get("name", "UNKNOWN")))
            continue

        # Preserve existing notes if card already verified
        existing = verified.get("cards", {}).get(card_id_str, {})
        if "notes" in existing:
            card_data["notes"] = existing["notes"]

        # Add verification metadata
        card_data["verified"] = True
        card_data["verification_source"] = "cards.cdb"
        card_data["verified_date"] = datetime.now().strftime("%Y-%m-%d")

        if card_id_str in verified.get("cards", {}):
            updated += 1
        else:
            added += 1

        verified["cards"][card_id_str] = card_data

    cdb.close()

    # Update metadata
    verified["metadata"] = {
        "source": "cards.cdb (authoritative)",
        "audit_date": datetime.now().strftime("%Y-%m-%d"),
        "verified_by": "bulk_verify_library.py script",
        "notes": "All card data from cards.cdb - the authoritative source"
    }

    # Sort cards by ID for consistency
    verified["cards"] = dict(sorted(verified["cards"].items(), key=lambda x: int(x[0])))

    # Save
    VERIFIED_PATH.write_text(json.dumps(verified, indent=2) + "\n")

    print(f"\nResults:")
    print(f"  Added: {added} new cards")
    print(f"  Updated: {updated} existing cards")
    print(f"  Failed: {len(failed)} cards")

    if failed:
        print("\nFailed cards (not in CDB):")
        for card_id, name in failed:
            print(f"  {card_id}: {name}")

    print(f"\nTotal verified cards: {len(verified['cards'])}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
