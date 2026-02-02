"""
card_validator.py - Verified card data validation module.

This module provides validation of card data against a human-verified reference
to prevent hallucinated or incorrect card information from propagating through
the combo pipeline.

Usage:
    from card_validator import CardValidator, get_verified_card

    validator = CardValidator()

    # Get verified card data
    card = validator.get_card(60764609)
    print(card['level'])  # 6

    # Validate engine data
    validator.validate_card(60764609, 'level', 6)  # OK
    validator.validate_card(60764609, 'level', 1)  # Raises warning
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Path to verified cards JSON (relative to project root, not src/)
VERIFIED_CARDS_PATH = Path(__file__).parent.parent.parent.parent / "config" / "verified_cards.json"
CDB_PATH = Path(__file__).parent.parent.parent.parent / "cards.cdb"


class CardNotVerifiedError(Exception):
    """Raised when accessing a card that hasn't been verified."""
    pass


class CardValidationError(Exception):
    """Raised when card data doesn't match verified data."""
    pass


class CardValidator:
    """Validates card data against verified reference.

    This class loads human-verified card data and provides methods to:
    - Look up verified card attributes
    - Validate engine/CDB data against verified data
    - Log warnings when discrepancies are found
    """

    def __init__(self, verified_path: Optional[Path] = None, strict: bool = False):
        """Initialize the validator.

        Args:
            verified_path: Path to verified_cards.json. Uses default if None.
            strict: If True, raise exceptions on validation failures.
                    If False, log warnings instead.
        """
        self.verified_path = verified_path or VERIFIED_CARDS_PATH
        self.strict = strict
        self._cards: Dict[str, Dict] = {}
        self._metadata: Dict = {}
        self._loaded = False

    def _ensure_loaded(self):
        """Load verified cards data if not already loaded."""
        if self._loaded:
            return

        if not self.verified_path.exists():
            raise FileNotFoundError(
                f"Verified cards file not found: {self.verified_path}\n"
                "Create config/verified_cards.json with human-verified card data."
            )

        with open(self.verified_path) as f:
            data = json.load(f)

        self._cards = data.get("cards", {})
        self._metadata = data.get("metadata", {})
        self._loaded = True

        logger.info(f"Loaded {len(self._cards)} verified cards from {self.verified_path}")

    def get_card(self, card_id: Union[int, str]) -> Dict[str, Any]:
        """Get verified card data by ID.

        Args:
            card_id: Card passcode (int or str)

        Returns:
            Dict with verified card attributes

        Raises:
            CardNotVerifiedError: If card is not in verified database
        """
        self._ensure_loaded()

        card_id_str = str(card_id)

        if card_id_str not in self._cards:
            raise CardNotVerifiedError(
                f"Card {card_id} is not in verified database.\n"
                "Add it to config/verified_cards.json after verifying data from official sources."
            )

        return self._cards[card_id_str].copy()

    def get_attribute(self, card_id: Union[int, str], attribute: str) -> Any:
        """Get a specific verified attribute for a card.

        Args:
            card_id: Card passcode
            attribute: Attribute name (e.g., 'level', 'atk', 'type')

        Returns:
            The verified attribute value

        Raises:
            CardNotVerifiedError: If card not verified
            KeyError: If attribute not present for this card
        """
        card = self.get_card(card_id)

        if attribute not in card:
            raise KeyError(
                f"Attribute '{attribute}' not found for card {card_id} ({card.get('name', 'unknown')}).\n"
                f"Available attributes: {list(card.keys())}"
            )

        return card[attribute]

    def validate(self, card_id: Union[int, str], attribute: str,
                 actual_value: Any, source: str = "unknown") -> bool:
        """Validate a card attribute against verified data.

        Args:
            card_id: Card passcode
            attribute: Attribute to validate (e.g., 'level')
            actual_value: The value to check
            source: Description of where actual_value came from (for logging)

        Returns:
            True if valid, False if mismatch (or raises if strict mode)

        Raises:
            CardValidationError: In strict mode, if validation fails
        """
        try:
            expected = self.get_attribute(card_id, attribute)
        except CardNotVerifiedError:
            # Card not verified - can't validate
            logger.warning(
                f"Cannot validate {attribute} for unverified card {card_id}"
            )
            return True  # Don't fail on unverified cards
        except KeyError:
            # Attribute not tracked for this card
            return True

        if actual_value != expected:
            card_name = self._cards.get(str(card_id), {}).get('name', 'unknown')
            msg = (
                f"Card data mismatch for {card_name} ({card_id}):\n"
                f"  {attribute}: expected={expected}, actual={actual_value}\n"
                f"  Source: {source}"
            )

            if self.strict:
                raise CardValidationError(msg)
            else:
                logger.warning(msg)
                return False

        return True

    def validate_card_dict(self, card_id: Union[int, str], card_data: Dict,
                          source: str = "unknown") -> List[str]:
        """Validate all attributes in a card dictionary.

        Args:
            card_id: Card passcode
            card_data: Dict with card attributes to validate
            source: Description of data source

        Returns:
            List of validation error messages (empty if all valid)
        """
        errors = []

        # Map of common attribute variations
        attr_map = {
            'level': ['level', 'rank', 'link_rating'],
            'atk': ['atk', 'attack'],
            'def': ['def', 'defense'],
        }

        try:
            verified = self.get_card(card_id)
        except CardNotVerifiedError:
            return []  # Can't validate unverified cards

        for attr, value in card_data.items():
            if attr in verified:
                if not self.validate(card_id, attr, value, source):
                    errors.append(
                        f"{attr}: expected={verified[attr]}, actual={value}"
                    )

        return errors

    def is_verified(self, card_id: Union[int, str]) -> bool:
        """Check if a card is in the verified database."""
        self._ensure_loaded()
        return str(card_id) in self._cards

    def get_all_verified_ids(self) -> List[str]:
        """Get list of all verified card IDs."""
        self._ensure_loaded()
        return list(self._cards.keys())

    def get_level_6_fiends(self) -> List[Dict]:
        """Get all verified Level 6 Fiend monsters (for Caesar materials)."""
        self._ensure_loaded()
        result = []
        for card_id, card in self._cards.items():
            if card.get('level') == 6 and 'Fiend' in card.get('type', ''):
                result.append({'id': card_id, **card})
        return result


def get_verified_card(card_id: Union[int, str]) -> Dict[str, Any]:
    """Convenience function to get verified card data.

    Args:
        card_id: Card passcode

    Returns:
        Dict with verified card attributes
    """
    validator = CardValidator()
    return validator.get_card(card_id)


def validate_engine_card(card_id: Union[int, str], level: int,
                         source: str = "ygopro-core") -> bool:
    """Validate a card's level from the engine against verified data.

    This is specifically for diagnosing the SELECT_SUM level parsing issue.

    Args:
        card_id: Card passcode
        level: Level value from engine
        source: Description of source

    Returns:
        True if level matches verified data
    """
    validator = CardValidator()
    return validator.validate(card_id, 'level', level, source)


def compare_cdb_to_verified() -> Dict[str, List[str]]:
    """Compare cards.cdb data against verified data.

    Returns:
        Dict with 'matches' and 'mismatches' lists
    """
    validator = CardValidator()
    validator._ensure_loaded()

    results = {'matches': [], 'mismatches': [], 'missing_from_cdb': []}

    if not CDB_PATH.exists():
        logger.warning(f"cards.cdb not found at {CDB_PATH}")
        return results

    conn = sqlite3.connect(CDB_PATH)
    cursor = conn.cursor()

    for card_id, verified in validator._cards.items():
        cursor.execute(
            "SELECT level, atk, def FROM datas WHERE id = ?",
            (int(card_id),)
        )
        row = cursor.fetchone()

        if row is None:
            results['missing_from_cdb'].append(f"{card_id} ({verified.get('name', 'unknown')})")
            continue

        cdb_level, cdb_atk, cdb_def = row

        # Check level (handle Xyz rank and Link rating)
        expected_level = verified.get('level') or verified.get('rank') or verified.get('link_rating')
        if expected_level and cdb_level != expected_level:
            # Note: CDB stores rank/link in level field with special encoding
            # Xyz: level & 0xff = rank, Link: level & 0xff = link rating
            actual_level = cdb_level & 0xff
            if actual_level != expected_level:
                results['mismatches'].append(
                    f"{card_id} ({verified.get('name')}): "
                    f"level CDB={cdb_level} (extracted={actual_level}), verified={expected_level}"
                )
            else:
                results['matches'].append(f"{card_id} level OK")
        else:
            results['matches'].append(f"{card_id} level OK")

        # Check ATK
        if 'atk' in verified:
            if cdb_atk != verified['atk']:
                results['mismatches'].append(
                    f"{card_id} ({verified.get('name')}): "
                    f"ATK CDB={cdb_atk}, verified={verified['atk']}"
                )

        # Check DEF (not applicable for Link monsters)
        if 'def' in verified and 'link_rating' not in verified:
            if cdb_def != verified['def']:
                results['mismatches'].append(
                    f"{card_id} ({verified.get('name')}): "
                    f"DEF CDB={cdb_def}, verified={verified['def']}"
                )

    conn.close()
    return results


if __name__ == "__main__":
    # Run validation check
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("CARD VALIDATOR - CDB vs Verified Data")
    print("=" * 60)

    results = compare_cdb_to_verified()

    print(f"\nMatches: {len(results['matches'])}")
    print(f"Mismatches: {len(results['mismatches'])}")
    print(f"Missing from CDB: {len(results['missing_from_cdb'])}")

    if results['mismatches']:
        print("\n--- MISMATCHES ---")
        for m in results['mismatches']:
            print(f"  {m}")

    if results['missing_from_cdb']:
        print("\n--- MISSING FROM CDB ---")
        for m in results['missing_from_cdb']:
            print(f"  {m}")

    # Test specific card
    print("\n--- Level 6 Fiends (Caesar Materials) ---")
    validator = CardValidator()
    for card in validator.get_level_6_fiends():
        print(f"  {card['id']}: {card['name']} (Level {card['level']})")
