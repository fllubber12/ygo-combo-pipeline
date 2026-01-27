"""
Sum enumeration utilities for Xyz/Synchro/Ritual material selection.

These functions enumerate all valid card combinations that sum to a target value,
used for material selection in various summoning mechanics.
"""

from itertools import combinations, product
from typing import Dict, List


def find_valid_sum_combinations(
    must_select: List[Dict],
    can_select: List[Dict],
    target_sum: int,
    min_select: int = 1,
    max_select: int = 5,
    mode: int = 0,
) -> List[List[int]]:
    """Find all valid combinations of cards that sum to target value.

    Used for Xyz summon material selection, Synchro tuning, ritual tributes, etc.

    Args:
        must_select: Cards that MUST be included (from must_select in message)
        can_select: Cards that CAN be selected (from can_select in message)
        target_sum: Target sum value (e.g., 12 for 2x Level 6 -> Rank 6)
        min_select: Minimum total cards to select
        max_select: Maximum total cards to select
        mode: 0 = exactly equal, 1 = at least equal

    Returns:
        List of valid index lists. Each inner list contains indices into can_select
        that form a valid sum when combined with must_select cards.

    Example:
        For Xyz summon of Rank 6 with two Level 6 monsters available:
        - must_select = []
        - can_select = [{"value": 6, ...}, {"value": 6, ...}]
        - target_sum = 12 (6 + 6)
        - Returns: [[0, 1]] (select both cards)
    """
    # Calculate sum from must_select cards (these are always included)
    must_sum = sum(card.get("value", 0) for card in must_select)
    must_count = len(must_select)

    # Remaining sum needed from can_select cards
    remaining_sum = target_sum - must_sum

    # Early exit: impossible to reach target with no cards available
    if not can_select and remaining_sum > 0:
        return []  # No cards available, can't reach target

    # Early exit: check if sum is achievable
    if can_select and mode == 0:  # Exact match mode
        # Get min and max possible values for each card
        card_values = []
        for c in can_select:
            lvl1 = c.get("value", 0) or c.get("level", 0)
            lvl2 = c.get("level2", lvl1) or lvl1
            card_values.append((min(lvl1, lvl2) if lvl2 > 0 else lvl1,
                               max(lvl1, lvl2) if lvl2 > 0 else lvl1))

        max_possible = sum(v[1] for v in card_values)
        min_single = min(v[0] for v in card_values) if card_values else 0

        if max_possible < remaining_sum:
            return []  # Even using all cards can't reach target
        if remaining_sum > 0 and min_single > remaining_sum:
            return []  # Smallest card exceeds target, impossible to hit exactly

    # Adjust selection bounds for can_select
    remaining_min = max(0, min_select - must_count)
    remaining_max = max(0, max_select - must_count)

    valid_combos: List[List[int]] = []

    # Edge case: if must_select already meets target
    if remaining_sum == 0 and remaining_min == 0:
        valid_combos.append([])  # Empty selection from can_select is valid

    # Try all combination sizes from remaining_min to remaining_max
    for size in range(max(1, remaining_min), min(remaining_max + 1, len(can_select) + 1)):
        for combo_indices in combinations(range(len(can_select)), size):
            combo_cards = [can_select[i] for i in combo_indices]

            # Handle cards with multiple possible levels (level vs level2)
            level_choices = []
            for card in combo_cards:
                lvl1 = card.get("value", 0) or card.get("level", 0)
                lvl2 = card.get("level2", lvl1)
                if lvl2 != lvl1 and lvl2 > 0:
                    level_choices.append([lvl1, lvl2])
                else:
                    level_choices.append([lvl1])

            # Check all possible level combinations
            for levels in product(*level_choices):
                total = sum(levels)

                if mode == 0:  # Exactly equal
                    if total == remaining_sum:
                        valid_combos.append(list(combo_indices))
                        break  # Only need one valid level choice per combo
                else:  # At least equal
                    if total >= remaining_sum:
                        valid_combos.append(list(combo_indices))
                        break

    return valid_combos


def find_sum_combinations_flexible(
    must_select: List[Dict],
    can_select: List[Dict],
    target_sum: int,
    min_select: int = 1,
    max_select: int = 5,
    exact: bool = True,
) -> List[List[int]]:
    """Find combinations with flexible matching (exact or at-least).

    Some Yu-Gi-Oh mechanics require exact sum (Xyz), others require at-least
    (some ritual tributes). This function supports both modes.

    Args:
        must_select: Cards that MUST be included
        can_select: Cards that CAN be selected
        target_sum: Target sum value
        min_select: Minimum total cards to select
        max_select: Maximum total cards to select
        exact: If True, sum must equal target. If False, sum must be >= target.

    Returns:
        List of valid index lists into can_select
    """
    must_sum = sum(card.get("value", 0) for card in must_select)
    must_count = len(must_select)
    remaining_sum = target_sum - must_sum
    remaining_min = max(0, min_select - must_count)
    remaining_max = max(0, max_select - must_count)

    valid_combos: List[List[int]] = []

    # Handle edge case
    if exact and remaining_sum == 0 and remaining_min == 0:
        valid_combos.append([])
    elif not exact and remaining_sum <= 0 and remaining_min == 0:
        valid_combos.append([])

    for size in range(max(1, remaining_min), min(remaining_max + 1, len(can_select) + 1)):
        for combo_indices in combinations(range(len(can_select)), size):
            combo_sum = sum(can_select[i].get("value", 0) for i in combo_indices)

            if exact:
                if combo_sum == remaining_sum:
                    valid_combos.append(list(combo_indices))
            else:
                if combo_sum >= remaining_sum:
                    valid_combos.append(list(combo_indices))

    return valid_combos


__all__ = [
    'find_valid_sum_combinations',
    'find_sum_combinations_flexible',
]
