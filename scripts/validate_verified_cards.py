#!/usr/bin/env python3
"""
Validate verified_cards.json against cards.cdb.

Checks:
  - INTEGRITY: Lock checksum matches (detects any modification)
  - All card IDs exist in CDB
  - Levels/Ranks/Link Ratings match
  - ATK/DEF values match
  - Names match

Exit codes:
  0 - All validations passed
  1 - Validation errors found
  2 - Missing required files
  3 - Integrity checksum mismatch (CRITICAL)
"""

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).parent.parent
VERIFIED_PATH = PROJECT_ROOT / "config" / "verified_cards.json"
CDB_PATH = PROJECT_ROOT / "cards.cdb"


def canonical_json(obj) -> str:
    """Convert object to canonical JSON string for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def compute_cards_checksum(cards: dict) -> str:
    """Compute SHA256 checksum of cards dictionary."""
    canonical = canonical_json(cards)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def verify_integrity(data: Dict) -> tuple[bool, str]:
    """Verify the integrity checksum of the card data.

    Returns:
        (is_valid, message)
    """
    metadata = data.get("metadata", {})
    stored_checksum = metadata.get("lock_checksum")

    if not stored_checksum:
        return True, "No lock checksum found (file not locked)"

    cards = data.get("cards", {})
    computed_checksum = compute_cards_checksum(cards)

    if computed_checksum != stored_checksum:
        return False, (
            f"INTEGRITY VIOLATION DETECTED!\n"
            f"  Stored checksum:   {stored_checksum[:32]}...\n"
            f"  Computed checksum: {computed_checksum[:32]}...\n"
            f"\n"
            f"  Card data has been modified without proper re-verification.\n"
            f"  Run 'python scripts/generate_lock_checksum.py' after audit to re-lock."
        )

    return True, f"Integrity verified (checksum: {stored_checksum[:16]}...)"


def extract_level(cdb_level: int, cdb_type: int) -> int:
    """Extract actual level/rank/link from CDB encoding."""
    # Link monsters: link rating in level field
    if cdb_type & 0x4000000:  # Link
        return cdb_level & 0xFF
    # Xyz monsters: rank in level field
    if cdb_type & 0x800000:  # Xyz
        return cdb_level & 0xFF
    # Regular monsters: level in level field
    return cdb_level & 0xFF


def validate_card(card_id: int, verified: Dict, cdb: sqlite3.Connection) -> List[str]:
    """Validate a single card against CDB."""
    errors = []

    # Query CDB
    row = cdb.execute(
        """SELECT d.level, d.atk, d.def, d.type, t.name
           FROM datas d JOIN texts t ON d.id = t.id
           WHERE d.id = ?""",
        (card_id,)
    ).fetchone()

    if not row:
        return [f"Card {card_id} ({verified.get('name', 'UNKNOWN')}) not found in CDB"]

    cdb_level, cdb_atk, cdb_def, cdb_type, cdb_name = row
    actual_level = extract_level(cdb_level, cdb_type)

    # Check name (case-insensitive)
    if verified.get("name", "").lower() != cdb_name.lower():
        errors.append(
            f"NAME MISMATCH: {card_id}\n"
            f"  Verified: '{verified.get('name')}'\n"
            f"  CDB:      '{cdb_name}'"
        )

    # Check level/rank/link_rating
    verified_level = (
        verified.get("level") or
        verified.get("rank") or
        verified.get("link_rating")
    )
    if verified_level and verified_level != actual_level:
        errors.append(
            f"LEVEL MISMATCH: {card_id} ({verified.get('name')})\n"
            f"  Verified: {verified_level}\n"
            f"  CDB:      {actual_level}"
        )

    # Check ATK (only for monsters with ATK field)
    if "atk" in verified and verified["atk"] != cdb_atk:
        errors.append(
            f"ATK MISMATCH: {card_id} ({verified.get('name')})\n"
            f"  Verified: {verified['atk']}\n"
            f"  CDB:      {cdb_atk}"
        )

    # Check DEF (skip for Link monsters)
    if "def" in verified and not (cdb_type & 0x4000000):
        if verified["def"] != cdb_def:
            errors.append(
                f"DEF MISMATCH: {card_id} ({verified.get('name')})\n"
                f"  Verified: {verified['def']}\n"
                f"  CDB:      {cdb_def}"
            )

    return errors


def main() -> int:
    """Run validation."""
    if not VERIFIED_PATH.exists():
        print(f"ERROR: {VERIFIED_PATH} not found")
        return 2
    if not CDB_PATH.exists():
        print(f"ERROR: {CDB_PATH} not found")
        return 2

    verified_data = json.loads(VERIFIED_PATH.read_text())

    # CRITICAL: Check integrity checksum FIRST
    integrity_ok, integrity_msg = verify_integrity(verified_data)
    if not integrity_ok:
        print("\n" + "=" * 60)
        print("CRITICAL: INTEGRITY CHECK FAILED")
        print("=" * 60)
        print(f"\n{integrity_msg}")
        print("\nCommit REJECTED. Card data has been tampered with.")
        return 3
    else:
        print(f"Integrity check: {integrity_msg}")

    cards = verified_data.get("cards", {})
    cdb = sqlite3.connect(CDB_PATH)

    all_errors = []

    print(f"Validating {len(cards)} verified cards...")

    for card_id_str, card_info in cards.items():
        errors = validate_card(int(card_id_str), card_info, cdb)
        all_errors.extend(errors)

    cdb.close()

    print("\n" + "=" * 60)
    if all_errors:
        print(f"VALIDATION FAILED: {len(all_errors)} error(s)")
        print("=" * 60)
        for err in all_errors:
            print(f"\n{err}")
        return 1
    else:
        print("VALIDATION PASSED: All verified cards match CDB")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
