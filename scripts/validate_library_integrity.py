#!/usr/bin/env python3
"""
Validate locked_library.json against cards.cdb.

Exit codes:
  0 - All validations passed
  1 - Validation errors found
  2 - Missing required files
"""

import json
import sqlite3
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
LIBRARY_PATH = PROJECT_ROOT / "config" / "locked_library.json"
CDB_PATH = PROJECT_ROOT / "cards.cdb"


def load_library() -> Dict:
    """Load locked_library.json."""
    if not LIBRARY_PATH.exists():
        print(f"ERROR: {LIBRARY_PATH} not found")
        sys.exit(2)
    return json.loads(LIBRARY_PATH.read_text())


def connect_cdb() -> sqlite3.Connection:
    """Connect to cards.cdb."""
    if not CDB_PATH.exists():
        print(f"ERROR: {CDB_PATH} not found")
        sys.exit(2)
    return sqlite3.connect(CDB_PATH)


def validate_card_exists(cdb: sqlite3.Connection, card_id: int) -> Tuple[bool, str]:
    """Check if card ID exists in CDB."""
    row = cdb.execute(
        "SELECT name FROM texts WHERE id = ?", (card_id,)
    ).fetchone()
    if row:
        return True, row[0]
    return False, ""


def validate_card_name(library_name: str, cdb_name: str) -> bool:
    """Check if names match (case-insensitive)."""
    return library_name.strip().lower() == cdb_name.strip().lower()


def validate_extra_deck_flag(cdb: sqlite3.Connection, card_id: int, is_extra: bool) -> bool:
    """Validate is_extra_deck flag against card type."""
    row = cdb.execute(
        "SELECT type FROM datas WHERE id = ?", (card_id,)
    ).fetchone()
    if not row:
        return False

    card_type = row[0]

    # Extra deck types (Fusion, Synchro, Xyz, Link)
    EXTRA_DECK_TYPES = {
        0x40,      # Fusion
        0x2000,    # Synchro
        0x800000,  # Xyz
        0x4000000, # Link
    }

    is_actually_extra = any(card_type & t for t in EXTRA_DECK_TYPES)
    return is_extra == is_actually_extra


def main() -> int:
    """Run all validations."""
    library = load_library()
    cdb = connect_cdb()

    errors: List[str] = []
    warnings: List[str] = []

    cards = library.get("cards", {})
    print(f"Validating {len(cards)} cards in locked_library.json...")

    for card_id_str, card_info in cards.items():
        card_id = int(card_id_str)
        library_name = card_info.get("name", "UNKNOWN")
        is_extra = card_info.get("is_extra_deck", False)

        # Check 1: Card exists in CDB
        exists, cdb_name = validate_card_exists(cdb, card_id)
        if not exists:
            errors.append(f"CRITICAL: {card_id} ({library_name}) not found in cards.cdb")
            continue

        # Check 2: Name matches
        if not validate_card_name(library_name, cdb_name):
            errors.append(
                f"NAME MISMATCH: {card_id}\n"
                f"  Library: '{library_name}'\n"
                f"  CDB:     '{cdb_name}'"
            )

        # Check 3: Extra deck flag correct
        if not validate_extra_deck_flag(cdb, card_id, is_extra):
            errors.append(
                f"EXTRA DECK FLAG MISMATCH: {card_id} ({library_name})\n"
                f"  Library says is_extra_deck={is_extra}"
            )

    cdb.close()

    # Report results
    print("\n" + "=" * 60)
    if errors:
        print(f"VALIDATION FAILED: {len(errors)} error(s)")
        print("=" * 60)
        for err in errors:
            print(f"\n{err}")
        return 1
    else:
        print("VALIDATION PASSED: All cards verified against cards.cdb")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
