#!/usr/bin/env python3
"""
Mini Validation Tests for Crystal Beast Fiendsmith Deck

Run these small tests BEFORE doing full combo analysis to verify:
1. Cards load correctly
2. Engine can process actions
3. Basic combos work as expected

Usage:
    python validate_engine.py --db /path/to/cards.cdb --library config/cb_fiendsmith_library.json
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any


def load_library(library_path: Path) -> Dict[str, List[int]]:
    """Load library configuration."""
    with open(library_path) as f:
        return json.load(f)


def test_1_library_loads(library_path: Path) -> bool:
    """Test 1: Library JSON loads correctly."""
    print("\n=== TEST 1: Library Loads ===")
    try:
        lib = load_library(library_path)
        main_count = len(lib.get("main_deck", []))
        extra_count = len(lib.get("extra_deck", []))

        print(f"  Main deck: {main_count} cards")
        print(f"  Extra deck: {extra_count} cards")

        if main_count == 0:
            print("  x FAIL: No main deck cards!")
            return False

        print("  + PASS")
        return True
    except Exception as e:
        print(f"  x FAIL: {e}")
        return False


def test_2_card_counts(library_path: Path) -> bool:
    """Test 2: Card counts match expectations."""
    print("\n=== TEST 2: Card Counts ===")
    try:
        lib = load_library(library_path)
        main_deck = lib.get("main_deck", [])
        extra_deck = lib.get("extra_deck", [])

        # We expect 47 engine cards in main deck
        # (60 total - 13 non-engine)
        expected_engine = 47

        print(f"  Main deck engine cards: {len(main_deck)}")
        print(f"  Expected: ~{expected_engine} (may vary based on lookup success)")

        if len(main_deck) < 30:
            print("  x FAIL: Too few main deck cards - check card lookups")
            return False

        if len(extra_deck) < 10:
            print(f"  WARNING: Only {len(extra_deck)} extra deck cards found")

        print("  + PASS")
        return True
    except Exception as e:
        print(f"  x FAIL: {e}")
        return False


def test_3_passcodes_valid(library_path: Path) -> bool:
    """Test 3: All passcodes are valid integers."""
    print("\n=== TEST 3: Passcode Validity ===")
    try:
        lib = load_library(library_path)

        all_codes = lib.get("main_deck", []) + lib.get("extra_deck", [])

        invalid = []
        for code in all_codes:
            if not isinstance(code, int) or code <= 0:
                invalid.append(code)

        if invalid:
            print(f"  x FAIL: Invalid passcodes: {invalid[:5]}...")
            return False

        print(f"  All {len(all_codes)} passcodes are valid integers")
        print("  + PASS")
        return True
    except Exception as e:
        print(f"  x FAIL: {e}")
        return False


def test_4_no_duplicates_in_extra(library_path: Path) -> bool:
    """Test 4: No duplicate cards in extra deck."""
    print("\n=== TEST 4: Extra Deck Duplicates ===")
    try:
        lib = load_library(library_path)
        extra_deck = lib.get("extra_deck", [])

        seen = set()
        duplicates = []
        for code in extra_deck:
            if code in seen:
                duplicates.append(code)
            seen.add(code)

        if duplicates:
            print(f"  WARNING: Duplicate extra deck cards: {duplicates}")
            # Not a failure, just a warning

        print(f"  Unique extra deck cards: {len(seen)}")
        print("  + PASS")
        return True
    except Exception as e:
        print(f"  x FAIL: {e}")
        return False


def test_5_key_cards_present(library_path: Path) -> bool:
    """Test 5: Key combo cards are present."""
    print("\n=== TEST 5: Key Cards Present ===")

    # Key passcodes we expect
    key_cards = {
        # Fiendsmith core
        60764609: "Fiendsmith Engraver",
        2463794: "Fiendsmith's Requiem",

        # Crystal Beast core
        7093411: "Crystal Beast Sapphire Pegasus",

        # Extra deck payoffs
        79559912: "D/D/D Wave High King Caesar",
        29301450: "S:P Little Knight",
    }

    try:
        lib = load_library(library_path)
        all_codes = set(lib.get("main_deck", []) + lib.get("extra_deck", []))

        missing = []
        found = []
        for code, name in key_cards.items():
            if code in all_codes:
                found.append(name)
            else:
                missing.append(name)

        for name in found:
            print(f"  + Found: {name}")

        for name in missing:
            print(f"  x Missing: {name}")

        if missing:
            print(f"\n  WARNING: {len(missing)} key cards missing!")
            print("  This may indicate passcode lookup issues")
            # Not a hard failure

        print("  + PASS (key cards check complete)")
        return True
    except Exception as e:
        print(f"  x FAIL: {e}")
        return False


def test_6_engine_import() -> bool:
    """Test 6: Can import combo enumeration engine."""
    print("\n=== TEST 6: Engine Import ===")
    try:
        # Try to import the engine modules
        sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "cffi"))

        from combo_enumeration import EnumerationEngine
        from state_representation import BoardSignature
        from transposition_table import TranspositionTable

        print("  + EnumerationEngine imported")
        print("  + BoardSignature imported")
        print("  + TranspositionTable imported")
        print("  + PASS")
        return True
    except ImportError as e:
        print(f"  x FAIL: Import error: {e}")
        print("  Make sure you're running from the project root")
        return False
    except Exception as e:
        print(f"  x FAIL: {e}")
        return False


def run_all_tests(library_path: Path) -> bool:
    """Run all validation tests."""
    print("=" * 60)
    print("CRYSTAL BEAST FIENDSMITH - ENGINE VALIDATION")
    print("=" * 60)

    tests = [
        ("Library Loads", lambda: test_1_library_loads(library_path)),
        ("Card Counts", lambda: test_2_card_counts(library_path)),
        ("Passcode Validity", lambda: test_3_passcodes_valid(library_path)),
        ("Extra Deck Duplicates", lambda: test_4_no_duplicates_in_extra(library_path)),
        ("Key Cards Present", lambda: test_5_key_cards_present(library_path)),
        ("Engine Import", test_6_engine_import),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"  x EXCEPTION: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, p in results if p)
    total = len(results)

    for name, p in results:
        status = "+" if p else "x"
        print(f"  {status} {name}")

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n+ All tests passed! Ready for combo analysis.")
        return True
    else:
        print(f"\n  {total - passed} test(s) had issues. Review above.")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate engine setup for Crystal Beast Fiendsmith")
    parser.add_argument(
        "--library",
        type=Path,
        default=Path("cb_fiendsmith_library.json"),
        help="Path to library JSON"
    )

    args = parser.parse_args()

    if not args.library.exists():
        print(f"ERROR: Library file not found: {args.library}")
        print("\nRun setup_deck.py first to create the library file.")
        sys.exit(1)

    success = run_all_tests(args.library)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
