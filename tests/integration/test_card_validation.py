#!/usr/bin/env python3
"""
Integration test for card validation in MSG_SELECT_SUM parsing.

Tests that:
1. Loads verified_cards.json for reference data
2. Validates SELECT_SUM card format (18-byte entries)
3. Compares parsed values against verified data
4. Documents expected vs actual behavior

CRITICAL FINDING:
The ygopro-core MSG_SELECT_SUM uses 18-byte card entries:
- code: 4 bytes (LE)
- loc_info: 10 bytes
  - controler: 1 byte
  - location: 1 byte
  - sequence: 4 bytes (LE)
  - position: 4 bytes (LE)  <-- MISSING FROM 14-BYTE PARSER!
- sum_param: 4 bytes (LE)

The current 14-byte parser reads sum_param 4 bytes too early,
causing incorrect level values (e.g., Engraver shows level=1 instead of 6).

Run:
    pytest tests/integration/test_card_validation.py -v
"""

import json
import struct
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "cffi"))

# =============================================================================
# TEST DATA
# =============================================================================

# Path to verified card data
VERIFIED_CARDS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "verified_cards.json"


def load_verified_cards():
    """Load verified card data from JSON."""
    with open(VERIFIED_CARDS_PATH) as f:
        data = json.load(f)
    return data["cards"]


# =============================================================================
# 18-BYTE FORMAT PARSER (CORRECT)
# =============================================================================

def parse_sum_card_18byte(data: bytes, offset: int) -> dict:
    """Parse a single card entry from MSG_SELECT_SUM using correct 18-byte format.

    Card format (18 bytes):
    - code: 4 bytes LE (card passcode)
    - controler: 1 byte
    - location: 1 byte
    - sequence: 4 bytes LE
    - position: 4 bytes LE  <- This was MISSING from 14-byte parser!
    - sum_param: 4 bytes LE (level for sum calculation)

    Returns:
        dict with parsed card data
    """
    if offset + 18 > len(data):
        raise ValueError(f"Not enough data for 18-byte card at offset {offset}")

    code = struct.unpack_from('<I', data, offset)[0]
    controler = data[offset + 4]
    location = data[offset + 5]
    sequence = struct.unpack_from('<I', data, offset + 6)[0]
    position = struct.unpack_from('<I', data, offset + 10)[0]
    sum_param = struct.unpack_from('<I', data, offset + 14)[0]

    # Extract level from sum_param (low 16 bits = primary level)
    level = sum_param & 0xFFFF
    level2 = (sum_param >> 16) & 0xFFFF

    return {
        'code': code,
        'controler': controler,
        'location': location,
        'sequence': sequence,
        'position': position,
        'sum_param': sum_param,
        'level': level if 1 <= level <= 12 else sum_param,
        'level2': level2 if 1 <= level2 <= 12 else 0,
    }


def parse_sum_card_14byte(data: bytes, offset: int) -> dict:
    """Parse card using INCORRECT 14-byte format (for comparison).

    This is the buggy format that reads sum_param 4 bytes too early.
    """
    if offset + 14 > len(data):
        raise ValueError(f"Not enough data for 14-byte card at offset {offset}")

    code = struct.unpack_from('<I', data, offset)[0]
    controler = data[offset + 4]
    location = data[offset + 5]
    sequence = struct.unpack_from('<I', data, offset + 6)[0]
    sum_param = struct.unpack_from('<I', data, offset + 10)[0]  # WRONG OFFSET!

    return {
        'code': code,
        'controler': controler,
        'location': location,
        'sequence': sequence,
        'sum_param': sum_param,
        'level': sum_param,  # Buggy: reads position as level
    }


# =============================================================================
# TEST FIXTURES: Synthetic MSG_SELECT_SUM Data
# =============================================================================

def create_select_sum_card(code: int, level: int, controler: int = 0,
                           location: int = 4, sequence: int = 0,
                           position: int = 0x5) -> bytes:
    """Create a synthetic 18-byte card entry for testing.

    Args:
        code: Card passcode
        level: Card level (goes into sum_param)
        controler: Controller (0 = player)
        location: Card location (4 = LOCATION_MZONE)
        sequence: Sequence number
        position: Position flags (5 = face-up attack)

    Returns:
        18 bytes representing the card entry
    """
    return struct.pack(
        '<I B B I I I',  # LE: u32, u8, u8, u32, u32, u32
        code,            # 4 bytes: passcode
        controler,       # 1 byte
        location,        # 1 byte
        sequence,        # 4 bytes
        position,        # 4 bytes
        level            # 4 bytes: sum_param (level)
    )


# =============================================================================
# TESTS
# =============================================================================

class TestSelectSumFormat:
    """Test MSG_SELECT_SUM card entry parsing."""

    def test_18byte_format_parses_correctly(self):
        """Test that 18-byte format correctly extracts level from sum_param."""
        # Create synthetic card: Fiendsmith Engraver (ID: 60764609, Level 6)
        card_data = create_select_sum_card(
            code=60764609,
            level=6,  # Engraver is Level 6
            controler=0,
            location=4,  # Monster zone
            sequence=0,
            position=5,  # Face-up attack
        )

        result = parse_sum_card_18byte(card_data, 0)

        assert result['code'] == 60764609, f"Expected code 60764609, got {result['code']}"
        assert result['level'] == 6, f"Expected level 6, got {result['level']}"
        assert result['sum_param'] == 6, f"Expected sum_param 6, got {result['sum_param']}"

    def test_14byte_format_shows_bug(self):
        """Test that 14-byte format incorrectly reads position as level."""
        # Create synthetic card with position=5 (what 14-byte parser reads as level)
        card_data = create_select_sum_card(
            code=60764609,
            level=6,
            position=5,  # This becomes 'level' in buggy parser!
        )

        result = parse_sum_card_14byte(card_data, 0)

        # BUG: 14-byte parser reads position (5) as sum_param instead of level (6)
        assert result['sum_param'] == 5, f"Buggy parser should read position (5) as sum_param"
        assert result['sum_param'] != 6, "Buggy parser should NOT get correct level"

    def test_format_difference_demonstrated(self):
        """Demonstrate the difference between 14-byte and 18-byte parsing."""
        # Engraver (Level 6) with position=1
        card_data = create_select_sum_card(
            code=60764609,
            level=6,
            position=1,  # Common position value
        )

        correct = parse_sum_card_18byte(card_data, 0)
        buggy = parse_sum_card_14byte(card_data, 0)

        print(f"\n18-byte (correct): level={correct['level']}, sum_param={correct['sum_param']}")
        print(f"14-byte (buggy):   level={buggy['level']}, sum_param={buggy['sum_param']}")

        assert correct['level'] == 6, "Correct parser should get level 6"
        assert buggy['sum_param'] == 1, "Buggy parser reads position (1) as sum_param"


class TestVerifiedCardData:
    """Test against verified card data."""

    def test_load_verified_cards(self):
        """Test that verified_cards.json loads correctly."""
        cards = load_verified_cards()
        assert len(cards) > 0, "Should have verified cards"

        # Check Engraver exists
        assert "60764609" in cards, "Fiendsmith Engraver should be in verified data"
        engraver = cards["60764609"]
        assert engraver["level"] == 6, f"Engraver level should be 6, got {engraver['level']}"

    def test_verified_level_6_fiends(self):
        """Test that Level 6 Fiends are correctly identified for Caesar Xyz."""
        cards = load_verified_cards()

        # Cards that should be Level 6 for Caesar materials
        level_6_candidates = ["60764609", "93860227"]  # Engraver, Necroquip Princess

        for card_id in level_6_candidates:
            if card_id in cards:
                card = cards[card_id]
                if "level" in card:
                    assert card["level"] == 6, f"{card['name']} should be Level 6"

    def test_engraver_synthetic_parse(self):
        """Test that synthetic Engraver data parses to verified level."""
        cards = load_verified_cards()
        engraver = cards["60764609"]
        verified_level = engraver["level"]

        # Create synthetic card with verified level
        card_data = create_select_sum_card(
            code=60764609,
            level=verified_level,  # Use verified level (6)
            position=5,
        )

        result = parse_sum_card_18byte(card_data, 0)

        assert result['level'] == verified_level, \
            f"Parsed level {result['level']} doesn't match verified {verified_level}"


class TestCaesarXyzMaterials:
    """Test Caesar Xyz summon requires Level 6 materials."""

    def test_caesar_target_sum(self):
        """Caesar (Rank 6) needs 2 Level 6 monsters: target_sum = 12."""
        cards = load_verified_cards()

        # Caesar requires: 2 Level 6 Fiend monsters
        caesar = cards.get("79559912")
        assert caesar is not None, "Caesar should be in verified data"
        assert caesar["rank"] == 6, f"Caesar should be Rank 6, got {caesar.get('rank')}"

        # Target sum for 2 Level 6 monsters = 6 + 6 = 12
        expected_target_sum = 12

        # Create synthetic SELECT_SUM with two Engravers
        engraver_level = cards["60764609"]["level"]  # 6

        card1 = create_select_sum_card(code=60764609, level=engraver_level, sequence=0)
        card2 = create_select_sum_card(code=60764609, level=engraver_level, sequence=1)

        parsed1 = parse_sum_card_18byte(card1, 0)
        parsed2 = parse_sum_card_18byte(card2, 0)

        actual_sum = parsed1['level'] + parsed2['level']

        assert actual_sum == expected_target_sum, \
            f"Sum of two Engravers should be {expected_target_sum}, got {actual_sum}"

    def test_observed_bug_behavior(self):
        """Document the observed bug: target=1, level=1 for Engraver."""
        # From trace.log:
        # SELECT_SUM: target=1 (exact), select 1-1 cards
        #   can[0]: Fiendsmith Engraver level=1 (sum_param=0x00000001)

        # This bug occurs because:
        # 1. 14-byte parser reads position field as sum_param
        # 2. Position value happens to be 1 (or similar small value)
        # 3. Engine still succeeds because it uses internal correct values

        # Simulate the bug with position=1
        buggy_card = create_select_sum_card(
            code=60764609,
            level=6,      # Actual level
            position=1,   # What gets read as level by buggy parser
        )

        buggy_result = parse_sum_card_14byte(buggy_card, 0)
        correct_result = parse_sum_card_18byte(buggy_card, 0)

        # Bug: 14-byte parser reads position (1) as sum_param
        assert buggy_result['sum_param'] == 1, "Bug reproduces: reads position as level"

        # Correct: 18-byte parser reads actual level (6)
        assert correct_result['level'] == 6, "Correct parser gets level 6"

        print("\n=== OBSERVED BUG REPRODUCED ===")
        print(f"14-byte (buggy):   sum_param={buggy_result['sum_param']} (position value)")
        print(f"18-byte (correct): level={correct_result['level']} (actual level)")
        print("This explains why trace shows 'level=1' instead of 'level=6'")


# =============================================================================
# MAIN
# =============================================================================

def run_all_tests():
    """Run all tests manually."""
    print("=" * 60)
    print("Card Validation Integration Tests")
    print("=" * 60)

    # Load verified data
    print("\n1. Loading verified cards...")
    cards = load_verified_cards()
    print(f"   Loaded {len(cards)} verified cards")

    # Test format parsing
    print("\n2. Testing 18-byte format...")
    card_data = create_select_sum_card(code=60764609, level=6, position=1)
    result = parse_sum_card_18byte(card_data, 0)
    print(f"   Engraver: code={result['code']}, level={result['level']}")
    assert result['level'] == 6, "FAIL: Level should be 6"
    print("   PASS: 18-byte format correctly parses level")

    # Test bug reproduction
    print("\n3. Demonstrating 14-byte bug...")
    buggy = parse_sum_card_14byte(card_data, 0)
    print(f"   14-byte reads sum_param as: {buggy['sum_param']} (should be 6)")
    print(f"   Bug: reads position field instead of sum_param")

    # Test Caesar materials
    print("\n4. Testing Caesar Xyz requirements...")
    engraver = cards["60764609"]
    caesar = cards.get("79559912", {"rank": 6, "materials": "2 Level 6 Fiend monsters"})
    print(f"   Caesar requires: {caesar.get('materials', 'N/A')}")
    print(f"   Engraver level: {engraver['level']}")
    print(f"   Two Engravers: {engraver['level']} + {engraver['level']} = {engraver['level'] * 2}")
    assert engraver['level'] == 6, "Engraver should be Level 6"
    print("   PASS: Verified Engraver is Level 6 for Caesar Xyz")

    print("\n" + "=" * 60)
    print("All integration tests passed!")
    print("=" * 60)
    print("\nCRITICAL: The combo_enumeration.py parser needs to be")
    print("updated from 14-byte to 18-byte card format.")
    print("\nFix location: combo_enumeration.py:790-823")
    print("Change: Add 4-byte position field before sum_param")


if __name__ == "__main__":
    run_all_tests()
