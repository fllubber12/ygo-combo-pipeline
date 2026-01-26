#!/usr/bin/env python3
"""
Submit a card for human verification.

This script is used by Claude to propose new cards for addition to the pipeline.
Cards are added to pending_verifications.json and MUST be verified by a human
against cards.cdb before being added to verified_cards.json.

Usage:
    python scripts/submit_for_verification.py 12345678 "Card Name"
    python scripts/submit_for_verification.py 12345678 "Card Name" --reason "Needed for XYZ combo"
"""

import json
import argparse
import sys
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


def save_json(path: Path, data: dict) -> None:
    """Save JSON file with pretty formatting."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved: {path}")


def check_cdb_exists(card_id: int) -> bool:
    """Check if card exists in cards.cdb."""
    if not CDB_PATH.exists():
        print(f"Warning: cards.cdb not found at {CDB_PATH}")
        return False

    import sqlite3
    conn = sqlite3.connect(CDB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM datas WHERE id = ?", (card_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def main():
    parser = argparse.ArgumentParser(
        description="Submit a card for human verification"
    )
    parser.add_argument("card_id", type=int, help="Card passcode/ID")
    parser.add_argument("card_name", type=str, help="Card name (for reference)")
    parser.add_argument(
        "--reason", "-r",
        type=str,
        default="",
        help="Reason for adding this card"
    )
    args = parser.parse_args()

    # Load existing data
    pending = load_json(PENDING_PATH)
    verified = load_json(VERIFIED_PATH)

    if "pending" not in pending:
        pending["pending"] = []

    # Check if already verified
    card_id_str = str(args.card_id)
    if card_id_str in verified:
        print(f"Card {args.card_id} ({args.card_name}) is already verified!")
        print(f"Entry: {json.dumps(verified[card_id_str], indent=2)}")
        sys.exit(0)

    # Check if already pending
    for entry in pending["pending"]:
        if entry["card_id"] == args.card_id:
            print(f"Card {args.card_id} ({args.card_name}) is already pending verification!")
            print(f"Submitted: {entry['submitted_at']}")
            sys.exit(0)

    # Check if exists in CDB
    exists_in_cdb = check_cdb_exists(args.card_id)

    # Create pending entry
    entry = {
        "card_id": args.card_id,
        "proposed_name": args.card_name,
        "reason": args.reason,
        "submitted_at": datetime.now().isoformat(),
        "submitted_by": "claude",
        "exists_in_cdb": exists_in_cdb,
        "status": "pending_review"
    }

    pending["pending"].append(entry)
    save_json(PENDING_PATH, pending)

    print(f"\nCard submitted for verification:")
    print(f"  ID: {args.card_id}")
    print(f"  Name: {args.card_name}")
    print(f"  Exists in CDB: {exists_in_cdb}")
    if args.reason:
        print(f"  Reason: {args.reason}")

    print("\n" + "="*60)
    print("NEXT STEPS FOR HUMAN REVIEWER:")
    print("="*60)
    print("1. Verify card ID exists in cards.cdb:")
    print(f"   sqlite3 cards.cdb \"SELECT id, name FROM texts WHERE id = {args.card_id}\"")
    print("\n2. If correct, approve with:")
    print(f"   python scripts/approve_pending.py {args.card_id}")
    print("\n3. If incorrect, reject with:")
    print(f"   python scripts/reject_pending.py {args.card_id} --reason 'explanation'")
    print("="*60)


if __name__ == "__main__":
    main()
