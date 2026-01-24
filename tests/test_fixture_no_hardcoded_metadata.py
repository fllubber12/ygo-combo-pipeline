"""
CI test to ensure fixtures only contain CIDs, no hardcoded stats.

The CDB is the single source of truth for card stats.
Fixtures should only specify CIDs - all metadata comes from CDB at runtime.
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

# Fields that should NOT appear in fixture card definitions
# These must come from CDB, not be hardcoded
FORBIDDEN_CARD_FIELDS = {
    "metadata",      # All metadata should come from CDB
    "level",         # CDB field
    "rank",          # CDB field
    "link_rating",   # CDB field
    "atk",           # CDB field
    "def",           # CDB field
    "attribute",     # CDB field
    "race",          # CDB field
    "card_type",     # CDB field
    "summon_type",   # CDB field
    "min_materials", # CDB field
    "from_extra",    # Derived from summon_type
}

# Allowed card fields
ALLOWED_CARD_FIELDS = {
    "cid",              # Required - identifies the card
    "name",             # Optional legacy support, will be ignored
    "equipped",         # Runtime state - cards equipped to this one
    "properly_summoned", # Runtime state - whether properly summoned
}


def check_no_hardcoded_metadata(obj, path: Path, location: str = ""):
    """Recursively check that no card has hardcoded metadata."""
    issues = []

    if isinstance(obj, dict):
        # Check if this looks like a card (has "cid" key)
        if "cid" in obj:
            for key in obj.keys():
                if key in FORBIDDEN_CARD_FIELDS:
                    issues.append(
                        f"{path.name}: Card at {location} has forbidden key '{key}' - "
                        f"use CDB instead (cid: {obj.get('cid')})"
                    )
                elif key not in ALLOWED_CARD_FIELDS:
                    issues.append(
                        f"{path.name}: Card at {location} has unknown key '{key}' - "
                        f"only {ALLOWED_CARD_FIELDS} are allowed (cid: {obj.get('cid')})"
                    )

            # Check equipped cards recursively
            if "equipped" in obj and obj["equipped"]:
                for i, equipped in enumerate(obj["equipped"]):
                    issues.extend(
                        check_no_hardcoded_metadata(
                            equipped, path, f"{location}.equipped[{i}]"
                        )
                    )
        else:
            # Not a card, recurse into values
            for k, v in obj.items():
                issues.extend(
                    check_no_hardcoded_metadata(v, path, f"{location}.{k}")
                )

    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            issues.extend(
                check_no_hardcoded_metadata(v, path, f"{location}[{i}]")
            )

    return issues


def get_all_fixture_paths():
    """Get all fixture JSON files."""
    return sorted(FIXTURES_DIR.rglob("*.json"))


@pytest.mark.parametrize("fixture_path", get_all_fixture_paths(), ids=lambda p: str(p.relative_to(FIXTURES_DIR)))
def test_no_hardcoded_metadata(fixture_path: Path):
    """Ensure fixture has no hardcoded card metadata."""
    # Skip schema files
    if "schema" in fixture_path.name:
        pytest.skip("Schema file")

    data = json.loads(fixture_path.read_text())
    issues = check_no_hardcoded_metadata(data, fixture_path)

    if issues:
        pytest.fail("\n".join(issues))


def test_all_fixtures_have_cids():
    """Ensure all cards in fixtures have CIDs (not just names)."""
    issues = []

    for fixture_path in get_all_fixture_paths():
        if "schema" in fixture_path.name:
            continue

        data = json.loads(fixture_path.read_text())
        card_issues = check_cards_have_cids(data, fixture_path)
        issues.extend(card_issues)

    if issues:
        pytest.fail(f"Found {len(issues)} cards without CIDs:\n" + "\n".join(issues[:20]))


def check_cards_have_cids(obj, path: Path, location: str = "") -> list:
    """Check that all cards have CIDs."""
    issues = []

    if isinstance(obj, dict):
        # Check if this looks like a card (has name but no cid)
        if "name" in obj and "cid" not in obj and "metadata" not in obj:
            # This might be a card without a CID
            if any(k in obj for k in ["level", "rank", "attribute", "race", "atk", "def"]):
                issues.append(
                    f"{path.name}: Card at {location} has name '{obj['name']}' but no CID"
                )

        for k, v in obj.items():
            issues.extend(check_cards_have_cids(v, path, f"{location}.{k}"))

    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            issues.extend(check_cards_have_cids(v, path, f"{location}[{i}]"))

    return issues
