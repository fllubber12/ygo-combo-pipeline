"""
Unit tests for enumeration/sum_utils.py.

Tests the pure sum combination algorithms used for Xyz/Synchro/Ritual material selection.
"""

import pytest
from math import comb
from src.ygo_combo.enumeration.sum_utils import (
    find_valid_sum_combinations,
    find_sum_combinations_flexible,
)


class TestFindValidSumCombinations:
    """Tests for find_valid_sum_combinations()."""

    # =========================================================================
    # Normal Cases
    # =========================================================================

    def test_xyz_rank6_two_materials(self):
        """Select 2 Level 6 monsters for Rank 6 Xyz (6+6=12)."""
        can_select = [{"value": 6}, {"value": 6}]
        result = find_valid_sum_combinations([], can_select, target_sum=12)
        assert result == [[0, 1]]

    def test_xyz_rank6_three_options(self):
        """Select 2 from 3 Level 6 monsters -> C(3,2) = 3 combinations."""
        can_select = [{"value": 6}, {"value": 6}, {"value": 6}]
        result = find_valid_sum_combinations([], can_select, target_sum=12)
        assert sorted(result) == [[0, 1], [0, 2], [1, 2]]

    def test_synchro_with_must_select_tuner(self):
        """Level 2 Tuner (must) + Level 6 (can) = Level 8 Synchro."""
        must_select = [{"value": 2}]
        can_select = [{"value": 6}, {"value": 4}]
        result = find_valid_sum_combinations(must_select, can_select, target_sum=8)
        assert result == [[0]]  # 2 + 6 = 8

    def test_at_least_mode(self):
        """Mode=1: sum >= target."""
        can_select = [{"value": 3}, {"value": 4}]
        result = find_valid_sum_combinations([], can_select, target_sum=5, mode=1)
        # 3+4=7 >= 5
        assert [0, 1] in result

    def test_at_least_mode_single_card_meets(self):
        """Mode=1: single card >= target."""
        can_select = [{"value": 3}, {"value": 6}]
        result = find_valid_sum_combinations([], can_select, target_sum=5, mode=1)
        # 6 >= 5, and 3+6=9 >= 5
        assert [1] in result
        assert [0, 1] in result

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_empty_can_select_must_meets_target(self):
        """Must-select alone meets target, no can_select needed."""
        must_select = [{"value": 12}]
        result = find_valid_sum_combinations(must_select, [], target_sum=12, min_select=1)
        assert [] in result

    def test_must_select_completes_target(self):
        """Two must-select cards complete the target sum."""
        must_select = [{"value": 6}, {"value": 6}]
        can_select = [{"value": 6}]  # Available but not needed
        result = find_valid_sum_combinations(must_select, can_select, target_sum=12, min_select=2)
        assert [] in result

    def test_no_valid_combinations(self):
        """No combination can reach the target."""
        can_select = [{"value": 3}, {"value": 4}]
        result = find_valid_sum_combinations([], can_select, target_sum=10)
        assert result == []

    def test_target_impossible_too_high(self):
        """Target exceeds maximum possible sum."""
        can_select = [{"value": 2}, {"value": 3}]
        result = find_valid_sum_combinations([], can_select, target_sum=100)
        assert result == []

    def test_target_impossible_smallest_exceeds(self):
        """Smallest card exceeds target (exact mode)."""
        can_select = [{"value": 10}]
        result = find_valid_sum_combinations([], can_select, target_sum=5, mode=0)
        assert result == []

    def test_empty_both_lists(self):
        """Both must_select and can_select are empty."""
        # With default min_select=1, need at least 1 card, so no valid combos
        result = find_valid_sum_combinations([], [], target_sum=0)
        assert result == []

    def test_empty_both_lists_min_select_zero(self):
        """Both lists empty but min_select=0 allows empty selection."""
        result = find_valid_sum_combinations([], [], target_sum=0, min_select=0)
        assert result == [[]]  # Empty selection valid when min_select=0

    def test_empty_can_select_must_not_enough(self):
        """Must-select doesn't meet target, no can_select available."""
        must_select = [{"value": 5}]
        result = find_valid_sum_combinations(must_select, [], target_sum=12)
        assert result == []

    # =========================================================================
    # level2 Feature (Variable Levels)
    # =========================================================================

    def test_level2_single_card(self):
        """Card with level2 can use either value."""
        can_select = [{"value": 4, "level2": 6}]
        result = find_valid_sum_combinations([], can_select, target_sum=6)
        assert result == [[0]]

    def test_level2_uses_primary_value(self):
        """Card with level2 can also match primary value."""
        can_select = [{"value": 4, "level2": 6}]
        result = find_valid_sum_combinations([], can_select, target_sum=4)
        assert result == [[0]]

    def test_level2_multiple_cards(self):
        """Multiple cards with level2 options."""
        can_select = [{"value": 2, "level2": 4}, {"value": 6}]
        result = find_valid_sum_combinations([], can_select, target_sum=10)
        # 4 + 6 = 10 (using level2 of first card)
        assert [0, 1] in result

    def test_level2_zero_ignored(self):
        """level2=0 should be ignored (use primary value only)."""
        can_select = [{"value": 6, "level2": 0}]
        result = find_valid_sum_combinations([], can_select, target_sum=6)
        assert result == [[0]]

    # =========================================================================
    # Selection Bounds
    # =========================================================================

    def test_min_select_constraint(self):
        """min_select=2 requires at least 2 cards."""
        can_select = [{"value": 6}]
        result = find_valid_sum_combinations([], can_select, target_sum=6, min_select=2)
        assert result == []  # Only 1 card available, need 2

    def test_max_select_constraint(self):
        """max_select=2 limits to at most 2 cards."""
        can_select = [{"value": 2}, {"value": 2}, {"value": 2}]
        result = find_valid_sum_combinations([], can_select, target_sum=6, max_select=2)
        assert result == []  # Need 3 cards but max is 2

    def test_combination_count_large(self):
        """Many cards with multiple valid combinations."""
        can_select = [{"value": 2} for _ in range(6)]
        result = find_valid_sum_combinations([], can_select, target_sum=6, max_select=6)
        # C(6,3) = 20 combinations of 3 cards summing to 6
        assert len(result) == comb(6, 3)

    def test_min_max_with_must_select(self):
        """min/max selection counts include must_select cards."""
        must_select = [{"value": 2}]  # 1 card already
        can_select = [{"value": 4}]
        # min_select=2 means total must be 2. must_count=1, so need 1 from can_select
        result = find_valid_sum_combinations(must_select, can_select, target_sum=6, min_select=2)
        assert result == [[0]]  # 2 + 4 = 6, total 2 cards


class TestFindSumCombinationsFlexible:
    """Tests for find_sum_combinations_flexible()."""

    def test_exact_true_matches_mode_0(self):
        """exact=True behaves like mode=0."""
        can_select = [{"value": 6}, {"value": 6}]
        result = find_sum_combinations_flexible([], can_select, target_sum=12, exact=True)
        assert result == [[0, 1]]

    def test_exact_false_allows_overshoot(self):
        """exact=False allows sum > target."""
        can_select = [{"value": 10}]
        result = find_sum_combinations_flexible([], can_select, target_sum=5, exact=False)
        assert result == [[0]]

    def test_exact_false_no_match_under_target(self):
        """exact=False still rejects sums under target."""
        can_select = [{"value": 3}]
        result = find_sum_combinations_flexible([], can_select, target_sum=5, exact=False)
        assert result == []

    def test_exact_false_must_select_meets_target(self):
        """exact=False with must_select already >= target."""
        must_select = [{"value": 10}]
        result = find_sum_combinations_flexible(must_select, [], target_sum=5, exact=False, min_select=1)
        assert [] in result

    def test_exact_true_no_match(self):
        """exact=True rejects sums not equal to target."""
        can_select = [{"value": 10}]
        result = find_sum_combinations_flexible([], can_select, target_sum=5, exact=True)
        assert result == []

    def test_flexible_vs_main_function_consistency(self):
        """find_sum_combinations_flexible should match find_valid_sum_combinations."""
        can_select = [{"value": 3}, {"value": 4}, {"value": 5}]

        # exact=True should match mode=0
        flex_exact = find_sum_combinations_flexible([], can_select, target_sum=7, exact=True)
        main_exact = find_valid_sum_combinations([], can_select, target_sum=7, mode=0)
        assert sorted(flex_exact) == sorted(main_exact)

        # exact=False should match mode=1
        flex_atleast = find_sum_combinations_flexible([], can_select, target_sum=7, exact=False)
        main_atleast = find_valid_sum_combinations([], can_select, target_sum=7, mode=1)
        assert sorted(flex_atleast) == sorted(main_atleast)
