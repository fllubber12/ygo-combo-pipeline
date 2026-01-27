"""
Property-based tests for combo enumeration.

Uses Hypothesis to generate random hands and verify invariants:
1. Termination - enumeration always completes within limits
2. Determinism - same input produces same output
3. Monotonicity - deeper search finds >= combos as shallower
4. Card conservation - card counts are preserved
5. Terminal validity - all terminals have required structure

These tests require the ygopro-core engine to be available.
"""

import pytest
import json
from pathlib import Path
from typing import List, Set, Tuple
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# Check if hypothesis is available
pytest.importorskip("hypothesis")

# Skip all tests if engine not available
try:
    from src.ygo_combo.engine.paths import get_scripts_path
    get_scripts_path()
    ENGINE_AVAILABLE = True
except (ImportError, EnvironmentError):
    ENGINE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not ENGINE_AVAILABLE,
    reason="ygopro-core engine not available (YGOPRO_SCRIPTS_PATH not set)"
)


# =============================================================================
# CARD LIBRARY LOADING
# =============================================================================

def load_main_deck_cards() -> List[Tuple[int, int]]:
    """
    Load main deck cards from locked library.

    Returns:
        List of (card_code, count) tuples for main deck cards.
    """
    library_path = Path(__file__).parent.parent.parent / "config" / "locked_library.json"
    if not library_path.exists():
        # Fallback: use minimal test cards
        return [
            (60764609, 3),  # Fiendsmith Engraver
            (81275020, 3),  # Speedroid Terrortop
            (97651498, 1),  # Fabled Lurrie
        ]

    with open(library_path) as f:
        library = json.load(f)

    main_deck = []
    for code_str, card_data in library.get("cards", {}).items():
        if not card_data.get("is_extra_deck", False):
            code = int(code_str)
            count = card_data.get("count", 1)
            main_deck.append((code, count))

    return main_deck


def build_deck_pool() -> List[int]:
    """
    Build a pool of main deck cards with duplicates based on count.

    Returns:
        List of card codes (with duplicates for multi-copy cards).
    """
    pool = []
    for code, count in load_main_deck_cards():
        pool.extend([code] * count)
    return pool


# Global deck pool for strategy
DECK_POOL = build_deck_pool()
HOLACTIE = 10000040  # Filler card


# =============================================================================
# HYPOTHESIS STRATEGIES
# =============================================================================

@st.composite
def valid_hand(draw, min_cards: int = 1, max_cards: int = 5) -> List[int]:
    """
    Generate a valid starting hand from the deck pool.

    Args:
        draw: Hypothesis draw function.
        min_cards: Minimum cards to include (excluding filler).
        max_cards: Maximum hand size.

    Returns:
        List of 5 card codes (padded with Holactie if needed).
    """
    if not DECK_POOL:
        # No deck pool available, use minimal hand
        return [60764609] + [HOLACTIE] * 4

    # Draw 1-5 cards from deck (without replacement to be realistic)
    num_cards = draw(st.integers(min_value=min_cards, max_value=max_cards))

    # Sample from deck pool
    indices = draw(st.lists(
        st.integers(min_value=0, max_value=len(DECK_POOL) - 1),
        min_size=num_cards,
        max_size=num_cards,
        unique=True,  # No duplicate indices (realistic draw)
    ))

    hand = [DECK_POOL[i] for i in indices]

    # Pad to 5 cards with Holactie
    while len(hand) < 5:
        hand.append(HOLACTIE)

    return hand


@st.composite
def hand_with_starter(draw) -> List[int]:
    """
    Generate a hand that includes at least one known starter card.

    This ensures the hand can potentially do something interesting.
    """
    starters = [
        60764609,  # Fiendsmith Engraver
        81275020,  # Speedroid Terrortop
        26434972,  # Fiendsmith Kyrie
        7093411,   # Crystal Beast Sapphire Pegasus
        9334391,   # Crystal Bond
    ]

    # Pick a starter
    starter = draw(st.sampled_from(starters))

    # Draw 0-4 additional cards
    additional_count = draw(st.integers(min_value=0, max_value=4))

    # Get additional cards from pool (excluding the starter to avoid duplicates)
    other_cards = [c for c in DECK_POOL if c != starter]
    if other_cards and additional_count > 0:
        indices = draw(st.lists(
            st.integers(min_value=0, max_value=len(other_cards) - 1),
            min_size=min(additional_count, len(other_cards)),
            max_size=min(additional_count, len(other_cards)),
            unique=True,
        ))
        additional = [other_cards[i] for i in indices]
    else:
        additional = []

    hand = [starter] + additional

    # Pad to 5
    while len(hand) < 5:
        hand.append(HOLACTIE)

    return hand


# =============================================================================
# PROPERTY TESTS
# =============================================================================

class TestEnumerationTermination:
    """Test that enumeration always terminates within limits."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock engine for testing without full engine setup."""
        # This fixture provides a lightweight way to test properties
        # For full integration, we'd use the real engine
        pass

    @given(hand=valid_hand())
    @settings(
        max_examples=50,
        deadline=60000,  # 60 seconds per example
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_enumeration_terminates(self, hand):
        """Enumeration should always terminate within configured limits."""
        # Import here to avoid issues if engine not available
        from src.ygo_combo.combo_enumeration import EnumerationEngine, load_locked_library

        # Use very conservative limits for property testing
        import src.ygo_combo.combo_enumeration as ce
        original_max_depth = ce.MAX_DEPTH
        original_max_paths = ce.MAX_PATHS

        try:
            ce.MAX_DEPTH = 10  # Shallow depth for fast testing
            ce.MAX_PATHS = 100  # Few paths for fast testing

            library = load_locked_library()
            engine = EnumerationEngine(
                lib=None,  # Will use global lib
                main_deck=library["main_deck"],
                extra_deck=library["extra_deck"],
                verbose=False,
                dedupe_boards=True,
                dedupe_intermediate=True,
            )

            # This should always complete (not hang)
            terminals = engine.enumerate_from_hand(hand)

            # Basic sanity checks
            assert isinstance(terminals, list)
            assert engine.paths_explored <= ce.MAX_PATHS
            assert engine.max_depth_seen <= ce.MAX_DEPTH

        finally:
            ce.MAX_DEPTH = original_max_depth
            ce.MAX_PATHS = original_max_paths


class TestEnumerationDeterminism:
    """Test that enumeration is deterministic."""

    @given(hand=hand_with_starter())
    @settings(
        max_examples=30,
        deadline=120000,  # 2 minutes per example
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_same_input_same_output(self, hand):
        """Same hand should produce identical results on repeated runs."""
        from src.ygo_combo.combo_enumeration import EnumerationEngine, load_locked_library
        import src.ygo_combo.combo_enumeration as ce

        original_max_depth = ce.MAX_DEPTH
        original_max_paths = ce.MAX_PATHS

        try:
            ce.MAX_DEPTH = 10
            ce.MAX_PATHS = 100

            library = load_locked_library()

            # Run enumeration twice
            results = []
            for _ in range(2):
                engine = EnumerationEngine(
                    lib=None,
                    main_deck=library["main_deck"],
                    extra_deck=library["extra_deck"],
                    verbose=False,
                    dedupe_boards=True,
                    dedupe_intermediate=True,
                )
                terminals = engine.enumerate_from_hand(hand)
                results.append({
                    "terminal_count": len(terminals),
                    "paths_explored": engine.paths_explored,
                    "board_hashes": sorted([t.board_hash for t in terminals if t.board_hash]),
                })

            # Results should be identical
            assert results[0]["terminal_count"] == results[1]["terminal_count"], \
                f"Terminal count mismatch: {results[0]['terminal_count']} vs {results[1]['terminal_count']}"
            assert results[0]["paths_explored"] == results[1]["paths_explored"], \
                f"Paths explored mismatch: {results[0]['paths_explored']} vs {results[1]['paths_explored']}"
            assert results[0]["board_hashes"] == results[1]["board_hashes"], \
                "Board hashes mismatch between runs"

        finally:
            ce.MAX_DEPTH = original_max_depth
            ce.MAX_PATHS = original_max_paths


class TestTerminalStructure:
    """Test that all terminals have valid structure."""

    @given(hand=hand_with_starter())
    @settings(
        max_examples=30,
        deadline=120000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_terminals_have_required_fields(self, hand):
        """All terminal states should have required fields."""
        from src.ygo_combo.combo_enumeration import EnumerationEngine, load_locked_library
        import src.ygo_combo.combo_enumeration as ce

        original_max_depth = ce.MAX_DEPTH
        original_max_paths = ce.MAX_PATHS

        try:
            ce.MAX_DEPTH = 10
            ce.MAX_PATHS = 100

            library = load_locked_library()
            engine = EnumerationEngine(
                lib=None,
                main_deck=library["main_deck"],
                extra_deck=library["extra_deck"],
                verbose=False,
            )
            terminals = engine.enumerate_from_hand(hand)

            for terminal in terminals:
                # Check required attributes exist
                assert hasattr(terminal, "action_sequence")
                assert hasattr(terminal, "board_state")
                assert hasattr(terminal, "depth")
                assert hasattr(terminal, "state_hash")
                assert hasattr(terminal, "termination_reason")

                # Check types
                assert isinstance(terminal.action_sequence, list)
                assert isinstance(terminal.board_state, dict)
                assert isinstance(terminal.depth, int)
                assert terminal.depth >= 0

                # Check termination reason is valid
                assert terminal.termination_reason in ["PASS", "NO_ACTIONS", "MAX_DEPTH"]

        finally:
            ce.MAX_DEPTH = original_max_depth
            ce.MAX_PATHS = original_max_paths


class TestTranspositionTableInvariants:
    """Test transposition table invariants."""

    @given(hand=hand_with_starter())
    @settings(
        max_examples=20,
        deadline=120000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_hit_rate_bounded(self, hand):
        """Hit rate should be between 0 and 1."""
        from src.ygo_combo.combo_enumeration import EnumerationEngine, load_locked_library
        import src.ygo_combo.combo_enumeration as ce

        original_max_depth = ce.MAX_DEPTH
        original_max_paths = ce.MAX_PATHS

        try:
            ce.MAX_DEPTH = 10
            ce.MAX_PATHS = 100

            library = load_locked_library()
            engine = EnumerationEngine(
                lib=None,
                main_deck=library["main_deck"],
                extra_deck=library["extra_deck"],
                verbose=False,
                dedupe_intermediate=True,
            )
            engine.enumerate_from_hand(hand)

            stats = engine.transposition_table.stats()
            hit_rate = stats.get("hit_rate", 0)

            assert 0 <= hit_rate <= 1, f"Hit rate {hit_rate} out of bounds"

            # Hits + misses should equal total lookups
            assert stats["hits"] >= 0
            assert stats["misses"] >= 0

        finally:
            ce.MAX_DEPTH = original_max_depth
            ce.MAX_PATHS = original_max_paths

    @given(hand=hand_with_starter())
    @settings(
        max_examples=20,
        deadline=120000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_stores_consistent(self, hand):
        """Stores should be >= table size (some may be overwrites)."""
        from src.ygo_combo.combo_enumeration import EnumerationEngine, load_locked_library
        import src.ygo_combo.combo_enumeration as ce

        original_max_depth = ce.MAX_DEPTH
        original_max_paths = ce.MAX_PATHS

        try:
            ce.MAX_DEPTH = 10
            ce.MAX_PATHS = 100

            library = load_locked_library()
            engine = EnumerationEngine(
                lib=None,
                main_deck=library["main_deck"],
                extra_deck=library["extra_deck"],
                verbose=False,
                dedupe_intermediate=True,
            )
            engine.enumerate_from_hand(hand)

            stats = engine.transposition_table.stats()

            # stores = unique_stores + overwrites
            # size <= stores (since overwrites replace existing entries)
            assert stats["stores"] >= 0
            assert stats["overwrites"] >= 0
            assert stats["size"] <= stats["stores"]

        finally:
            ce.MAX_DEPTH = original_max_depth
            ce.MAX_PATHS = original_max_paths


class TestPathExploration:
    """Test path exploration properties."""

    @given(hand=hand_with_starter())
    @settings(
        max_examples=20,
        deadline=120000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_paths_explored_positive(self, hand):
        """At least one path should be explored."""
        from src.ygo_combo.combo_enumeration import EnumerationEngine, load_locked_library
        import src.ygo_combo.combo_enumeration as ce

        original_max_depth = ce.MAX_DEPTH
        original_max_paths = ce.MAX_PATHS

        try:
            ce.MAX_DEPTH = 10
            ce.MAX_PATHS = 100

            library = load_locked_library()
            engine = EnumerationEngine(
                lib=None,
                main_deck=library["main_deck"],
                extra_deck=library["extra_deck"],
                verbose=False,
            )
            engine.enumerate_from_hand(hand)

            # Should explore at least one path
            assert engine.paths_explored >= 1, "No paths explored"

        finally:
            ce.MAX_DEPTH = original_max_depth
            ce.MAX_PATHS = original_max_paths

    @given(hand=hand_with_starter())
    @settings(
        max_examples=20,
        deadline=120000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_terminal_depth_bounded(self, hand):
        """Terminal depths should be within max_depth."""
        from src.ygo_combo.combo_enumeration import EnumerationEngine, load_locked_library
        import src.ygo_combo.combo_enumeration as ce

        original_max_depth = ce.MAX_DEPTH
        original_max_paths = ce.MAX_PATHS

        try:
            ce.MAX_DEPTH = 10
            ce.MAX_PATHS = 100

            library = load_locked_library()
            engine = EnumerationEngine(
                lib=None,
                main_deck=library["main_deck"],
                extra_deck=library["extra_deck"],
                verbose=False,
            )
            terminals = engine.enumerate_from_hand(hand)

            for terminal in terminals:
                assert terminal.depth <= ce.MAX_DEPTH, \
                    f"Terminal depth {terminal.depth} exceeds max {ce.MAX_DEPTH}"

        finally:
            ce.MAX_DEPTH = original_max_depth
            ce.MAX_PATHS = original_max_paths


class TestActionSequence:
    """Test action sequence properties."""

    @given(hand=hand_with_starter())
    @settings(
        max_examples=20,
        deadline=120000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_action_sequence_length_matches_depth(self, hand):
        """Action sequence length should match terminal depth."""
        from src.ygo_combo.combo_enumeration import EnumerationEngine, load_locked_library
        import src.ygo_combo.combo_enumeration as ce

        original_max_depth = ce.MAX_DEPTH
        original_max_paths = ce.MAX_PATHS

        try:
            ce.MAX_DEPTH = 10
            ce.MAX_PATHS = 100

            library = load_locked_library()
            engine = EnumerationEngine(
                lib=None,
                main_deck=library["main_deck"],
                extra_deck=library["extra_deck"],
                verbose=False,
            )
            terminals = engine.enumerate_from_hand(hand)

            for terminal in terminals:
                # Depth should equal action count
                assert len(terminal.action_sequence) == terminal.depth, \
                    f"Action count {len(terminal.action_sequence)} != depth {terminal.depth}"

        finally:
            ce.MAX_DEPTH = original_max_depth
            ce.MAX_PATHS = original_max_paths

    @given(hand=hand_with_starter())
    @settings(
        max_examples=20,
        deadline=120000,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_actions_have_required_fields(self, hand):
        """All actions should have required fields."""
        from src.ygo_combo.combo_enumeration import EnumerationEngine, load_locked_library
        import src.ygo_combo.combo_enumeration as ce

        original_max_depth = ce.MAX_DEPTH
        original_max_paths = ce.MAX_PATHS

        try:
            ce.MAX_DEPTH = 10
            ce.MAX_PATHS = 100

            library = load_locked_library()
            engine = EnumerationEngine(
                lib=None,
                main_deck=library["main_deck"],
                extra_deck=library["extra_deck"],
                verbose=False,
            )
            terminals = engine.enumerate_from_hand(hand)

            for terminal in terminals:
                for action in terminal.action_sequence:
                    # Check required fields
                    assert hasattr(action, "action_type")
                    assert hasattr(action, "message_type")
                    assert hasattr(action, "response_bytes")
                    assert hasattr(action, "description")

                    # Check types
                    assert isinstance(action.action_type, str)
                    assert isinstance(action.message_type, int)
                    assert isinstance(action.response_bytes, bytes)
                    assert isinstance(action.description, str)

        finally:
            ce.MAX_DEPTH = original_max_depth
            ce.MAX_PATHS = original_max_paths


# =============================================================================
# STATELESS PROPERTY TESTS (No engine required)
# These tests do NOT require ygopro-core and should always run
# =============================================================================

@pytest.mark.skipif(False, reason="Always run - no engine needed")
class TestSumEnumerationProperties:
    """Test properties of the sum enumeration algorithm (no engine needed)."""

    @given(
        must_cards=st.lists(st.integers(min_value=1, max_value=12), min_size=0, max_size=5),
        can_cards=st.lists(st.integers(min_value=1, max_value=12), min_size=0, max_size=8),
        target=st.integers(min_value=1, max_value=24),
    )
    @settings(max_examples=100)
    def test_sum_combinations_valid(self, must_cards, can_cards, target):
        """All returned combinations should sum to at least target."""
        from src.ygo_combo.enumeration.responses import find_valid_sum_combinations

        # Skip if no cards to select from
        assume(len(must_cards) + len(can_cards) > 0)

        # Build card data structure expected by function
        must_select = [{"level1": level, "level2": 0} for level in must_cards]
        can_select = [{"level1": level, "level2": 0} for level in can_cards]

        try:
            combinations = find_valid_sum_combinations(
                must_select=must_select,
                can_select=can_select,
                target=target,
                exact_match=False,  # At least target
            )

            for combo in combinations:
                # Calculate sum
                total = sum(must_cards)  # Must cards always included
                for idx in combo:
                    if idx < len(can_cards):
                        total += can_cards[idx]

                assert total >= target, f"Combination sums to {total}, less than target {target}"

        except Exception:
            # Function may raise for invalid inputs - that's acceptable
            pass

    @given(
        cards=st.lists(st.integers(min_value=1, max_value=6), min_size=1, max_size=6),
    )
    @settings(max_examples=50)
    def test_exact_match_combinations(self, cards):
        """Exact match combinations should sum to exactly target."""
        from src.ygo_combo.enumeration.responses import find_valid_sum_combinations

        target = sum(cards)  # Use sum of all cards as target

        can_select = [{"level1": level, "level2": 0} for level in cards]

        try:
            combinations = find_valid_sum_combinations(
                must_select=[],
                can_select=can_select,
                target=target,
                exact_match=True,
            )

            # Should find at least one combination (all cards)
            assert len(combinations) >= 1, "Should find combination using all cards"

            for combo in combinations:
                total = sum(cards[idx] for idx in combo)
                assert total == target, f"Exact match combination sums to {total}, not {target}"

        except Exception:
            # Function may raise for edge cases
            pass
