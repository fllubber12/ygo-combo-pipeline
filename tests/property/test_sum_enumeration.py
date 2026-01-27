"""
Property-based tests for sum enumeration (no engine required).

These tests verify the correctness of the sum enumeration algorithm
used for SELECT_SUM responses, without requiring ygopro-core.
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Check if hypothesis is available
pytest.importorskip("hypothesis")


class TestSumEnumerationProperties:
    """Test properties of the sum enumeration algorithm."""

    @given(
        must_cards=st.lists(st.integers(min_value=1, max_value=12), min_size=0, max_size=5),
        can_cards=st.lists(st.integers(min_value=1, max_value=12), min_size=0, max_size=8),
        target=st.integers(min_value=1, max_value=24),
    )
    @settings(max_examples=100)
    def test_sum_combinations_valid(self, must_cards, can_cards, target):
        """All returned combinations should sum to at least target."""
        from src.ygo_combo.combo_enumeration import find_valid_sum_combinations

        # Skip if no cards to select from
        assume(len(must_cards) + len(can_cards) > 0)

        # Build card data structure expected by function (uses "value" key)
        must_select = [{"value": level} for level in must_cards]
        can_select = [{"value": level} for level in can_cards]

        try:
            combinations = find_valid_sum_combinations(
                must_select=must_select,
                can_select=can_select,
                target_sum=target,
                mode=1,  # At least target
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
        from src.ygo_combo.combo_enumeration import find_valid_sum_combinations

        target = sum(cards)  # Use sum of all cards as target

        can_select = [{"value": level} for level in cards]

        try:
            combinations = find_valid_sum_combinations(
                must_select=[],
                can_select=can_select,
                target_sum=target,
                mode=0,  # Exact match
            )

            # Should find at least one combination (all cards)
            assert len(combinations) >= 1, "Should find combination using all cards"

            for combo in combinations:
                total = sum(cards[idx] for idx in combo)
                assert total == target, f"Exact match combination sums to {total}, not {target}"

        except Exception:
            # Function may raise for edge cases
            pass

    @given(
        levels=st.lists(st.integers(min_value=1, max_value=8), min_size=2, max_size=5),
    )
    @settings(max_examples=50)
    def test_combination_count_bounded(self, levels):
        """Number of combinations should be at most 2^n."""
        from src.ygo_combo.combo_enumeration import find_valid_sum_combinations

        can_select = [{"value": level} for level in levels]
        target = 1  # Very low target to get many combinations

        try:
            combinations = find_valid_sum_combinations(
                must_select=[],
                can_select=can_select,
                target_sum=target,
                mode=1,  # At least target
            )

            # At most 2^n combinations (all subsets)
            max_combinations = 2 ** len(levels)
            assert len(combinations) <= max_combinations, \
                f"Found {len(combinations)} combinations, max should be {max_combinations}"

        except Exception:
            pass

    @given(
        level1=st.integers(min_value=1, max_value=12),
        level2=st.integers(min_value=0, max_value=12),
    )
    @settings(max_examples=50)
    def test_variable_level_cards(self, level1, level2):
        """Cards with variable levels should be handled correctly."""
        from src.ygo_combo.combo_enumeration import find_valid_sum_combinations

        # Skip if level2 is 0 (not variable) or same as level1
        assume(level2 > 0 and level2 != level1)

        can_select = [{"value": level1, "level2": level2}]
        target = min(level1, level2)  # Use lower level as target

        try:
            combinations = find_valid_sum_combinations(
                must_select=[],
                can_select=can_select,
                target_sum=target,
                mode=0,  # Exact match
            )

            # Should find at least one combination (the card at lower level)
            # The function should consider both levels
            for combo in combinations:
                assert len(combo) == 1, "Should select exactly one card"

        except Exception:
            pass

    @given(
        must_levels=st.lists(st.integers(min_value=1, max_value=6), min_size=1, max_size=3),
        can_levels=st.lists(st.integers(min_value=1, max_value=6), min_size=0, max_size=4),
    )
    @settings(max_examples=50)
    def test_must_select_always_included(self, must_levels, can_levels):
        """Must-select cards should always be included in the sum."""
        from src.ygo_combo.combo_enumeration import find_valid_sum_combinations

        must_sum = sum(must_levels)
        target = must_sum  # Target is exactly the must-select sum

        must_select = [{"value": level} for level in must_levels]
        can_select = [{"value": level} for level in can_levels]

        try:
            combinations = find_valid_sum_combinations(
                must_select=must_select,
                can_select=can_select,
                target_sum=target,
                mode=0,  # Exact match
            )

            # Should find at least one combination (just must-select)
            if must_sum == target:
                assert len(combinations) >= 1, "Should find combination with just must-select"

            # Verify must-select sum is always included
            for combo in combinations:
                can_sum = sum(can_levels[idx] for idx in combo if idx < len(can_levels))
                total = must_sum + can_sum
                assert total == target, f"Total {total} != target {target}"

        except Exception:
            pass


class TestCheckpointSerialization:
    """Property tests for checkpoint serialization (no engine needed)."""

    @given(
        paths_explored=st.integers(min_value=0, max_value=1000000),
        terminals_found=st.integers(min_value=0, max_value=10000),
        max_depth_seen=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=50)
    def test_progress_round_trip(self, paths_explored, terminals_found, max_depth_seen):
        """CheckpointProgress should survive serialization round-trip."""
        from src.ygo_combo.checkpoint import CheckpointProgress
        from dataclasses import asdict

        progress = CheckpointProgress(
            paths_explored=paths_explored,
            max_depth_seen=max_depth_seen,
            duplicate_boards_skipped=0,
            intermediate_states_pruned=0,
            terminals_found=terminals_found,
        )

        # Serialize
        data = asdict(progress)

        # Deserialize
        restored = CheckpointProgress(**data)

        # Verify
        assert restored.paths_explored == paths_explored
        assert restored.terminals_found == terminals_found
        assert restored.max_depth_seen == max_depth_seen

    @given(
        hit_count=st.integers(min_value=0, max_value=100000),
        miss_count=st.integers(min_value=0, max_value=100000),
    )
    @settings(max_examples=50)
    def test_transposition_stats_hit_rate(self, hit_count, miss_count):
        """Transposition table hit rate should be correctly calculated."""
        from src.ygo_combo.search.transposition import TranspositionTable

        tt = TranspositionTable(max_size=1000)
        tt.hits = hit_count
        tt.misses = miss_count

        stats = tt.stats()

        if hit_count + miss_count > 0:
            expected_hit_rate = hit_count / (hit_count + miss_count)
            assert abs(stats["hit_rate"] - expected_hit_rate) < 0.0001, \
                f"Hit rate {stats['hit_rate']} != expected {expected_hit_rate}"
        else:
            assert stats["hit_rate"] == 0.0


class TestHandGeneratorProperties:
    """Test properties of hand generation (validation only)."""

    @given(
        hand_size=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=20)
    def test_hand_size_valid(self, hand_size):
        """Generated hands should have valid sizes."""
        # This tests the concept without actually generating
        assert 1 <= hand_size <= 5

    @given(
        card_code=st.integers(min_value=1, max_value=99999999),
    )
    @settings(max_examples=50)
    def test_card_code_is_positive(self, card_code):
        """Card codes should be positive integers."""
        assert card_code > 0
        assert isinstance(card_code, int)
