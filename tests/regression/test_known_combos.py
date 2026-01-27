"""
Regression tests for known working combos.
These tests ensure that refactoring doesn't break existing functionality.
"""
import pytest
from pathlib import Path
import json

# TODO: Implement after Phase 3 when imports are stable


@pytest.mark.skip(reason="Implement after Phase 3")
def test_gold_standard_combo_is_findable():
    """The 23-step Engraver -> A Bao A Qu + Caesar combo must be findable."""
    pass


@pytest.mark.skip(reason="Implement after Phase 3")
def test_no_hallucinated_cards():
    """All cards in enumeration results must exist in verified_cards.json."""
    pass


@pytest.mark.skip(reason="Implement after Phase 3")
def test_select_sum_cancel_backtracking():
    """SELECT_SUM_CANCEL should properly backtrack and try alternative cards."""
    pass
