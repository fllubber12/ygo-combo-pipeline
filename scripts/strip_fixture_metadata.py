#!/usr/bin/env python3
"""
Remove all hardcoded metadata from fixtures.

Only CIDs should remain - all card stats come from CDB at runtime.
This enforces the single-source-of-truth principle.
"""

import json
from pathlib import Path


def strip_card(card: dict | None) -> dict | None:
    """Keep only cid and structural fields (equipped, properly_summoned)."""
    if card is None:
        return None

    if not isinstance(card, dict):
        return card

    # CID is required
    cid = card.get("cid")
    if not cid:
        print(f"  WARNING: Card missing CID: {card}")
        return card

    stripped = {"cid": cid}

    # Keep equipped cards (recursive)
    if "equipped" in card and card["equipped"]:
        stripped["equipped"] = [strip_card(c) for c in card["equipped"]]

    # Keep properly_summoned (runtime state, not card data)
    if card.get("properly_summoned"):
        stripped["properly_summoned"] = True

    return stripped


def strip_zone_list(cards: list | None) -> list:
    """Strip metadata from a list of cards."""
    if not cards:
        return []
    return [strip_card(c) for c in cards]


def strip_field_zone(slots: list | None) -> list:
    """Strip metadata from field zone slots (can contain None)."""
    if not slots:
        return []
    return [strip_card(c) if c is not None else None for c in slots]


def strip_fixture(fixture_path: Path) -> tuple[int, int]:
    """
    Strip all hardcoded metadata from a fixture file.
    Returns (cards_processed, fields_removed).
    """
    data = json.loads(fixture_path.read_text())

    cards_processed = 0
    fields_removed = 0

    zones = data.get("state", {}).get("zones", {})

    # Strip list zones
    for zone in ["hand", "deck", "gy", "banished", "extra"]:
        if zone in zones and zones[zone]:
            original = zones[zone]
            zones[zone] = strip_zone_list(original)
            cards_processed += len([c for c in original if c])
            for orig, stripped in zip(original, zones[zone]):
                if orig and stripped:
                    fields_removed += len(orig) - len(stripped)

    # Strip field zones
    if "field_zones" in zones:
        for fz in ["mz", "emz", "stz", "fz"]:
            if fz in zones["field_zones"]:
                original = zones["field_zones"][fz]
                zones["field_zones"][fz] = strip_field_zone(original)
                cards_processed += len([c for c in original if c])
                for orig, stripped in zip(original, zones["field_zones"][fz]):
                    if orig and stripped:
                        fields_removed += len(orig) - len(stripped)

    # Write back with consistent formatting
    fixture_path.write_text(json.dumps(data, indent=2) + "\n")

    return cards_processed, fields_removed


def main():
    repo_root = Path(__file__).parent.parent
    fixtures_dir = repo_root / "tests" / "fixtures"

    print("=" * 70)
    print("STRIPPING HARDCODED METADATA FROM FIXTURES")
    print("=" * 70)
    print("\nPrinciple: CDB is the ONLY source for card stats.")
    print("Fixtures should only contain CIDs.\n")

    total_cards = 0
    total_fields = 0
    files_processed = 0

    for fixture_path in sorted(fixtures_dir.rglob("*.json")):
        # Skip non-fixture files
        if "schema" in fixture_path.name:
            continue

        cards, fields = strip_fixture(fixture_path)
        if fields > 0:
            print(f"  Stripped: {fixture_path.relative_to(repo_root)}")
            print(f"    Cards: {cards}, Fields removed: {fields}")
        else:
            print(f"  Clean: {fixture_path.relative_to(repo_root)}")

        total_cards += cards
        total_fields += fields
        files_processed += 1

    print("\n" + "=" * 70)
    print(f"SUMMARY")
    print("=" * 70)
    print(f"Files processed: {files_processed}")
    print(f"Total cards: {total_cards}")
    print(f"Total fields removed: {total_fields}")

    if total_fields > 0:
        print("\nMetadata has been stripped. All card stats now come from CDB.")
    else:
        print("\nAll fixtures were already clean.")


if __name__ == "__main__":
    main()
