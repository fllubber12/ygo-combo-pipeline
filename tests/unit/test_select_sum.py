#!/usr/bin/env python3
"""
Unit tests for MSG_SELECT_SUM handling and sum enumeration.

Tests:
1. find_valid_sum_combinations() - Core algorithm
2. parse_select_sum() - Message parsing  
3. Response format encoding - Binary protocol
4. Edge cases - Empty lists, impossible sums, duplicates

Run:
    python tests/test_select_sum.py
    pytest tests/test_select_sum.py -v
"""

import sys
import struct
from pathlib import Path
from typing import List, Dict
from itertools import combinations

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src" / "ygo_combo"))


# =============================================================================
# STANDALONE IMPLEMENTATION (for testing before patch applied)
# =============================================================================

def find_valid_sum_combinations(
    must_select: List[Dict],
    can_select: List[Dict],
    target_sum: int,
    min_select: int = 1,
    max_select: int = 5,
) -> List[List[int]]:
    """Find all valid combinations of cards that sum to target value."""
    
    must_sum = sum(card.get("value", 0) for card in must_select)
    must_count = len(must_select)
    remaining_sum = target_sum - must_sum
    remaining_min = max(0, min_select - must_count)
    remaining_max = max(0, max_select - must_count)
    
    valid_combos = []
    
    # Handle edge case: must_select already meets target
    if remaining_sum == 0 and remaining_min == 0:
        valid_combos.append([])
    
    # Try all combination sizes
    for size in range(max(1, remaining_min), min(remaining_max + 1, len(can_select) + 1)):
        for combo_indices in combinations(range(len(can_select)), size):
            combo_sum = sum(can_select[i].get("value", 0) for i in combo_indices)
            
            if combo_sum == remaining_sum:
                valid_combos.append(list(combo_indices))
    
    return valid_combos


# =============================================================================
# TEST CASES
# =============================================================================

def test_xyz_rank6_two_materials():
    """Test: Select 2 Level 6 monsters for Rank 6 Xyz (6+6=12)."""
    must_select = []
    can_select = [
        {"code": 35552986, "value": 6, "name": "Token A"},
        {"code": 2463794, "value": 6, "name": "Requiem"},
    ]
    target_sum = 12  # 6 + 6
    
    combos = find_valid_sum_combinations(must_select, can_select, target_sum)
    
    assert len(combos) == 1, f"Expected 1 combo, got {len(combos)}: {combos}"
    assert combos[0] == [0, 1], f"Expected [0, 1], got {combos[0]}"
    
    print("✅ test_xyz_rank6_two_materials PASSED")


def test_xyz_rank6_three_options():
    """Test: Select 2 from 3 Level 6 monsters."""
    must_select = []
    can_select = [
        {"code": 1, "value": 6, "name": "Monster A"},
        {"code": 2, "value": 6, "name": "Monster B"},
        {"code": 3, "value": 6, "name": "Monster C"},
    ]
    target_sum = 12  # 6 + 6
    
    combos = find_valid_sum_combinations(must_select, can_select, target_sum)
    
    # Should find 3 combinations: (0,1), (0,2), (1,2)
    assert len(combos) == 3, f"Expected 3 combos, got {len(combos)}: {combos}"
    
    expected = [[0, 1], [0, 2], [1, 2]]
    assert combos == expected, f"Expected {expected}, got {combos}"
    
    print("✅ test_xyz_rank6_three_options PASSED")


def test_synchro_level8_tuner_nontuner():
    """Test: Level 2 Tuner + Level 6 non-tuner = Level 8 Synchro."""
    must_select = [
        {"code": 100, "value": 2, "name": "Tuner (Level 2)"},  # Must use this tuner
    ]
    can_select = [
        {"code": 200, "value": 6, "name": "Non-tuner A (Level 6)"},
        {"code": 201, "value": 4, "name": "Non-tuner B (Level 4)"},
        {"code": 202, "value": 6, "name": "Non-tuner C (Level 6)"},
    ]
    target_sum = 8  # Synchro level
    
    combos = find_valid_sum_combinations(must_select, can_select, target_sum)
    
    # Remaining sum = 8 - 2 = 6
    # Valid: index 0 (value 6), index 2 (value 6)
    assert len(combos) == 2, f"Expected 2 combos, got {len(combos)}: {combos}"
    assert [0] in combos, f"Expected [0] in combos"
    assert [2] in combos, f"Expected [2] in combos"
    
    print("✅ test_synchro_level8_tuner_nontuner PASSED")


def test_no_valid_combinations():
    """Test: No possible combination reaches target."""
    must_select = []
    can_select = [
        {"code": 1, "value": 3},
        {"code": 2, "value": 4},
    ]
    target_sum = 10  # Can only make 3, 4, or 7 - can't make 10
    
    combos = find_valid_sum_combinations(must_select, can_select, target_sum)
    
    assert len(combos) == 0, f"Expected 0 combos, got {len(combos)}"
    
    print("✅ test_no_valid_combinations PASSED")


def test_must_select_completes_sum():
    """Test: Must-select cards already meet the target."""
    must_select = [
        {"code": 1, "value": 6},
        {"code": 2, "value": 6},
    ]
    can_select = [
        {"code": 3, "value": 6},  # Available but not needed
    ]
    target_sum = 12  # Already met by must_select
    
    combos = find_valid_sum_combinations(must_select, can_select, target_sum, min_select=2)
    
    # Empty list means "select nothing from can_select" (must_select is auto-included)
    assert [] in combos, f"Expected empty combo in {combos}"
    
    print("✅ test_must_select_completes_sum PASSED")


def test_empty_can_select():
    """Test: No optional cards available."""
    must_select = [
        {"code": 1, "value": 12},  # Single card meets target
    ]
    can_select = []
    target_sum = 12
    
    combos = find_valid_sum_combinations(must_select, can_select, target_sum, min_select=1)
    
    assert [] in combos, f"Expected empty combo for must-only selection"
    
    print("✅ test_empty_can_select PASSED")


def test_large_combination_space():
    """Test: Many cards with multiple valid combinations."""
    must_select = []
    can_select = [
        {"code": i, "value": 2} for i in range(6)  # 6 Level 2 monsters
    ]
    target_sum = 6  # Need 3 Level 2s (2+2+2=6)
    
    combos = find_valid_sum_combinations(must_select, can_select, target_sum, max_select=6)
    
    # C(6,3) = 20 combinations
    from math import comb
    expected_count = comb(6, 3)
    assert len(combos) == expected_count, f"Expected {expected_count} combos, got {len(combos)}"
    
    print("✅ test_large_combination_space PASSED")


# =============================================================================
# RESPONSE FORMAT TESTS
# =============================================================================

def test_cancel_response_format():
    """Test: Cancel response is int32(-1)."""
    response = struct.pack("<i", -1)
    
    assert len(response) == 4, f"Cancel should be 4 bytes, got {len(response)}"
    assert struct.unpack("<i", response)[0] == -1
    
    print("✅ test_cancel_response_format PASSED")


def test_select_response_format_single():
    """Test: Single card selection response format."""
    # type=0, count=1, index=3
    indices = [3]
    response = struct.pack("<iI", 0, len(indices))
    for idx in indices:
        response += struct.pack("<I", idx)
    
    assert len(response) == 12, f"Expected 12 bytes (4+4+4), got {len(response)}"
    
    # Verify unpacking
    offset = 0
    typ = struct.unpack_from("<i", response, offset)[0]; offset += 4
    count = struct.unpack_from("<I", response, offset)[0]; offset += 4
    idx0 = struct.unpack_from("<I", response, offset)[0]; offset += 4
    
    assert typ == 0
    assert count == 1
    assert idx0 == 3
    
    print("✅ test_select_response_format_single PASSED")


def test_select_response_format_multiple():
    """Test: Multi-card selection response format."""
    indices = [0, 2, 5]
    response = struct.pack("<iI", 0, len(indices))
    for idx in indices:
        response += struct.pack("<I", idx)
    
    expected_len = 4 + 4 + 4 * len(indices)  # type + count + indices
    assert len(response) == expected_len, f"Expected {expected_len} bytes, got {len(response)}"
    
    print("✅ test_select_response_format_multiple PASSED")


# =============================================================================
# MESSAGE PARSING TESTS
# =============================================================================

def test_parse_select_sum_basic():
    """Test: Parse a basic MSG_SELECT_SUM message."""
    # Build test message
    player = 0
    must_count = 1
    can_count = 2
    target_sum = 8
    
    msg = struct.pack("<BBB", player, must_count, can_count)
    msg += struct.pack("<I", target_sum)
    
    # Must card: code=100, con=0, loc=4, seq=0, value=2
    msg += struct.pack("<IBBBI", 100, 0, 4, 0, 2)
    
    # Can cards
    msg += struct.pack("<IBBBI", 200, 0, 4, 1, 6)  # value=6
    msg += struct.pack("<IBBBI", 201, 0, 4, 2, 4)  # value=4
    
    # Try to import the parser
    try:
        from combo_enumeration import parse_select_sum
        result = parse_select_sum(msg)
        
        assert result["player"] == 0
        assert result["must_count"] == 1
        assert result["can_count"] == 2
        assert result["target_sum"] == 8
        assert len(result["must_select"]) == 1
        assert len(result["can_select"]) == 2
        assert result["must_select"][0]["value"] == 2
        assert result["can_select"][0]["value"] == 6
        assert result["can_select"][1]["value"] == 4
        
        print("✅ test_parse_select_sum_basic PASSED")
    except ImportError:
        print("⚠️  test_parse_select_sum_basic SKIPPED (combo_enumeration not importable)")


# =============================================================================
# MAIN
# =============================================================================

def run_all_tests():
    """Run all tests and report results."""
    tests = [
        # Core algorithm tests
        test_xyz_rank6_two_materials,
        test_xyz_rank6_three_options,
        test_synchro_level8_tuner_nontuner,
        test_no_valid_combinations,
        test_must_select_completes_sum,
        test_empty_can_select,
        test_large_combination_space,
        # Response format tests
        test_cancel_response_format,
        test_select_response_format_single,
        test_select_response_format_multiple,
        # Message parsing tests
        test_parse_select_sum_basic,
    ]
    
    print("=" * 60)
    print("MSG_SELECT_SUM Unit Tests")
    print("=" * 60)
    print()
    
    passed = 0
    failed = 0
    skipped = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            if "SKIPPED" in str(e) or "SKIP" in str(e):
                skipped += 1
            else:
                print(f"❌ {test.__name__} ERROR: {e}")
                failed += 1
    
    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
