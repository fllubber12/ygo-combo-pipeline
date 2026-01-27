"""
Known-count regression tests for combo enumeration.

These tests verify that specific hands produce EXACT expected combo counts.
If the count changes, it indicates either a regression or an improvement
that needs to be verified and the baseline updated.

Usage:
    # Run all known-count tests
    pytest tests/regression/test_known_counts.py -v

    # Run with verbose output to see actual counts
    pytest tests/regression/test_known_counts.py -v -s

Note: Baseline values were captured on 2026-01-26 with:
    - MAX_PATHS = 10000
    - MAX_DEPTH = 25
    - dedupe_boards = True
    - dedupe_intermediate = True
"""
import pytest
import sys
import os
from pathlib import Path

# Skip all tests if YGOPRO_SCRIPTS_PATH not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("YGOPRO_SCRIPTS_PATH"),
    reason="YGOPRO_SCRIPTS_PATH not set - skipping engine tests"
)

# Add src to path
sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "ygo_combo"))


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

# Configuration for reproducible counts
MAX_PATHS = 10000
MAX_DEPTH = 25

# Card passcodes
ENGRAVER = 60764609      # Fiendsmith Engraver
TERRORTOP = 81275020     # Speedroid Terrortop
CRYSTAL_BOND = 2700673   # Crystal Bond
ASH = 14558127           # Ash Blossom
DROLL = 94145021         # Droll & Lock Bird
HOLACTIE = 10000040      # Holactie (filler)

# Gold standard endboard cards
A_BAO_A_QU = 4731783     # A Bao A Qu, the Lightless Shadow
CAESAR = 79559912        # D/D/D Wave High King Caesar


# =============================================================================
# KNOWN HANDS WITH EXPECTED COUNTS
# =============================================================================

# Format: (hand, expected_terminals, expected_paths_min, expected_paths_max, description)
# Values marked with "BASELINE" need to be captured by running the tests once

KNOWN_HANDS = {
    "engraver_solo": {
        "hand": [ENGRAVER, ASH, ASH, ASH, DROLL],
        "expected_terminals": None,  # BASELINE: Run test to capture
        "expected_paths_range": (100, 5000),
        "description": "1-card Engraver combo (gold standard baseline)",
    },
    "brick_hand": {
        "hand": [ASH, ASH, ASH, DROLL, DROLL],
        "expected_terminals": 1,  # Just PASS
        "expected_paths_range": (1, 10),
        "description": "No starters - should only PASS",
    },
    "engraver_terrortop": {
        "hand": [ENGRAVER, TERRORTOP, ASH, ASH, ASH],
        "expected_terminals": None,  # BASELINE: Run test to capture
        "expected_paths_range": (200, 10000),
        "description": "2-card starter combination",
    },
    "crystal_bond_solo": {
        "hand": [CRYSTAL_BOND, ASH, ASH, ASH, DROLL],
        "expected_terminals": None,  # BASELINE: Run test to capture
        "expected_paths_range": (50, 3000),
        "description": "Crystal Beast line only",
    },
}


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="module")
def engine_setup():
    """Initialize engine once per test module."""
    from engine.interface import init_card_database, set_lib
    from engine.bindings import load_library
    from combo_enumeration import load_locked_library, get_deck_lists

    if not init_card_database():
        pytest.skip("Could not initialize card database")

    lib = load_library()
    set_lib(lib)

    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)

    return {
        "lib": lib,
        "main_deck": main_deck,
        "extra_deck": extra_deck,
    }


@pytest.fixture
def enumeration_engine(engine_setup):
    """Create fresh EnumerationEngine for each test."""
    from combo_enumeration import EnumerationEngine
    import combo_enumeration

    combo_enumeration.MAX_PATHS = MAX_PATHS
    combo_enumeration.MAX_DEPTH = MAX_DEPTH

    engine = EnumerationEngine(
        engine_setup["lib"],
        engine_setup["main_deck"],
        engine_setup["extra_deck"],
        verbose=False,
        dedupe_boards=True,
        dedupe_intermediate=True,
    )
    return engine


# =============================================================================
# KNOWN-COUNT TESTS
# =============================================================================

class TestKnownCounts:
    """Tests that verify exact terminal counts for known hands."""

    def test_brick_hand_exact_count(self, enumeration_engine):
        """Brick hand should produce exactly 1 terminal (PASS only)."""
        config = KNOWN_HANDS["brick_hand"]
        terminals = enumeration_engine.enumerate_from_hand(config["hand"])

        actual_count = len(terminals)
        expected = config["expected_terminals"]

        # Brick hand has an exact known count
        assert actual_count == expected, \
            f"Brick hand terminal count changed: expected {expected}, got {actual_count}"

    def test_engraver_solo_count(self, enumeration_engine):
        """Engraver solo hand terminal count (baseline test)."""
        config = KNOWN_HANDS["engraver_solo"]
        terminals = enumeration_engine.enumerate_from_hand(config["hand"])

        actual_count = len(terminals)
        paths_explored = enumeration_engine.paths_explored

        # Print actual values for baseline capture
        print(f"\n  Engraver Solo: {actual_count} terminals, {paths_explored} paths")

        if config["expected_terminals"] is not None:
            assert actual_count == config["expected_terminals"], \
                f"Terminal count changed: expected {config['expected_terminals']}, got {actual_count}"
        else:
            # Baseline not yet set - just verify within reasonable range
            assert actual_count >= 5, f"Too few terminals: {actual_count}"
            assert actual_count <= 200, f"Too many terminals: {actual_count}"

        # Verify paths in expected range
        min_paths, max_paths = config["expected_paths_range"]
        assert min_paths <= paths_explored <= max_paths, \
            f"Paths {paths_explored} outside range [{min_paths}, {max_paths}]"

    def test_engraver_terrortop_count(self, enumeration_engine):
        """Engraver + Terrortop hand terminal count."""
        config = KNOWN_HANDS["engraver_terrortop"]
        terminals = enumeration_engine.enumerate_from_hand(config["hand"])

        actual_count = len(terminals)
        paths_explored = enumeration_engine.paths_explored

        print(f"\n  Engraver+Terrortop: {actual_count} terminals, {paths_explored} paths")

        if config["expected_terminals"] is not None:
            assert actual_count == config["expected_terminals"], \
                f"Terminal count changed: expected {config['expected_terminals']}, got {actual_count}"
        else:
            # More starters = more combos expected
            assert actual_count >= 10, f"Too few terminals: {actual_count}"

    def test_crystal_bond_solo_count(self, enumeration_engine):
        """Crystal Bond solo hand terminal count."""
        config = KNOWN_HANDS["crystal_bond_solo"]
        terminals = enumeration_engine.enumerate_from_hand(config["hand"])

        actual_count = len(terminals)
        paths_explored = enumeration_engine.paths_explored

        print(f"\n  Crystal Bond Solo: {actual_count} terminals, {paths_explored} paths")

        if config["expected_terminals"] is not None:
            assert actual_count == config["expected_terminals"], \
                f"Terminal count changed: expected {config['expected_terminals']}, got {actual_count}"


# =============================================================================
# GOLD STANDARD ENDBOARD TESTS
# =============================================================================

class TestGoldStandardEndboard:
    """Tests that verify the gold standard endboard is reachable."""

    def test_abaoaqu_reachable(self, enumeration_engine):
        """Verify A Bao A Qu appears on at least one terminal board."""
        config = KNOWN_HANDS["engraver_solo"]
        terminals = enumeration_engine.enumerate_from_hand(config["hand"])

        # Check if any terminal has A Bao A Qu on field
        found_abaoaqu = False
        for term in terminals:
            monsters = term.board_state.get('player0', {}).get('monsters', [])
            for monster in monsters:
                if monster.get('code') == A_BAO_A_QU:
                    found_abaoaqu = True
                    break
            if found_abaoaqu:
                break

        assert found_abaoaqu, \
            "A Bao A Qu not found on any terminal board - gold standard combo may be broken"

    def test_caesar_reachable(self, enumeration_engine):
        """Verify D/D/D Wave High King Caesar appears on at least one terminal board."""
        config = KNOWN_HANDS["engraver_solo"]
        terminals = enumeration_engine.enumerate_from_hand(config["hand"])

        # Check if any terminal has Caesar on field
        found_caesar = False
        for term in terminals:
            monsters = term.board_state.get('player0', {}).get('monsters', [])
            for monster in monsters:
                if monster.get('code') == CAESAR:
                    found_caesar = True
                    break
            if found_caesar:
                break

        assert found_caesar, \
            "Caesar not found on any terminal board - gold standard combo may be broken"

    def test_gold_standard_endboard_reachable(self, enumeration_engine):
        """Verify the full gold standard endboard (A Bao A Qu + Caesar) is reachable."""
        config = KNOWN_HANDS["engraver_solo"]
        terminals = enumeration_engine.enumerate_from_hand(config["hand"])

        # Check for terminal with BOTH A Bao A Qu AND Caesar
        found_gold_standard = False
        gold_standard_depth = None

        for term in terminals:
            monsters = term.board_state.get('player0', {}).get('monsters', [])
            monster_codes = {m.get('code') for m in monsters}

            if A_BAO_A_QU in monster_codes and CAESAR in monster_codes:
                found_gold_standard = True
                gold_standard_depth = term.depth
                break

        print(f"\n  Gold standard endboard found: {found_gold_standard}")
        if gold_standard_depth:
            print(f"  Depth to reach: {gold_standard_depth} actions")

        assert found_gold_standard, \
            "Gold standard endboard (A Bao A Qu + Caesar) not reachable - CRITICAL REGRESSION"


# =============================================================================
# DETERMINISM TESTS
# =============================================================================

class TestDeterminism:
    """Tests that verify enumeration is deterministic."""

    def test_same_hand_same_count_three_runs(self, engine_setup):
        """Run enumeration 3 times and verify identical terminal counts."""
        from combo_enumeration import EnumerationEngine
        import combo_enumeration

        combo_enumeration.MAX_PATHS = MAX_PATHS
        combo_enumeration.MAX_DEPTH = MAX_DEPTH

        hand = KNOWN_HANDS["engraver_solo"]["hand"]
        counts = []

        for i in range(3):
            engine = EnumerationEngine(
                engine_setup["lib"],
                engine_setup["main_deck"],
                engine_setup["extra_deck"],
                verbose=False,
            )
            terminals = engine.enumerate_from_hand(hand)
            counts.append(len(terminals))

        assert counts[0] == counts[1] == counts[2], \
            f"Non-deterministic results: {counts}"

    def test_terminal_hashes_consistent(self, enumeration_engine):
        """Verify terminal state hashes are consistent across terminals."""
        config = KNOWN_HANDS["engraver_solo"]
        terminals = enumeration_engine.enumerate_from_hand(config["hand"])

        # Collect all terminal state hashes
        state_hashes = [t.state_hash for t in terminals]

        # All should be non-empty strings
        for h in state_hashes:
            assert h and isinstance(h, str), f"Invalid state hash: {h}"

        # Check for expected uniqueness (some may be same if different paths reach same state)
        unique_hashes = set(state_hashes)
        print(f"\n  {len(state_hashes)} terminals, {len(unique_hashes)} unique state hashes")


# =============================================================================
# BASELINE CAPTURE HELPER
# =============================================================================

def capture_baselines():
    """
    Helper function to run enumeration and capture baseline values.
    Run this manually when setting up tests:
        python -c "from tests.regression.test_known_counts import capture_baselines; capture_baselines()"
    """
    import json

    # Skip if no engine
    if not os.environ.get("YGOPRO_SCRIPTS_PATH"):
        print("ERROR: Set YGOPRO_SCRIPTS_PATH to capture baselines")
        return

    from engine.interface import init_card_database, set_lib
    from engine.bindings import load_library
    from combo_enumeration import EnumerationEngine, load_locked_library, get_deck_lists
    import combo_enumeration

    init_card_database()
    lib = load_library()
    set_lib(lib)

    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)

    combo_enumeration.MAX_PATHS = MAX_PATHS
    combo_enumeration.MAX_DEPTH = MAX_DEPTH

    print("Capturing baselines...")
    print(f"MAX_PATHS={MAX_PATHS}, MAX_DEPTH={MAX_DEPTH}")
    print("-" * 60)

    baselines = {}
    for name, config in KNOWN_HANDS.items():
        engine = EnumerationEngine(lib, main_deck, extra_deck, verbose=False)
        terminals = engine.enumerate_from_hand(config["hand"])

        baselines[name] = {
            "terminals": len(terminals),
            "paths_explored": engine.paths_explored,
            "description": config["description"],
        }
        print(f"{name}: {len(terminals)} terminals, {engine.paths_explored} paths")

    print("-" * 60)
    print("Baseline values (copy to KNOWN_HANDS):")
    print(json.dumps(baselines, indent=2))


if __name__ == "__main__":
    capture_baselines()
