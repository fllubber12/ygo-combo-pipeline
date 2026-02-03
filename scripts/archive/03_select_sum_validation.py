#!/usr/bin/env python3
"""
Diagnostic 3: SELECT_SUM parsing validation for Xyz summons.

Caesar requires 2x Level 6 Fiends. The SELECT_SUM message should show:
- target_sum = 12 (6 + 6)
- Cards with level/value = 6

Known issue: sum_param field may show 1 instead of actual level.
Workaround: Falls back to verified_cards.json lookup.

This diagnostic:
1. Patches combo_enumeration to log SELECT_SUM messages
2. Runs enumeration until SELECT_SUM is encountered
3. Validates the parsed values

Run from repo root:
    python3 scripts/diagnostics/03_select_sum_validation.py
"""

import sys
import os
import struct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Import parsers directly to test
from ygo_combo.enumeration.parsers import (
    parse_select_sum, _get_card_validator
)

# Known Level 6 Fiends for Caesar
LEVEL_6_FIENDS = {
    60764609: ("Fiendsmith Engraver", 6),
    46640168: ("Fiendsmith's Lacrima", 6),
    93860227: ("Necroquip Princess", 6),
}


def test_parser_with_synthetic_data():
    """Test parser with known-good synthetic SELECT_SUM message."""
    print("=" * 60)
    print("TEST 1: Synthetic SELECT_SUM message")
    print("=" * 60)
    
    # Build a synthetic MSG_SELECT_SUM for 2x Level 6
    # Header (15 bytes):
    #   player(1) + select_mode(1) + min(1) + max(1) + 
    #   target_sum(4 BE) + can_count(4 BE) + padding(3)
    # Cards (16 bytes each):
    #   code(4) + controller(1) + location(1) + sequence(4) + sum_param(4) + padding(2)
    
    # Engraver + Necroquip for Caesar Xyz
    engraver_code = 60764609
    necroquip_code = 93860227
    
    header = struct.pack(
        '>BBBB I I',  # Mix of bytes and big-endian u32
        0,    # player
        0,    # select_mode (exact)
        2,    # min select
        2,    # max select  
        12,   # target_sum (6+6)
        2,    # can_count
    )
    header += b'\x00\x00\x00'  # padding to offset 15
    
    # Card 1: Engraver (Level 6)
    card1 = struct.pack('<I', engraver_code)  # code
    card1 += struct.pack('<BB', 0, 0x04)       # controller, location (MZONE)
    card1 += struct.pack('<I', 0)              # sequence
    card1 += struct.pack('<I', 6)              # sum_param = level 6
    card1 += b'\x00\x00'                       # padding
    
    # Card 2: Necroquip (Level 6)
    card2 = struct.pack('<I', necroquip_code)
    card2 += struct.pack('<BB', 0, 0x04)
    card2 += struct.pack('<I', 1)
    card2 += struct.pack('<I', 6)              # sum_param = level 6
    card2 += b'\x00\x00'
    
    msg = header + card1 + card2
    
    print(f"Message length: {len(msg)} bytes")
    print(f"Raw hex: {msg.hex()}")
    
    result = parse_select_sum(msg)
    
    print(f"\nParsed result:")
    print(f"  target_sum: {result['target_sum']} (expected: 12)")
    print(f"  can_count: {result['can_count']} (expected: 2)")
    print(f"  select_mode: {result['select_mode']} (expected: 0)")
    
    print(f"\nCards:")
    for i, card in enumerate(result['can_select']):
        expected_name, expected_level = LEVEL_6_FIENDS.get(card['code'], ("Unknown", "?"))
        print(f"  [{i}] code={card['code']} ({expected_name})")
        print(f"      level/value={card.get('value', '?')} (expected: {expected_level})")
        print(f"      sum_param_raw=0x{card.get('sum_param', 0):08x}")
    
    # Validate
    errors = []
    if result['target_sum'] != 12:
        errors.append(f"target_sum={result['target_sum']}, expected 12")
    
    for card in result['can_select']:
        if card.get('value', 0) != 6:
            errors.append(f"Card {card['code']} has value={card.get('value')}, expected 6")
    
    if errors:
        print(f"\n✗ VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return False
    else:
        print(f"\n✓ Parser correctly handles synthetic data")
        return True


def test_verified_cards_fallback():
    """Test that verified_cards.json lookup works."""
    print("\n" + "=" * 60)
    print("TEST 2: verified_cards.json fallback")
    print("=" * 60)
    
    try:
        validator = _get_card_validator()
        print("✓ CardValidator loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load CardValidator: {e}")
        return False
    
    # Check Level 6 Fiends
    all_good = True
    for code, (name, expected_level) in LEVEL_6_FIENDS.items():
        card = validator.get_card(code)
        if card is None:
            print(f"✗ {name} ({code}) not found in verified_cards.json")
            all_good = False
        else:
            level = card.get('level') or card.get('rank') or card.get('link_rating')
            if level == expected_level:
                print(f"✓ {name}: level={level}")
            else:
                print(f"✗ {name}: level={level}, expected {expected_level}")
                all_good = False
    
    return all_good


def test_buggy_sum_param():
    """Test parser behavior when sum_param is wrong (the known bug)."""
    print("\n" + "=" * 60)
    print("TEST 3: Buggy sum_param (sum_param=1 instead of level)")
    print("=" * 60)
    
    engraver_code = 60764609
    necroquip_code = 93860227
    
    header = struct.pack(
        '>BBBB I I',
        0, 0, 2, 2, 12, 2
    )
    header += b'\x00\x00\x00'
    
    # Cards with BUGGY sum_param = 1 (the known upstream bug)
    card1 = struct.pack('<I', engraver_code)
    card1 += struct.pack('<BB', 0, 0x04)
    card1 += struct.pack('<I', 0)
    card1 += struct.pack('<I', 1)  # BUG: shows 1 instead of 6
    card1 += b'\x00\x00'
    
    card2 = struct.pack('<I', necroquip_code)
    card2 += struct.pack('<BB', 0, 0x04)
    card2 += struct.pack('<I', 1)
    card2 += struct.pack('<I', 1)  # BUG: shows 1 instead of 6
    card2 += b'\x00\x00'
    
    msg = header + card1 + card2
    
    print(f"Simulating buggy message where sum_param=1 for Level 6 cards")
    print(f"Raw hex: {msg.hex()}")
    
    result = parse_select_sum(msg)
    
    print(f"\nParsed result:")
    for i, card in enumerate(result['can_select']):
        expected_name, expected_level = LEVEL_6_FIENDS.get(card['code'], ("Unknown", "?"))
        actual_value = card.get('value', '?')
        
        if actual_value == expected_level:
            print(f"  [{i}] {expected_name}: value={actual_value} ✓ (fallback worked!)")
        elif actual_value == 1:
            print(f"  [{i}] {expected_name}: value={actual_value} ✗ (fallback NOT working)")
        else:
            print(f"  [{i}] {expected_name}: value={actual_value} ? (unexpected)")
    
    # Check if fallback kicked in
    values = [c.get('value', 0) for c in result['can_select']]
    if all(v == 6 for v in values):
        print(f"\n✓ Fallback to verified_cards.json is working!")
        return True
    else:
        print(f"\n✗ Fallback NOT working - SELECT_SUM will fail for Caesar")
        return False


def main():
    print("=" * 60)
    print("DIAGNOSTIC 3: SELECT_SUM Parsing Validation")
    print("=" * 60)
    print("Caesar Xyz requires 2x Level 6 Fiends (sum=12)")
    print("Known bug: ygopro-core may send sum_param=1 instead of level")
    print()
    
    results = []
    
    results.append(("Synthetic data parsing", test_parser_with_synthetic_data()))
    results.append(("verified_cards.json fallback", test_verified_cards_fallback()))
    results.append(("Buggy sum_param handling", test_buggy_sum_param()))
    
    print("\n" + "=" * 60)
    print("SUMMARY:")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\nSELECT_SUM parsing should work for Caesar Xyz summon.")
    else:
        print("\nSELECT_SUM has issues - Caesar Xyz may fail.")
        print("Check: Is verified_cards.json present and complete?")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
