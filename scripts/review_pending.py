#!/usr/bin/env python3
"""
Review all pending card verifications.

Shows all cards submitted for verification and provides commands to approve/reject.

Usage:
    python scripts/review_pending.py
    python scripts/review_pending.py --verbose
"""

import json
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime

# Paths
CONFIG_DIR = Path(__file__).parent.parent / "config"
PENDING_PATH = CONFIG_DIR / "pending_verifications.json"
VERIFIED_PATH = CONFIG_DIR / "verified_cards.json"
CDB_PATH = Path(__file__).parent.parent / "cards.cdb"


def load_json(path: Path) -> dict:
    """Load JSON file."""
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def get_cdb_name(card_id: int) -> str:
    """Get card name from CDB."""
    if not CDB_PATH.exists():
        return "(CDB not available)"

    try:
        conn = sqlite3.connect(CDB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM texts WHERE id = ?", (card_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "(NOT FOUND IN CDB)"
    except Exception as e:
        return f"(Error: {e})"


def main():
    parser = argparse.ArgumentParser(
        description="Review pending card verifications"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information"
    )
    args = parser.parse_args()

    pending = load_json(PENDING_PATH)
    verified = load_json(VERIFIED_PATH)

    pending_cards = pending.get("pending", [])

    print("="*70)
    print("PENDING CARD VERIFICATIONS")
    print("="*70)

    if not pending_cards:
        print("\nNo pending verifications.")
        print(f"\nTotal verified cards: {len(verified)}")
        return

    print(f"\n{len(pending_cards)} card(s) awaiting verification:\n")

    for i, entry in enumerate(pending_cards, 1):
        card_id = entry["card_id"]
        cdb_name = get_cdb_name(card_id)

        print(f"{i}. Card ID: {card_id}")
        print(f"   Proposed Name: {entry['proposed_name']}")
        print(f"   CDB Name: {cdb_name}")

        if entry['proposed_name'].lower() != cdb_name.lower() and "NOT FOUND" not in cdb_name:
            print(f"   >>> NAME MISMATCH <<<")

        if args.verbose:
            print(f"   Submitted: {entry['submitted_at']}")
            print(f"   Submitted by: {entry.get('submitted_by', 'unknown')}")
            if entry.get("reason"):
                print(f"   Reason: {entry['reason']}")
            print(f"   In CDB: {entry.get('exists_in_cdb', 'unknown')}")

        print(f"\n   To approve: python scripts/approve_pending.py {card_id}")
        print(f"   To reject:  python scripts/reject_pending.py {card_id} -r 'reason'")
        print()

    print("-"*70)
    print(f"Total pending: {len(pending_cards)}")
    print(f"Total verified: {len(verified)}")
    print("-"*70)
    print("\nVERIFICATION CHECKLIST:")
    print("1. Check card ID against cards.cdb")
    print("2. Verify name matches exactly")
    print("3. Approve or reject using the commands above")


if __name__ == "__main__":
    main()
