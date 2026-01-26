#!/usr/bin/env python3
"""
Card Lookup and Deck Validation for Crystal Beast Fiendsmith

This script:
1. Looks up all cards by name in cards.cdb
2. Validates passcodes
3. Creates a validated locked_library.json for the combo pipeline
4. Reports any missing cards

Usage:
    python setup_deck.py --db /path/to/cards.cdb

The script will:
- Find all card passcodes
- Create config/cb_fiendsmith_library.json
- Create config/cb_fiendsmith_roles.json
- Report any issues
"""

import sqlite3
import json
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any


# ============================================================================
# DECK DEFINITION
# ============================================================================

# Main deck engine cards (exclude hand traps)
MAIN_DECK_ENGINE = [
    # Monsters
    ("Buio the Dawn's Light", 1, "EXTENDER"),
    ("Crystal Beast Rainbow Dragon", 1, "EXTENDER"),
    ("Crystal Beast Ruby Carbuncle", 2, "EXTENDER"),
    ("Crystal Beast Sapphire Pegasus", 3, "STARTER"),
    ("Crystal Keeper", 3, "STARTER"),
    ("Fabled Lurrie", 1, "EXTENDER"),
    ("Fiendish Rhino Warrior", 1, "EXTENDER"),
    ("Fiendsmith Engraver", 3, "STARTER"),
    ("Lacrima the Crimson Tears", 1, "EXTENDER"),
    ("Rainbow Dragon", 1, "GARNET"),
    ("Speedroid Taketomborg", 1, "EXTENDER"),
    ("Speedroid Terrortop", 3, "STARTER"),

    # Spells
    ("Awakening of the Crystal Ultimates", 1, "PAYOFF"),
    ("Crystal Bond", 3, "STARTER"),
    ("Fiendsmith's Sanct", 1, "EXTENDER"),
    ("Fiendsmith's Tract", 1, "STARTER"),
    ("Foolish Burial Goods", 3, "STARTER"),
    ("Golden Rule", 3, "EXTENDER"),
    ("Mutiny in the Sky", 3, "EXTENDER"),
    ("Rainbow Bridge", 3, "STARTER"),
    ("Rainbow Bridge of the Heart", 3, "STARTER"),
    ("Triple Tactics Thrust", 3, "STARTER"),
    ("Vaylantz World - Konig Wissen", 1, "EXTENDER"),
    ("Vaylantz World - Shinra Bansho", 1, "EXTENDER"),

    # Traps
    ("Fiendsmith Kyrie", 1, "EXTENDER"),
    ("Fiendsmith in Paradise", 1, "EXTENDER"),
    ("Rainbow Bridge of Salvation", 1, "EXTENDER"),
]

# Non-engine cards (hand traps, going-second cards)
MAIN_DECK_NON_ENGINE = [
    ("Ash Blossom & Joyous Spring", 3),
    ("Droll & Lock Bird", 2),
    ("Mulcharmy Fuwalos", 3),
    ("Called by the Grave", 1),
    ("Forbidden Droplet", 3),
]

# Extra deck pool (expanded for evaluation)
EXTRA_DECK_POOL = [
    ("A Bao A Qu, the Lightless Shadow", "PAYOFF"),
    ("Aerial Eater", "EXTENDER"),
    ("Cherubini, Ebon Angel of the Burning Abyss", "EXTENDER"),
    ("D/D/D Wave High King Caesar", "PAYOFF"),
    ("Evilswarm Exciton Knight", "PAYOFF"),
    ("Fiendsmith's Agnumday", "PAYOFF"),
    ("Fiendsmith's Desirae", "PAYOFF"),
    ("Fiendsmith's Lacrima", "EXTENDER"),
    ("Fiendsmith's Requiem", "EXTENDER"),
    ("Fiendsmith's Rextremende", "PAYOFF"),
    ("Fiendsmith's Sequence", "EXTENDER"),
    ("Melomelody the Brass Djinn", "EXTENDER"),
    ("Necroquip Princess", "EXTENDER"),
    ("S:P Little Knight", "PAYOFF"),
    ("Snake-Eye Ash", "EXTENDER"),  # May need for Snake-Eyes Dragon
    ("Snake-Eyes Flamberge Dragon", "PAYOFF"),
    ("Luce the Dusk's Dark", "PAYOFF"),
    ("Rainbow Overdragon", "PAYOFF"),
    ("Ultimate Crystal Rainbow Dragon Overdrive", "PAYOFF"),
    ("Herald of the Arc Light", "PAYOFF"),
    ("Beatrice, Lady of the Eternal", "EXTENDER"),
    ("Knightmare Phoenix", "UTILITY"),
    ("Knightmare Unicorn", "UTILITY"),
    ("Accesscode Talker", "PAYOFF"),
    ("Apollousa, Bow of the Goddess", "PAYOFF"),
    # Fiendsmith Token is generated, not in extra deck
]

# Alternative card names (some cards have multiple names in DB)
ALTERNATIVE_NAMES = {
    "Snake-Eyes Doomed Dragon": ["Snake-Eyes Flamberge Dragon"],
    "Fiendsmith's Sequence": ["Fiendsmith Sequence"],
    "D/D/D Wave High King Caesar": ["D/D/D Wave King Caesar", "DDD Wave High King Caesar"],
}


@dataclass
class CardLookupResult:
    """Result of looking up a card."""
    search_name: str
    found: bool
    passcode: Optional[int] = None
    db_name: Optional[str] = None
    error: Optional[str] = None


def connect_db(db_path: Path) -> sqlite3.Connection:
    """Connect to cards.cdb database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    return sqlite3.connect(str(db_path))


def lookup_card(conn: sqlite3.Connection, name: str) -> CardLookupResult:
    """Look up a card by name, trying various matching strategies."""
    cursor = conn.cursor()
    result = CardLookupResult(search_name=name, found=False)

    # Strategy 1: Exact match
    cursor.execute("SELECT id, name FROM texts WHERE LOWER(name) = LOWER(?)", (name,))
    row = cursor.fetchone()
    if row:
        result.found = True
        result.passcode = row[0]
        result.db_name = row[1]
        return result

    # Strategy 2: Try alternative names
    alt_names = ALTERNATIVE_NAMES.get(name, [])
    for alt in alt_names:
        cursor.execute("SELECT id, name FROM texts WHERE LOWER(name) = LOWER(?)", (alt,))
        row = cursor.fetchone()
        if row:
            result.found = True
            result.passcode = row[0]
            result.db_name = row[1]
            return result

    # Strategy 3: Contains match (for partial names)
    cursor.execute(
        "SELECT id, name FROM texts WHERE LOWER(name) LIKE LOWER(?) LIMIT 5",
        (f"%{name}%",)
    )
    rows = cursor.fetchall()
    if len(rows) == 1:
        # Unique match
        result.found = True
        result.passcode = rows[0][0]
        result.db_name = rows[0][1]
        return result
    elif len(rows) > 1:
        # Multiple matches - report them
        matches = [f"{r[0]}: {r[1]}" for r in rows]
        result.error = f"MULTIPLE_MATCHES: {'; '.join(matches)}"
        return result

    # Strategy 4: Try without special characters
    clean_name = name.replace("'", "").replace("-", " ").replace(":", "")
    cursor.execute(
        "SELECT id, name FROM texts WHERE REPLACE(REPLACE(REPLACE(LOWER(name), '''', ''), '-', ' '), ':', '') LIKE LOWER(?)",
        (f"%{clean_name}%",)
    )
    rows = cursor.fetchall()
    if len(rows) == 1:
        result.found = True
        result.passcode = rows[0][0]
        result.db_name = rows[0][1]
        return result
    elif len(rows) > 1:
        matches = [f"{r[0]}: {r[1]}" for r in rows[:5]]
        result.error = f"MULTIPLE_MATCHES_FUZZY: {'; '.join(matches)}"
        return result

    result.error = "NOT_FOUND"
    return result


def lookup_all_cards(conn: sqlite3.Connection) -> Dict[str, List[CardLookupResult]]:
    """Look up all cards in the deck definition."""
    results = {
        "main_engine": [],
        "main_non_engine": [],
        "extra_deck": [],
    }

    print("Looking up main deck engine cards...")
    for name, count, role in MAIN_DECK_ENGINE:
        result = lookup_card(conn, name)
        results["main_engine"].append((result, count, role))

    print("Looking up main deck non-engine cards...")
    for name, count in MAIN_DECK_NON_ENGINE:
        result = lookup_card(conn, name)
        results["main_non_engine"].append((result, count, "NON_ENGINE"))

    print("Looking up extra deck pool...")
    for name, role in EXTRA_DECK_POOL:
        result = lookup_card(conn, name)
        results["extra_deck"].append((result, 1, role))

    return results


def print_report(results: Dict[str, List]) -> tuple:
    """Print validation report, return (found_count, error_count)."""
    print("\n" + "=" * 70)
    print("CARD VALIDATION REPORT")
    print("=" * 70)

    total_found = 0
    total_errors = 0

    for section, cards in results.items():
        print(f"\n### {section.upper().replace('_', ' ')} ###")

        for lookup_result, count, role in cards:
            status = "+" if lookup_result.found else "x"
            count_str = f"x{count}" if count > 1 else "   "

            if lookup_result.found:
                total_found += 1
                name_match = lookup_result.db_name == lookup_result.search_name
                name_info = "" if name_match else f" -> {lookup_result.db_name}"
                print(f"  {status} {count_str} [{role:8}] {lookup_result.search_name}{name_info}")
                print(f"           Passcode: {lookup_result.passcode}")
            else:
                total_errors += 1
                print(f"  {status} {count_str} [{role:8}] {lookup_result.search_name}")
                print(f"           ERROR: {lookup_result.error}")

    return total_found, total_errors


def create_library_config(results: Dict[str, List], output_path: Path):
    """Create locked_library.json format config."""
    library = {
        "name": "Crystal Beast Fiendsmith Library",
        "description": "Engine cards for Crystal Beast Fiendsmith combo analysis",
        "main_deck": [],
        "extra_deck": [],
    }

    # Add main deck engine cards
    for lookup_result, count, role in results["main_engine"]:
        if lookup_result.found:
            for _ in range(count):
                library["main_deck"].append(lookup_result.passcode)

    # Add extra deck cards
    for lookup_result, count, role in results["extra_deck"]:
        if lookup_result.found:
            library["extra_deck"].append(lookup_result.passcode)

    with open(output_path, 'w') as f:
        json.dump(library, f, indent=2)

    print(f"\nCreated library config: {output_path}")
    print(f"  Main deck: {len(library['main_deck'])} cards")
    print(f"  Extra deck: {len(library['extra_deck'])} cards")

    return library


def create_roles_config(results: Dict[str, List], output_path: Path):
    """Create card_roles.json format config."""
    roles = {
        "description": "Card role classifications for Crystal Beast Fiendsmith deck",
        "roles": {}
    }

    for section in ["main_engine", "extra_deck"]:
        for lookup_result, count, role in results[section]:
            if lookup_result.found and role != "NON_ENGINE":
                roles["roles"][str(lookup_result.passcode)] = {
                    "name": lookup_result.db_name or lookup_result.search_name,
                    "role": role,
                    "priority": 0,
                    "tags": []
                }

    with open(output_path, 'w') as f:
        json.dump(roles, f, indent=2)

    print(f"Created roles config: {output_path}")
    print(f"  Classified cards: {len(roles['roles'])}")


def create_detailed_deck_json(results: Dict[str, List], output_path: Path):
    """Create detailed deck JSON with all info."""
    deck = {
        "deck_name": "Crystal Beast Fiendsmith",
        "main_deck_engine": [],
        "main_deck_non_engine": [],
        "extra_deck_pool": [],
        "validation_summary": {},
    }

    for lookup_result, count, role in results["main_engine"]:
        deck["main_deck_engine"].append({
            "name": lookup_result.db_name or lookup_result.search_name,
            "passcode": lookup_result.passcode,
            "count": count,
            "role": role,
            "found": lookup_result.found,
            "error": lookup_result.error,
        })

    for lookup_result, count, role in results["main_non_engine"]:
        deck["main_deck_non_engine"].append({
            "name": lookup_result.db_name or lookup_result.search_name,
            "passcode": lookup_result.passcode,
            "count": count,
            "found": lookup_result.found,
        })

    for lookup_result, count, role in results["extra_deck"]:
        deck["extra_deck_pool"].append({
            "name": lookup_result.db_name or lookup_result.search_name,
            "passcode": lookup_result.passcode,
            "role": role,
            "found": lookup_result.found,
            "error": lookup_result.error,
        })

    # Summary stats
    main_engine_count = sum(c["count"] for c in deck["main_deck_engine"] if c["found"])
    main_non_engine_count = sum(c["count"] for c in deck["main_deck_non_engine"] if c["found"])
    extra_count = sum(1 for c in deck["extra_deck_pool"] if c["found"])

    deck["validation_summary"] = {
        "main_deck_engine_cards": main_engine_count,
        "main_deck_non_engine_cards": main_non_engine_count,
        "total_main_deck": main_engine_count + main_non_engine_count,
        "extra_deck_pool_size": extra_count,
        "errors": sum(1 for section in results.values() for r, _, _ in section if not r.found),
    }

    with open(output_path, 'w') as f:
        json.dump(deck, f, indent=2)

    print(f"Created detailed deck JSON: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Set up Crystal Beast Fiendsmith deck for combo analysis")
    parser.add_argument("--db", type=Path, required=True, help="Path to cards.cdb")
    parser.add_argument("--output-dir", type=Path, default=Path("."), help="Output directory for configs")

    args = parser.parse_args()

    print(f"Connecting to database: {args.db}")
    try:
        conn = connect_db(args.db)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    # Look up all cards
    results = lookup_all_cards(conn)

    # Print report
    found, errors = print_report(results)

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Cards found: {found}")
    print(f"Cards with errors: {errors}")

    if errors > 0:
        print(f"\n  {errors} cards need manual lookup!")
        print("Please check the card names against your cards.cdb")

    # Create output files
    args.output_dir.mkdir(parents=True, exist_ok=True)

    create_library_config(results, args.output_dir / "cb_fiendsmith_library.json")
    create_roles_config(results, args.output_dir / "cb_fiendsmith_roles.json")
    create_detailed_deck_json(results, args.output_dir / "cb_fiendsmith_deck_validated.json")

    conn.close()

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("1. Review any cards marked with errors above")
    print("2. Copy cb_fiendsmith_library.json to config/locked_library.json")
    print("3. Copy cb_fiendsmith_roles.json to config/card_roles.json")
    print("4. Run small validation tests before full analysis")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
