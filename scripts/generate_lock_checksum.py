#!/usr/bin/env python3
"""
Generate cryptographic checksum for verified_cards.json.

This script:
1. Reads verified_cards.json
2. Computes SHA256 hash of the "cards" section (canonical JSON)
3. Updates the metadata with lock information
4. Writes back the file with integrity checksum

The checksum ensures any modification to card data is detected.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
VERIFIED_PATH = PROJECT_ROOT / "config" / "verified_cards.json"


def canonical_json(obj) -> str:
    """Convert object to canonical JSON string for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))


def compute_cards_checksum(cards: dict) -> str:
    """Compute SHA256 checksum of cards dictionary."""
    canonical = canonical_json(cards)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def main():
    if not VERIFIED_PATH.exists():
        print(f"ERROR: {VERIFIED_PATH} not found")
        return 1

    # Load current data
    data = json.loads(VERIFIED_PATH.read_text())
    cards = data.get("cards", {})

    if not cards:
        print("ERROR: No cards found in verified_cards.json")
        return 1

    # Compute checksum
    checksum = compute_cards_checksum(cards)
    now = datetime.now(timezone.utc).isoformat()

    # Update metadata with lock info
    data["metadata"] = {
        "source": "cards.cdb (authoritative) + manual audit",
        "audit_date": "2026-01-26",
        "verified_by": "Triple-pass audit against YGOProDeck API",
        "lock_status": "LOCKED",
        "lock_date": now,
        "lock_checksum": checksum,
        "card_count": len(cards),
        "audit_passes": 3,
        "notes": "DO NOT MODIFY without explicit user approval and re-verification"
    }

    # Write back with nice formatting
    VERIFIED_PATH.write_text(json.dumps(data, indent=2) + "\n")

    print(f"Lock checksum generated successfully")
    print(f"  Cards: {len(cards)}")
    print(f"  Checksum: {checksum[:16]}...{checksum[-16:]}")
    print(f"  Lock date: {now}")
    print(f"\nFile updated: {VERIFIED_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
