#!/usr/bin/env python3
"""
Data Integrity Tests for Anti-Hallucination Defense

This test module validates that all card data in the pipeline is consistent
and verified against the authoritative cards.cdb database.

Run with: pytest tests/unit/test_data_integrity.py -v
"""

import json
import sqlite3
import pytest
from pathlib import Path
from typing import Set

# Paths
PROJECT_ROOT = Path(__file__).parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
CDB_PATH = PROJECT_ROOT / "cards.cdb"

VERIFIED_CARDS_PATH = CONFIG_DIR / "verified_cards.json"
LOCKED_LIBRARY_PATH = CONFIG_DIR / "locked_library.json"
CONSTANTS_PATH = CONFIG_DIR / "constants.json"
EVALUATION_CONFIG_PATH = CONFIG_DIR / "evaluation_config.json"
CARD_ROLES_PATH = CONFIG_DIR / "card_roles.json"
PENDING_PATH = CONFIG_DIR / "pending_verifications.json"


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def cdb_connection():
    """Provide database connection to cards.cdb."""
    if not CDB_PATH.exists():
        pytest.skip(f"cards.cdb not found at {CDB_PATH}")
    conn = sqlite3.connect(CDB_PATH)
    yield conn
    conn.close()


@pytest.fixture
def verified_cards() -> dict:
    """Load verified_cards.json (returns the 'cards' section)."""
    if not VERIFIED_CARDS_PATH.exists():
        pytest.fail(f"verified_cards.json not found at {VERIFIED_CARDS_PATH}")
    with open(VERIFIED_CARDS_PATH) as f:
        data = json.load(f)
    # Return the cards section (file has metadata + cards structure)
    return data.get("cards", data)


@pytest.fixture
def locked_library() -> dict:
    """Load locked_library.json."""
    if not LOCKED_LIBRARY_PATH.exists():
        pytest.fail(f"locked_library.json not found at {LOCKED_LIBRARY_PATH}")
    with open(LOCKED_LIBRARY_PATH) as f:
        return json.load(f)


@pytest.fixture
def constants() -> dict:
    """Load constants.json."""
    if not CONSTANTS_PATH.exists():
        pytest.fail(f"constants.json not found at {CONSTANTS_PATH}")
    with open(CONSTANTS_PATH) as f:
        return json.load(f)


@pytest.fixture
def evaluation_config() -> dict:
    """Load evaluation_config.json."""
    if not EVALUATION_CONFIG_PATH.exists():
        pytest.fail(f"evaluation_config.json not found at {EVALUATION_CONFIG_PATH}")
    with open(EVALUATION_CONFIG_PATH) as f:
        return json.load(f)


@pytest.fixture
def card_roles() -> dict:
    """Load card_roles.json."""
    if not CARD_ROLES_PATH.exists():
        pytest.skip(f"card_roles.json not found at {CARD_ROLES_PATH}")
    with open(CARD_ROLES_PATH) as f:
        return json.load(f)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_cdb_card(conn: sqlite3.Connection, card_id: int) -> dict:
    """Get card data from cards.cdb."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, t.name, d.type, d.level, d.atk, d.def
        FROM datas d
        JOIN texts t ON d.id = t.id
        WHERE d.id = ?
    """, (card_id,))
    result = cursor.fetchone()
    if not result:
        return None
    return {
        "id": result[0],
        "name": result[1],
        "type": result[2],
        "level": result[3] & 0xFF,
        "atk": result[4],
        "def": result[5]
    }


def extract_card_ids_from_constants(constants: dict) -> Set[int]:
    """Extract all card IDs from constants.json."""
    ids = set()

    # default_hand
    if "default_hand" in constants:
        ids.add(constants["default_hand"]["starter"])
        ids.add(constants["default_hand"]["filler"])

    # evaluation boss monsters and interaction pieces
    if "evaluation" in constants:
        ids.update(constants["evaluation"].get("boss_monsters", []))
        ids.update(constants["evaluation"].get("interaction_pieces", []))
        ids.update(constants["evaluation"].get("fiendsmith_gy_targets", []))

    # level_6_fiends
    if "level_6_fiends" in constants:
        ids.update(constants["level_6_fiends"].get("cards", []))

    # level_1_light_fiends
    if "level_1_light_fiends" in constants:
        ids.update(constants["level_1_light_fiends"].get("cards", []))

    return ids


# =============================================================================
# TESTS: VERIFIED CARDS
# =============================================================================

class TestVerifiedCards:
    """Tests for verified_cards.json integrity."""

    def test_all_verified_cards_exist_in_cdb(self, verified_cards, cdb_connection):
        """Every card in verified_cards.json must exist in cards.cdb."""
        errors = []
        for card_id_str, card_data in verified_cards.items():
            if card_id_str.startswith("_"):  # Skip metadata
                continue
            card_id = int(card_id_str)
            cdb_card = get_cdb_card(cdb_connection, card_id)
            if cdb_card is None:
                errors.append(f"Card {card_id} ({card_data.get('name', 'unknown')}) not found in CDB")

        assert not errors, f"Verified cards missing from CDB:\n" + "\n".join(errors)

    def test_verified_card_names_match_cdb(self, verified_cards, cdb_connection):
        """Card names in verified_cards.json must match cards.cdb."""
        errors = []
        for card_id_str, card_data in verified_cards.items():
            if card_id_str.startswith("_"):
                continue
            card_id = int(card_id_str)
            cdb_card = get_cdb_card(cdb_connection, card_id)
            if cdb_card and cdb_card["name"] != card_data.get("name"):
                errors.append(
                    f"Card {card_id}: verified='{card_data.get('name')}', cdb='{cdb_card['name']}'"
                )

        assert not errors, f"Name mismatches:\n" + "\n".join(errors)

    def test_all_verified_cards_have_required_fields(self, verified_cards):
        """All verified cards must have required fields."""
        errors = []
        for card_id_str, card_data in verified_cards.items():
            if card_id_str.startswith("_"):
                continue
            if "name" not in card_data:
                errors.append(f"Card {card_id_str}: missing 'name'")
            if "verified" not in card_data:
                errors.append(f"Card {card_id_str}: missing 'verified'")
            if card_data.get("verified") is not True:
                errors.append(f"Card {card_id_str}: 'verified' is not True")

        assert not errors, f"Missing required fields:\n" + "\n".join(errors)


# =============================================================================
# TESTS: LOCKED LIBRARY
# =============================================================================

class TestLockedLibrary:
    """Tests for locked_library.json integrity."""

    def test_all_library_cards_are_verified(self, locked_library, verified_cards):
        """Every card in locked_library.json must be in verified_cards.json."""
        errors = []
        cards = locked_library.get("cards", {})
        for card_id_str, card_data in cards.items():
            if card_id_str not in verified_cards:
                errors.append(f"Card {card_id_str} ({card_data.get('name', 'unknown')}) not in verified_cards.json")

        assert not errors, f"Library cards not verified:\n" + "\n".join(errors)

    def test_library_card_names_match_verified(self, locked_library, verified_cards):
        """Card names in locked_library.json must match verified_cards.json."""
        errors = []
        cards = locked_library.get("cards", {})
        for card_id_str, card_data in cards.items():
            if card_id_str in verified_cards:
                verified_name = verified_cards[card_id_str].get("name")
                library_name = card_data.get("name")
                if verified_name != library_name:
                    errors.append(f"Card {card_id_str}: library='{library_name}', verified='{verified_name}'")

        assert not errors, f"Name mismatches:\n" + "\n".join(errors)

    def test_library_has_valid_deck_structure(self, locked_library):
        """Verify library has both main and extra deck cards."""
        cards = locked_library.get("cards", {})
        main_deck = [c for c in cards.values() if not c.get("is_extra_deck", False)]
        extra_deck = [c for c in cards.values() if c.get("is_extra_deck", False)]

        # Basic sanity checks
        assert len(main_deck) > 0, "No main deck cards found"
        assert len(extra_deck) > 0, "No extra deck cards found"
        assert len(cards) == len(main_deck) + len(extra_deck), "Card categorization mismatch"

        # Report actual counts (informational)
        print(f"\nLibrary structure: {len(main_deck)} main deck, {len(extra_deck)} extra deck")

        # If metadata exists, warn if it doesn't match (metadata may be stale)
        meta = locked_library.get("_meta", {})
        if "main_deck_unique" in meta and len(main_deck) != meta["main_deck_unique"]:
            print(f"Note: Metadata says {meta['main_deck_unique']} main deck unique, actual is {len(main_deck)}")
        if "extra_deck_unique" in meta and len(extra_deck) != meta["extra_deck_unique"]:
            print(f"Note: Metadata says {meta['extra_deck_unique']} extra deck unique, actual is {len(extra_deck)}")


# =============================================================================
# TESTS: CONSTANTS
# =============================================================================

class TestConstants:
    """Tests for constants.json integrity."""

    def test_all_constant_ids_are_verified(self, constants, verified_cards):
        """Every card ID in constants.json must be in verified_cards.json."""
        card_ids = extract_card_ids_from_constants(constants)
        errors = []
        for card_id in card_ids:
            if str(card_id) not in verified_cards:
                errors.append(f"Card ID {card_id} in constants.json not in verified_cards.json")

        assert not errors, f"Unverified card IDs in constants:\n" + "\n".join(errors)

    def test_constants_have_required_sections(self, constants):
        """constants.json must have required sections."""
        assert "default_hand" in constants, "Missing 'default_hand' section"
        assert "starter" in constants["default_hand"], "Missing 'starter' in default_hand"
        assert "filler" in constants["default_hand"], "Missing 'filler' in default_hand"


# =============================================================================
# TESTS: EVALUATION CONFIG
# =============================================================================

class TestEvaluationConfig:
    """Tests for evaluation_config.json integrity."""

    def test_all_eval_card_ids_are_verified(self, evaluation_config, verified_cards):
        """Every card ID in evaluation_config.json must be verified."""
        errors = []

        for card_id in evaluation_config.get("boss_monsters", []):
            if str(card_id) not in verified_cards:
                errors.append(f"Boss monster {card_id} not in verified_cards.json")

        for card_id in evaluation_config.get("interaction_pieces", []):
            if str(card_id) not in verified_cards:
                errors.append(f"Interaction piece {card_id} not in verified_cards.json")

        for card_id in evaluation_config.get("fiendsmith_gy_targets", []):
            if str(card_id) not in verified_cards:
                errors.append(f"GY target {card_id} not in verified_cards.json")

        assert not errors, f"Unverified card IDs in evaluation_config:\n" + "\n".join(errors)


# =============================================================================
# TESTS: CARD ROLES
# =============================================================================

class TestCardRoles:
    """Tests for card_roles.json integrity."""

    def test_all_role_card_ids_are_verified(self, card_roles, verified_cards):
        """Every card ID in card_roles.json must be verified."""
        errors = []
        for card_id_str in card_roles.get("cards", {}).keys():
            if card_id_str not in verified_cards:
                errors.append(f"Card ID {card_id_str} in card_roles.json not in verified_cards.json")

        assert not errors, f"Unverified card IDs in card_roles:\n" + "\n".join(errors)


# =============================================================================
# TESTS: CROSS-FILE CONSISTENCY
# =============================================================================

class TestCrossFileConsistency:
    """Tests for consistency across all config files."""

    def test_no_orphan_verified_cards(self, verified_cards, locked_library):
        """Warn about verified cards not in the library (informational)."""
        library_ids = set(locked_library.get("cards", {}).keys())
        # Add token and filler which aren't in library
        library_ids.add("35552986")  # Fiendsmith Token
        library_ids.add("10000040")  # Holactie (filler card)

        orphans = []
        for card_id_str in verified_cards.keys():
            if card_id_str.startswith("_"):
                continue
            if card_id_str not in library_ids:
                orphans.append(f"{card_id_str}: {verified_cards[card_id_str].get('name')}")

        # This is just informational - some verified cards may be for testing
        if orphans:
            print(f"\nNote: {len(orphans)} verified cards not in library (may be intentional)")


# =============================================================================
# TESTS: PENDING VERIFICATIONS
# =============================================================================

class TestPendingVerifications:
    """Tests for pending_verifications.json."""

    def test_pending_file_exists(self):
        """pending_verifications.json should exist."""
        assert PENDING_PATH.exists(), f"pending_verifications.json not found at {PENDING_PATH}"

    def test_no_stale_pending_verifications(self):
        """Warn if there are pending verifications (informational)."""
        if not PENDING_PATH.exists():
            return

        with open(PENDING_PATH) as f:
            pending = json.load(f)

        pending_cards = pending.get("pending", [])
        if pending_cards:
            print(f"\nWARNING: {len(pending_cards)} cards pending verification!")
            for card in pending_cards:
                print(f"  - {card['card_id']}: {card['proposed_name']}")
            print("Run: python scripts/review_pending.py")


# =============================================================================
# RUN DIRECTLY
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
