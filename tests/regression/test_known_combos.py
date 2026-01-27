"""
Regression tests for combo enumeration.

These tests ensure that refactoring doesn't break existing functionality.
They capture known behavior and alert when results change.

Run with: pytest tests/regression/ -v
"""
import pytest
import os

# Skip all tests if YGOPRO_SCRIPTS_PATH not set (CI environment)
pytestmark = pytest.mark.skipif(
    not os.environ.get("YGOPRO_SCRIPTS_PATH"),
    reason="YGOPRO_SCRIPTS_PATH not set - skipping engine tests"
)


# =============================================================================
# TEST CONFIGURATION
# =============================================================================

# Max paths to explore (keep low for fast tests)
MAX_PATHS = 5000
MAX_DEPTH = 20

# Known test hands
ENGRAVER_HAND = [60764609, 14558127, 14558127, 14558127, 94145021]  # Engraver + 4 dead
BRICK_HAND = [14558127, 14558127, 14558127, 94145021, 94145021]     # All hand traps


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture(scope="module")
def engine_setup():
    """Initialize engine once per test module."""
    from src.ygo_combo.engine.interface import init_card_database, load_library, set_lib
    from src.ygo_combo.engine.duel_factory import load_locked_library, get_deck_lists

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
    from src.ygo_combo.combo_enumeration import EnumerationEngine
    import src.ygo_combo.combo_enumeration as combo_enumeration

    combo_enumeration.MAX_PATHS = MAX_PATHS
    combo_enumeration.MAX_DEPTH = MAX_DEPTH

    engine = EnumerationEngine(
        engine_setup["lib"],
        engine_setup["main_deck"],
        engine_setup["extra_deck"],
        verbose=False,
    )
    return engine


# =============================================================================
# DETERMINISM TESTS
# =============================================================================

class TestEnumerationDeterminism:
    """Verify enumeration produces consistent results."""

    def test_same_hand_same_results(self, enumeration_engine):
        """Same hand should produce same number of terminals."""
        # Run enumeration twice
        terminals1 = enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        # Create fresh engine for second run
        from combo_enumeration import EnumerationEngine
        import combo_enumeration

        engine2 = EnumerationEngine(
            enumeration_engine.lib,
            enumeration_engine.main_deck,
            enumeration_engine.extra_deck,
            verbose=False,
        )
        terminals2 = engine2.enumerate_from_hand(ENGRAVER_HAND)

        assert len(terminals1) == len(terminals2), \
            f"Enumeration not deterministic: {len(terminals1)} vs {len(terminals2)} terminals"

    def test_brick_hand_minimal_terminals(self, enumeration_engine):
        """Hand with no starters should have very few terminals."""
        terminals = enumeration_engine.enumerate_from_hand(BRICK_HAND)

        # Brick hand should just pass with minimal exploration
        assert len(terminals) <= 5, \
            f"Brick hand produced too many terminals: {len(terminals)}"


# =============================================================================
# BASELINE METRICS TESTS
# =============================================================================

class TestBaselineMetrics:
    """Capture baseline metrics for regression detection."""

    def test_engraver_hand_terminal_count(self, enumeration_engine):
        """Engraver hand should find a minimum number of terminals."""
        terminals = enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        # Based on current observation: ~15 terminals
        # Allow some variance but catch major regressions
        assert len(terminals) >= 5, \
            f"Too few terminals found: {len(terminals)} (expected >= 5)"
        assert len(terminals) <= 100, \
            f"Too many terminals found: {len(terminals)} (expected <= 100)"

    def test_transposition_table_has_hits(self, enumeration_engine):
        """Transposition table should have cache hits."""
        enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        tt = enumeration_engine.transposition_table
        assert tt.hits > 0, "Transposition table had no hits - caching broken?"

    def test_transposition_table_stores(self, enumeration_engine):
        """Transposition table should have stores recorded."""
        enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        tt = enumeration_engine.transposition_table
        stats = tt.stats()
        assert stats["stores"] > 0, "No stores recorded"
        assert stats["size"] <= stats["stores"], "Size should not exceed stores"

    def test_paths_explored_reasonable(self, enumeration_engine):
        """Paths explored should be within expected range."""
        enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        paths = enumeration_engine.paths_explored
        assert paths >= 100, f"Too few paths explored: {paths}"
        assert paths <= MAX_PATHS, f"Exceeded max paths: {paths}"


# =============================================================================
# STRUCTURE TESTS
# =============================================================================

class TestTerminalStructure:
    """Verify terminal states have expected structure."""

    def test_terminal_has_required_fields(self, enumeration_engine):
        """Each terminal should have action_sequence, board_state, depth."""
        terminals = enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        assert len(terminals) > 0, "No terminals to check"

        for term in terminals:
            assert hasattr(term, 'action_sequence'), "Missing action_sequence"
            assert hasattr(term, 'board_state'), "Missing board_state"
            assert hasattr(term, 'depth'), "Missing depth"
            assert term.depth > 0, "Terminal depth should be positive"

    def test_board_state_has_player_zones(self, enumeration_engine):
        """Board state should have player0 with expected zones."""
        terminals = enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        for term in terminals:
            board = term.board_state
            assert 'player0' in board, "Missing player0 in board_state"

            p0 = board['player0']
            expected_zones = ['monsters', 'spells', 'graveyard', 'hand']
            for zone in expected_zones:
                assert zone in p0, f"Missing zone: {zone}"


# =============================================================================
# TRANSPOSITION TABLE INSTRUMENTATION TESTS
# =============================================================================

class TestTranspositionTableInstrumentation:
    """Verify transposition table metrics are captured correctly."""

    def test_stats_structure(self, enumeration_engine):
        """Stats dict should have all expected fields."""
        enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        stats = enumeration_engine.transposition_table.stats()
        required_fields = [
            "size", "max_size", "hits", "misses", "hit_rate",
            "stores", "overwrites", "evictions", "evicted_entries",
            "depth_distribution", "avg_depth", "max_visits", "avg_visits"
        ]
        for field in required_fields:
            assert field in stats, f"Missing field: {field}"

    def test_hit_rate_reasonable(self, enumeration_engine):
        """Hit rate should be between 0 and 1."""
        enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        stats = enumeration_engine.transposition_table.stats()
        assert 0.0 <= stats["hit_rate"] <= 1.0, f"Invalid hit rate: {stats['hit_rate']}"

    def test_depth_distribution_nonempty(self, enumeration_engine):
        """Depth distribution should have entries after enumeration."""
        enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        stats = enumeration_engine.transposition_table.stats()
        assert len(stats["depth_distribution"]) > 0, "Empty depth distribution"

    def test_no_evictions_under_limit(self, enumeration_engine):
        """With small path count, should not trigger evictions."""
        enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        stats = enumeration_engine.transposition_table.stats()
        # With MAX_PATHS=5000, we shouldn't hit 1M entry limit
        assert stats["evictions"] == 0, f"Unexpected evictions: {stats['evictions']}"


# =============================================================================
# CARD VALIDATION TESTS
# =============================================================================

class TestCardValidation:
    """Verify cards in results are valid."""

    def test_no_unknown_cards_in_monsters(self, enumeration_engine):
        """All monster codes should be valid passcodes."""
        terminals = enumeration_engine.enumerate_from_hand(ENGRAVER_HAND)

        for term in terminals:
            monsters = term.board_state.get('player0', {}).get('monsters', [])
            for monster in monsters:
                code = monster.get('code', 0)
                assert code > 0, f"Invalid monster code: {code}"
                assert code < 100000000, f"Suspiciously large code: {code}"
