#!/usr/bin/env python3
"""
Reject a pending card verification.

This script is used by HUMANS ONLY to reject cards that Claude has submitted.
Rejected cards are removed from the pending list.

Usage:
    python scripts/reject_pending.py 12345678
    python scripts/reject_pending.py 12345678 --reason "Card ID is incorrect"
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

# Paths
CONFIG_DIR = Path(__file__).parent.parent / "config"
PENDING_PATH = CONFIG_DIR / "pending_verifications.json"
REJECTIONS_LOG = CONFIG_DIR / "rejection_log.json"


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


def main():
    parser = argparse.ArgumentParser(
        description="Reject a pending card verification (HUMAN USE ONLY)"
    )
    parser.add_argument("card_id", type=int, help="Card passcode/ID to reject")
    parser.add_argument(
        "--reason", "-r",
        type=str,
        default="No reason provided",
        help="Reason for rejection"
    )
    args = parser.parse_args()

    # Load pending
    pending = load_json(PENDING_PATH)

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

    # Log rejection
    rejections = load_json(REJECTIONS_LOG)
    if "rejections" not in rejections:
        rejections["rejections"] = []

    rejection_record = {
        "card_id": args.card_id,
        "proposed_name": pending_entry["proposed_name"],
        "reason": args.reason,
        "rejected_at": datetime.now().isoformat(),
        "original_submission": pending_entry
    }
    rejections["rejections"].append(rejection_record)
    save_json(REJECTIONS_LOG, rejections)

    # Remove from pending
    pending["pending"].pop(pending_idx)
    save_json(PENDING_PATH, pending)

    print(f"\nCard {args.card_id} ({pending_entry['proposed_name']}) has been REJECTED.")
    print(f"Reason: {args.reason}")
    print("\nRejection logged to config/rejection_log.json")


if __name__ == "__main__":
    main()
