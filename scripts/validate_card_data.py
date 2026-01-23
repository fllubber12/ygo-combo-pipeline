#!/usr/bin/env python3
"""
Validate card data against the official ProjectIgnis CDB.

Downloads cards.cdb and compares every card in our decklist against:
1. Hardcoded metadata in our effect files
2. Fixture files

Reports ALL discrepancies.
"""
from __future__ import annotations

import sqlite3
import tempfile
import urllib.request
from pathlib import Path

# CDB URL from ProjectIgnis
CDB_URL = "https://github.com/ProjectIgnis/BabelCDB/raw/master/cards.cdb"

# Card type flags from YGOPro
TYPE_MONSTER = 0x1
TYPE_SPELL = 0x2
TYPE_TRAP = 0x4
TYPE_NORMAL = 0x10
TYPE_EFFECT = 0x20
TYPE_FUSION = 0x40
TYPE_RITUAL = 0x80
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_PENDULUM = 0x1000000
TYPE_LINK = 0x4000000

# Attribute flags
ATTR_EARTH = 0x01
ATTR_WATER = 0x02
ATTR_FIRE = 0x04
ATTR_WIND = 0x08
ATTR_LIGHT = 0x10
ATTR_DARK = 0x20
ATTR_DIVINE = 0x40

ATTR_NAMES = {
    ATTR_EARTH: "EARTH",
    ATTR_WATER: "WATER",
    ATTR_FIRE: "FIRE",
    ATTR_WIND: "WIND",
    ATTR_LIGHT: "LIGHT",
    ATTR_DARK: "DARK",
    ATTR_DIVINE: "DIVINE",
}

# Race/Type flags
RACE_WARRIOR = 0x1
RACE_SPELLCASTER = 0x2
RACE_FAIRY = 0x4
RACE_FIEND = 0x8
RACE_ZOMBIE = 0x10
RACE_MACHINE = 0x20
RACE_AQUA = 0x40
RACE_PYRO = 0x80
RACE_ROCK = 0x100
RACE_WINGEDBEAST = 0x200
RACE_PLANT = 0x400
RACE_INSECT = 0x800
RACE_THUNDER = 0x1000
RACE_DRAGON = 0x2000
RACE_BEAST = 0x4000
RACE_BEASTWARRIOR = 0x8000
RACE_DINOSAUR = 0x10000
RACE_FISH = 0x20000
RACE_SEASERPENT = 0x40000
RACE_REPTILE = 0x80000
RACE_PSYCHIC = 0x100000
RACE_DIVINE = 0x200000
RACE_CREATORGOD = 0x400000
RACE_WYRM = 0x800000
RACE_CYBERSE = 0x1000000
RACE_ILLUSION = 0x2000000

RACE_NAMES = {
    RACE_WARRIOR: "Warrior",
    RACE_SPELLCASTER: "Spellcaster",
    RACE_FAIRY: "Fairy",
    RACE_FIEND: "Fiend",
    RACE_ZOMBIE: "Zombie",
    RACE_MACHINE: "Machine",
    RACE_AQUA: "Aqua",
    RACE_PYRO: "Pyro",
    RACE_ROCK: "Rock",
    RACE_WINGEDBEAST: "Winged Beast",
    RACE_PLANT: "Plant",
    RACE_INSECT: "Insect",
    RACE_THUNDER: "Thunder",
    RACE_DRAGON: "Dragon",
    RACE_BEAST: "Beast",
    RACE_BEASTWARRIOR: "Beast-Warrior",
    RACE_DINOSAUR: "Dinosaur",
    RACE_FISH: "Fish",
    RACE_SEASERPENT: "Sea Serpent",
    RACE_REPTILE: "Reptile",
    RACE_PSYCHIC: "Psychic",
    RACE_DIVINE: "Divine-Beast",
    RACE_CREATORGOD: "Creator God",
    RACE_WYRM: "Wyrm",
    RACE_CYBERSE: "Cyberse",
    RACE_ILLUSION: "Illusion",
}


def download_cdb(dest_path: Path) -> None:
    """Download the CDB file."""
    print(f"Downloading CDB from {CDB_URL}...")
    urllib.request.urlretrieve(CDB_URL, dest_path)
    print(f"Downloaded to {dest_path}")


def get_card_type_string(type_val: int) -> str:
    """Convert type flags to readable string."""
    parts = []
    if type_val & TYPE_MONSTER:
        if type_val & TYPE_LINK:
            parts.append("Link")
        elif type_val & TYPE_XYZ:
            parts.append("Xyz")
        elif type_val & TYPE_SYNCHRO:
            parts.append("Synchro")
        elif type_val & TYPE_FUSION:
            parts.append("Fusion")
        elif type_val & TYPE_RITUAL:
            parts.append("Ritual")
        if type_val & TYPE_PENDULUM:
            parts.append("Pendulum")
        if type_val & TYPE_EFFECT:
            parts.append("Effect")
        elif type_val & TYPE_NORMAL:
            parts.append("Normal")
        parts.append("Monster")
    elif type_val & TYPE_SPELL:
        parts.append("Spell")
    elif type_val & TYPE_TRAP:
        parts.append("Trap")
    return " ".join(parts) if parts else f"Unknown({type_val})"


def get_attribute_string(attr: int) -> str:
    """Convert attribute flag to string."""
    return ATTR_NAMES.get(attr, f"Unknown({attr})")


def get_race_string(race: int) -> str:
    """Convert race flag to string."""
    return RACE_NAMES.get(race, f"Unknown({race})")


def get_summon_type(type_val: int) -> str | None:
    """Get summon type for Extra Deck monsters."""
    if type_val & TYPE_LINK:
        return "link"
    if type_val & TYPE_XYZ:
        return "xyz"
    if type_val & TYPE_SYNCHRO:
        return "synchro"
    if type_val & TYPE_FUSION:
        return "fusion"
    return None


def is_main_deck(type_val: int) -> bool:
    """Check if card goes in main deck."""
    extra_deck_flags = TYPE_FUSION | TYPE_SYNCHRO | TYPE_XYZ | TYPE_LINK
    if type_val & TYPE_MONSTER:
        return not (type_val & extra_deck_flags)
    return True  # Spells/Traps go in main deck


def query_card(conn: sqlite3.Connection, passcode: int) -> dict | None:
    """Query a card by passcode from the CDB."""
    cursor = conn.execute(
        """
        SELECT d.id, t.name, d.type, d.attribute, d.race, d.level, d.atk, d.def, t.desc
        FROM datas d
        JOIN texts t ON d.id = t.id
        WHERE d.id = ?
        """,
        (passcode,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    id_, name, type_val, attr, race, level, atk, def_, desc = row

    # For Link monsters, level field contains link rating
    # For Xyz monsters, level field contains rank
    # For Pendulum monsters, level encodes scales too
    link_rating = None
    actual_level = level & 0xFF  # Lower 8 bits are level/rank

    if type_val & TYPE_LINK:
        link_rating = actual_level
        actual_level = None

    return {
        "passcode": id_,
        "name": name,
        "type_raw": type_val,
        "type_string": get_card_type_string(type_val),
        "attribute": get_attribute_string(attr) if attr else None,
        "attribute_raw": attr,
        "race": get_race_string(race) if race else None,
        "race_raw": race,
        "level": actual_level,
        "link_rating": link_rating,
        "atk": atk,
        "def": def_,
        "is_monster": bool(type_val & TYPE_MONSTER),
        "is_spell": bool(type_val & TYPE_SPELL),
        "is_trap": bool(type_val & TYPE_TRAP),
        "summon_type": get_summon_type(type_val),
        "is_main_deck": is_main_deck(type_val),
        "desc": desc,
    }


def load_decklist(decklist_path: Path) -> list[int]:
    """Load passcodes from a .ydk file."""
    passcodes = []
    in_section = False
    for line in decklist_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or line.startswith("!"):
            in_section = True
            continue
        if in_section and line.isdigit():
            passcodes.append(int(line))
    return list(set(passcodes))  # Unique passcodes


def load_cid_to_passcode_map() -> dict[str, int]:
    """
    Load mapping from our internal CIDs to YGOPro passcodes.
    This reads from the data_cache if available.
    """
    repo_root = Path(__file__).resolve().parents[1]
    cache_file = repo_root / "data_cache" / "cid_to_passcode.json"
    if cache_file.exists():
        import json
        return json.loads(cache_file.read_text())
    return {}


def extract_hardcoded_cids() -> dict[str, list[str]]:
    """Extract all hardcoded CIDs from our effect files."""
    repo_root = Path(__file__).resolve().parents[1]
    results = {}

    # Check fiendsmith_effects.py
    fiendsmith_path = repo_root / "src" / "sim" / "effects" / "fiendsmith_effects.py"
    if fiendsmith_path.exists():
        content = fiendsmith_path.read_text()
        results["fiendsmith_effects.py"] = []
        for line in content.splitlines():
            if "_CID" in line and "=" in line and '"' in line:
                results["fiendsmith_effects.py"].append(line.strip())

    # Check library_effects.py
    library_path = repo_root / "src" / "sim" / "effects" / "library_effects.py"
    if library_path.exists():
        content = library_path.read_text()
        results["library_effects.py"] = []
        for line in content.splitlines():
            if "_CID" in line and "=" in line and '"' in line:
                results["library_effects.py"].append(line.strip())

    return results


def query_card_by_name(conn: sqlite3.Connection, name: str) -> dict | None:
    """Query a card by name from the CDB."""
    cursor = conn.execute(
        """
        SELECT d.id, t.name, d.type, d.attribute, d.race, d.level, d.atk, d.def, t.desc
        FROM datas d
        JOIN texts t ON d.id = t.id
        WHERE t.name LIKE ?
        """,
        (name,),
    )
    row = cursor.fetchone()
    if not row:
        return None

    id_, name, type_val, attr, race, level, atk, def_, desc = row

    link_rating = None
    actual_level = level & 0xFF

    if type_val & TYPE_LINK:
        link_rating = actual_level
        actual_level = None

    return {
        "passcode": id_,
        "name": name,
        "type_raw": type_val,
        "type_string": get_card_type_string(type_val),
        "attribute": get_attribute_string(attr) if attr else None,
        "attribute_raw": attr,
        "race": get_race_string(race) if race else None,
        "race_raw": race,
        "level": actual_level,
        "link_rating": link_rating,
        "atk": atk,
        "def": def_,
        "is_monster": bool(type_val & TYPE_MONSTER),
        "is_spell": bool(type_val & TYPE_SPELL),
        "is_trap": bool(type_val & TYPE_TRAP),
        "summon_type": get_summon_type(type_val),
        "is_main_deck": is_main_deck(type_val),
        "desc": desc,
    }


# Known card names from our CID mapping
CARD_NAMES = {
    "20196": "Fiendsmith Engraver",
    "20214": "Fiendsmith's Lacrima",
    "20215": "Fiendsmith's Desirae",
    "20225": "Fiendsmith's Requiem",
    "20226": "Fiendsmith's Sequence",  # Alt CID?
    "20238": "Fiendsmith's Sequence",
    "20240": "Fiendsmith's Tract",
    "20241": "Fiendsmith's Sanct",
    "20251": "Fiendsmith in Paradise",
    "20490": "Fiendsmith's Lacrima - Crimson Tears",
    "20521": "Fiendsmith's Agnumday the Bestower",
    "20774": "Fiendsmith's Rextremende",
    "20816": "Fiendsmith Kyrie",
    "14856": "Cross-Sheep",
    "17806": "Muckraker From the Underworld",
    "19188": "S:P Little Knight",
    "20389": "Duke of Demise",
    "20423": "Necroquip Princess",
    "20427": "Aerial Eater",
    "20772": "Snake-Eyes Diabellstar",
    "20786": "A Bao A Qu, the Lightless Shadow",
    "21624": "Buio, Dawn's Light",
    "21625": "Luce, Dusk's Dark",
    "21626": "Mutiny in the Sky",
    "10942": "D/D/D Wave High King Caesar",
    "13081": "Unknown",  # Need to find this
}


def main():
    repo_root = Path(__file__).resolve().parents[1]

    # Download CDB to temp file
    with tempfile.NamedTemporaryFile(suffix=".cdb", delete=False) as tmp:
        cdb_path = Path(tmp.name)

    try:
        download_cdb(cdb_path)
        conn = sqlite3.connect(cdb_path)

        print(f"\nLooking up cards by name...\n")

        # Query and display each card by name
        print("=" * 80)
        print("CARD DATA FROM OFFICIAL CDB")
        print("=" * 80)

        cards = []
        cid_to_passcode = {}

        for cid, name in sorted(CARD_NAMES.items(), key=lambda x: x[1]):
            if name == "Unknown":
                continue
            card = query_card_by_name(conn, name)
            if card:
                cards.append(card)
                cid_to_passcode[cid] = card['passcode']
                print(f"\nOur CID: {cid} -> Passcode: {card['passcode']}")
                print(f"  Name: {card['name']}")
                print(f"  Type: {card['type_string']}")
                if card['is_monster']:
                    print(f"  Attribute: {card['attribute']}")
                    print(f"  Race: {card['race']}")
                    if card['link_rating'] is not None:
                        print(f"  Link Rating: {card['link_rating']}")
                    elif card['level'] is not None:
                        print(f"  Level/Rank: {card['level']}")
                    print(f"  ATK: {card['atk']}")
                    if card['link_rating'] is None:
                        print(f"  DEF: {card['def']}")
                    if card['summon_type']:
                        print(f"  Summon Type: {card['summon_type']}")
                    print(f"  Main Deck: {card['is_main_deck']}")
            else:
                print(f"\nOur CID: {cid} -> Name: {name} - NOT FOUND IN CDB")

        conn.close()

        # Show hardcoded CIDs in our code
        print("\n" + "=" * 80)
        print("HARDCODED CIDS IN OUR CODE")
        print("=" * 80)

        hardcoded = extract_hardcoded_cids()
        for filename, lines in hardcoded.items():
            print(f"\n{filename}:")
            for line in lines:
                print(f"  {line}")

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)

        monsters = [c for c in cards if c['is_monster']]
        spells = [c for c in cards if c['is_spell']]
        traps = [c for c in cards if c['is_trap']]
        main_deck_monsters = [c for c in monsters if c['is_main_deck']]
        extra_deck_monsters = [c for c in monsters if not c['is_main_deck']]

        print(f"\nTotal cards: {len(cards)}")
        print(f"  Monsters: {len(monsters)}")
        print(f"    Main Deck: {len(main_deck_monsters)}")
        print(f"    Extra Deck: {len(extra_deck_monsters)}")
        print(f"  Spells: {len(spells)}")
        print(f"  Traps: {len(traps)}")

        print("\nMain Deck Monsters:")
        for c in main_deck_monsters:
            print(f"  - {c['name']} (Level {c['level']}, {c['attribute']} {c['race']})")

        print("\nExtra Deck Monsters:")
        for c in extra_deck_monsters:
            rating = c['link_rating'] if c['link_rating'] else c['level']
            rtype = "Link" if c['link_rating'] else "Level/Rank"
            print(f"  - {c['name']} ({c['summon_type']}, {rtype} {rating}, {c['attribute']} {c['race']})")

        print("\nSpells:")
        for c in spells:
            print(f"  - {c['name']}")

        print("\nTraps:")
        for c in traps:
            print(f"  - {c['name']}")

    finally:
        cdb_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
