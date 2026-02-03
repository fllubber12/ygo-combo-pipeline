"""
Unit tests for enumeration/handlers.py.

Tests the MessageHandlerMixin class using a test harness that mocks
the expected attributes and methods from the host class.
"""

import struct
import pytest
from typing import List, Dict, Any, Optional
from unittest.mock import patch

from src.ygo_combo.enumeration.handlers import MessageHandlerMixin
from src.ygo_combo.types import Action


# Mock get_card_name for all tests
def mock_get_card_name(code):
    """Return a predictable name for testing."""
    return f"Card_{code}"


class HandlerHarness(MessageHandlerMixin):
    """Test harness that provides all dependencies expected by MessageHandlerMixin.

    Expected Attributes (from handlers.py docstring):
        - lib: The CFFI library handle
        - dedupe_intermediate: bool - Whether to dedupe intermediate states
        - transposition_table: TranspositionTable instance
        - intermediate_states_pruned: int - Counter for pruned states
        - verbose: bool - Enable verbose logging
        - prioritize_cards: set - Card codes to prioritize
        - prioritize_order: list - Order of prioritized cards
        - failed_at_context: dict - Context hash -> set of failed card codes

    Expected Methods:
        - log(msg, depth): Log a message at given depth
        - _recurse(action_history): Continue enumeration with action history
        - _record_terminal(action_history, reason): Record a terminal state
        - _compute_select_card_context(select_data): Compute context hash
        - _mark_card_failed_at_context(context_hash, card_code): Mark card failed
    """

    def __init__(
        self,
        dedupe_intermediate: bool = False,
        verbose: bool = False,
        prioritize_cards: Optional[set] = None,
        prioritize_order: Optional[list] = None,
    ):
        # Required attributes
        self.lib = None  # Not needed for simple handlers
        self.dedupe_intermediate = dedupe_intermediate
        self.transposition_table = MockTranspositionTable()
        self.intermediate_states_pruned = 0
        self.verbose = verbose
        self.prioritize_cards = prioritize_cards or set()
        self.prioritize_order = prioritize_order or []
        self.failed_at_context = {}

        # Test tracking
        self.recorded_recurses: List[List[Action]] = []
        self.recorded_terminals: List[tuple] = []
        self.log_messages: List[str] = []
        self.marked_failed: List[tuple] = []  # (context_hash, card_code)

    def log(self, msg: str, depth: int) -> None:
        """Record log messages for test assertions."""
        self.log_messages.append(f"[{depth}] {msg}")

    def _recurse(self, action_history: List[Action]) -> None:
        """Record the action history for test assertions."""
        self.recorded_recurses.append(action_history.copy())

    def _record_terminal(self, action_history: List[Action], reason: str) -> None:
        """Record terminal states for test assertions."""
        self.recorded_terminals.append((action_history.copy(), reason))

    def _compute_select_card_context(self, select_data: dict) -> int:
        """Return a simple hash for testing."""
        return hash(str(sorted(select_data.items())))

    def _mark_card_failed_at_context(self, context_hash: int, card_code: int) -> None:
        """Track marked failures for test assertions."""
        self.marked_failed.append((context_hash, card_code))
        if context_hash not in self.failed_at_context:
            self.failed_at_context[context_hash] = set()
        self.failed_at_context[context_hash].add(card_code)


class MockTranspositionTable:
    """Mock transposition table for testing."""

    def __init__(self):
        self.stored = {}

    def lookup(self, state_hash):
        return self.stored.get(state_hash)

    def store(self, state_hash, entry):
        self.stored[state_hash] = entry


# =============================================================================
# Tests for _handle_select_position
# =============================================================================

class TestHandleSelectPosition:
    """Tests for _handle_select_position - always selects ATK position."""

    def test_always_returns_attack_position(self):
        """Handler should always select face-up ATK position (0x1)."""
        harness = HandlerHarness()
        action_history = []
        msg_data = {}  # Unused by this handler

        harness._handle_select_position(None, action_history, msg_data)

        assert len(harness.recorded_recurses) == 1
        recorded = harness.recorded_recurses[0]
        assert len(recorded) == 1

        action = recorded[0]
        assert action.action_type == "SELECT_POSITION"
        assert action.response_value == 0x1
        assert struct.unpack("<I", action.response_bytes)[0] == 0x1
        assert "ATK" in action.description

    def test_appends_to_existing_history(self):
        """Handler should append action to existing action history."""
        harness = HandlerHarness()
        existing_action = Action(
            action_type="ACTIVATE",
            message_type=0,
            response_value=0,
            response_bytes=b"",
            description="Previous action",
        )
        action_history = [existing_action]

        harness._handle_select_position(None, action_history, {})

        assert len(harness.recorded_recurses) == 1
        recorded = harness.recorded_recurses[0]
        assert len(recorded) == 2
        assert recorded[0] is existing_action
        assert recorded[1].action_type == "SELECT_POSITION"

    def test_no_terminal_recorded(self):
        """Position selection should not record terminal state."""
        harness = HandlerHarness()
        harness._handle_select_position(None, [], {})

        assert len(harness.recorded_terminals) == 0


# =============================================================================
# Tests for _handle_yes_no
# =============================================================================

class TestHandleYesNo:
    """Tests for _handle_yes_no - branches on Yes and No."""

    def test_branches_yes_and_no(self):
        """Handler should create branches for both Yes and No."""
        harness = HandlerHarness()
        msg_type = 15  # MSG_SELECT_YESNO

        harness._handle_yes_no(None, [], {}, msg_type)

        assert len(harness.recorded_recurses) == 2

        # First branch is Yes
        yes_action = harness.recorded_recurses[0][0]
        assert yes_action.action_type == "YES_NO"
        assert yes_action.response_value == 1
        assert struct.unpack("<I", yes_action.response_bytes)[0] == 1
        assert "Yes" in yes_action.description

        # Second branch is No
        no_action = harness.recorded_recurses[1][0]
        assert no_action.action_type == "YES_NO"
        assert no_action.response_value == 0
        assert struct.unpack("<I", no_action.response_bytes)[0] == 0
        assert "No" in no_action.description

    def test_yes_explored_first(self):
        """Yes should be explored before No (order matters for pruning)."""
        harness = HandlerHarness()

        harness._handle_yes_no(None, [], {}, 15)

        first_value = harness.recorded_recurses[0][0].response_value
        second_value = harness.recorded_recurses[1][0].response_value
        assert first_value == 1  # Yes first
        assert second_value == 0  # No second

    def test_preserves_message_type(self):
        """Handler should preserve the message type in the action."""
        harness = HandlerHarness()
        msg_type = 14  # MSG_SELECT_EFFECTYN

        harness._handle_yes_no(None, [], {}, msg_type)

        assert harness.recorded_recurses[0][0].message_type == 14
        assert harness.recorded_recurses[1][0].message_type == 14

    def test_logs_both_branches(self):
        """Handler should log both Yes and No branches."""
        harness = HandlerHarness()

        harness._handle_yes_no(None, [], {}, 15)

        assert any("Yes" in msg for msg in harness.log_messages)
        assert any("No" in msg for msg in harness.log_messages)

    def test_no_terminal_recorded(self):
        """Yes/No selection should not record terminal state."""
        harness = HandlerHarness()
        harness._handle_yes_no(None, [], {}, 15)

        assert len(harness.recorded_terminals) == 0


# =============================================================================
# Tests for _handle_select_option
# =============================================================================

class TestHandleSelectOption:
    """Tests for _handle_select_option - iterates over available options."""

    def test_branches_on_each_option(self):
        """Handler should create a branch for each option."""
        harness = HandlerHarness()
        msg_data = {
            "count": 3,
            "options": [
                {"desc": 100},
                {"desc": 200},
                {"desc": 300},
            ]
        }

        harness._handle_select_option(None, [], msg_data)

        assert len(harness.recorded_recurses) == 3

        for i, recorded in enumerate(harness.recorded_recurses):
            action = recorded[0]
            assert action.action_type == "SELECT_OPTION"
            assert action.response_value == i
            assert struct.unpack("<I", action.response_bytes)[0] == i

    def test_includes_desc_in_description(self):
        """Handler should include option desc in the action description."""
        harness = HandlerHarness()
        msg_data = {
            "count": 2,
            "options": [
                {"desc": 12345},
                {"desc": 67890},
            ]
        }

        harness._handle_select_option(None, [], msg_data)

        assert "12345" in harness.recorded_recurses[0][0].description
        assert "67890" in harness.recorded_recurses[1][0].description

    def test_handles_missing_options_list(self):
        """Handler should work when options list is shorter than count."""
        harness = HandlerHarness()
        msg_data = {
            "count": 3,
            "options": [{"desc": 100}]  # Only one option provided
        }

        harness._handle_select_option(None, [], msg_data)

        # Should still create 3 branches
        assert len(harness.recorded_recurses) == 3
        # Missing options should use desc=0
        assert "desc=0" in harness.recorded_recurses[2][0].description

    def test_handles_none_msg_data(self):
        """Handler should handle None msg_data with defaults."""
        harness = HandlerHarness()

        harness._handle_select_option(None, [], None)

        # Default count is 2
        assert len(harness.recorded_recurses) == 2

    def test_handles_empty_msg_data(self):
        """Handler should handle empty msg_data with defaults."""
        harness = HandlerHarness()

        harness._handle_select_option(None, [], {})

        # Default count is 2
        assert len(harness.recorded_recurses) == 2

    def test_logs_option_count(self):
        """Handler should log the number of available options."""
        harness = HandlerHarness()
        msg_data = {"count": 4, "options": []}

        harness._handle_select_option(None, [], msg_data)

        assert any("4 options" in msg for msg in harness.log_messages)

    def test_logs_each_branch(self):
        """Handler should log each option branch."""
        harness = HandlerHarness()
        msg_data = {"count": 2, "options": []}

        harness._handle_select_option(None, [], msg_data)

        assert any("Option 0" in msg for msg in harness.log_messages)
        assert any("Option 1" in msg for msg in harness.log_messages)


# =============================================================================
# Tests for _handle_legacy_message_12
# =============================================================================

class TestHandleLegacyMessage12:
    """Tests for _handle_legacy_message_12 - legacy Yes/No prompt."""

    def test_branches_yes_and_no(self):
        """Handler should create branches for both Yes (1) and No (0)."""
        harness = HandlerHarness()

        harness._handle_legacy_message_12(None, [], {})

        assert len(harness.recorded_recurses) == 2

        # First branch is Yes (1)
        yes_action = harness.recorded_recurses[0][0]
        assert yes_action.action_type == "LEGACY_12"
        assert yes_action.response_value == 1
        assert yes_action.message_type == 12

        # Second branch is No (0)
        no_action = harness.recorded_recurses[1][0]
        assert no_action.action_type == "LEGACY_12"
        assert no_action.response_value == 0

    def test_yes_explored_first(self):
        """Yes should be explored before No."""
        harness = HandlerHarness()

        harness._handle_legacy_message_12(None, [], {})

        assert harness.recorded_recurses[0][0].response_value == 1
        assert harness.recorded_recurses[1][0].response_value == 0


# =============================================================================
# Tests for _handle_select_place
# =============================================================================

class TestHandleSelectPlace:
    """Tests for _handle_select_place - zone selection from flag bitfield."""

    def test_selects_first_available_szone(self):
        """Handler should select first available S/T zone."""
        harness = HandlerHarness()
        # flag bits 8-12 are S/T zones 0-4
        # If bit is SET, zone is OCCUPIED. We want first UNSET bit.
        # All zones available: flag=0
        msg_data = {"player": 0, "flag": 0}

        harness._handle_select_place(None, [], msg_data)

        assert len(harness.recorded_recurses) == 1
        action = harness.recorded_recurses[0][0]
        assert action.action_type == "SELECT_PLACE"

        # Parse the response bytes
        player, location, sequence = struct.unpack("<BBB", action.response_bytes)
        assert player == 0
        assert location == 0x08  # S/T zone
        assert sequence == 0  # First available

    def test_selects_monster_zone_when_szone_full(self):
        """Handler should fall back to monster zone if S/T zones are full."""
        harness = HandlerHarness()
        # Set bits 8-12 to mark all S/T zones as occupied
        szone_full_flag = 0x1F00  # Bits 8-12 set
        msg_data = {"player": 0, "flag": szone_full_flag}

        harness._handle_select_place(None, [], msg_data)

        action = harness.recorded_recurses[0][0]
        player, location, sequence = struct.unpack("<BBB", action.response_bytes)
        assert location == 0x04  # Monster zone
        assert sequence == 0  # First available

    def test_skips_occupied_szone(self):
        """Handler should skip occupied S/T zones."""
        harness = HandlerHarness()
        # Zone 0 occupied (bit 8 set), zones 1-4 available
        msg_data = {"player": 0, "flag": 0x100}

        harness._handle_select_place(None, [], msg_data)

        action = harness.recorded_recurses[0][0]
        player, location, sequence = struct.unpack("<BBB", action.response_bytes)
        assert location == 0x08  # S/T zone
        assert sequence == 1  # Second zone (index 1)

    def test_respects_player_field(self):
        """Handler should use the player value from msg_data."""
        harness = HandlerHarness()
        msg_data = {"player": 1, "flag": 0}

        harness._handle_select_place(None, [], msg_data)

        action = harness.recorded_recurses[0][0]
        player, _, _ = struct.unpack("<BBB", action.response_bytes)
        assert player == 1

    def test_logs_flag_value(self):
        """Handler should log the flag value."""
        harness = HandlerHarness()
        msg_data = {"player": 0, "flag": 0x1234}

        harness._handle_select_place(None, [], msg_data)

        assert any("0x00001234" in msg for msg in harness.log_messages)


# =============================================================================
# Tests for _handle_select_card
# =============================================================================

@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectCardSingleSelection:
    """Tests for _handle_select_card with min=max=1 (single card selection)."""

    def test_single_card_one_branch(self):
        """Single card available should create one branch."""
        harness = HandlerHarness()
        select_data = {
            "cards": [{"code": 12345}],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, [], select_data)

        assert len(harness.recorded_recurses) == 1
        action = harness.recorded_recurses[0][0]
        assert action.action_type == "SELECT_CARD"
        assert action.card_code == 12345
        assert "Card_12345" in action.description

    def test_two_unique_cards_two_branches(self):
        """Two different cards should create two branches."""
        harness = HandlerHarness()
        select_data = {
            "cards": [{"code": 111}, {"code": 222}],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, [], select_data)

        assert len(harness.recorded_recurses) == 2
        codes = [r[0].card_code for r in harness.recorded_recurses]
        assert 111 in codes
        assert 222 in codes

    def test_deduplication_same_code_one_branch(self):
        """Two copies of same card (same code) should create one branch."""
        harness = HandlerHarness()
        select_data = {
            "cards": [
                {"code": 12345},  # First copy
                {"code": 12345},  # Second copy (same card)
            ],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, [], select_data)

        # Should only create ONE branch due to deduplication
        assert len(harness.recorded_recurses) == 1
        assert harness.recorded_recurses[0][0].card_code == 12345

    def test_deduplication_mixed_cards(self):
        """Mix of unique and duplicate cards should dedupe correctly."""
        harness = HandlerHarness()
        select_data = {
            "cards": [
                {"code": 111},
                {"code": 222},
                {"code": 111},  # Duplicate of first
                {"code": 333},
                {"code": 222},  # Duplicate of second
            ],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, [], select_data)

        # Should create 3 branches (111, 222, 333)
        assert len(harness.recorded_recurses) == 3
        codes = [r[0].card_code for r in harness.recorded_recurses]
        assert sorted(codes) == [111, 222, 333]

    def test_uses_first_index_for_duplicates(self):
        """When deduping, should use the first occurrence's index."""
        harness = HandlerHarness()
        select_data = {
            "cards": [
                {"code": 999},  # Index 0
                {"code": 111},  # Index 1
                {"code": 999},  # Index 2 (duplicate, should be ignored)
            ],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, [], select_data)

        # Find the action for code 999
        action_999 = None
        for r in harness.recorded_recurses:
            if r[0].card_code == 999:
                action_999 = r[0]
                break

        # The response should use index 0, not index 2
        assert action_999 is not None
        assert action_999.response_value == [0]


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectCardPrioritization:
    """Tests for _handle_select_card priority sorting."""

    def test_priority_cards_explored_first(self):
        """Cards in prioritize_cards should be explored before others."""
        harness = HandlerHarness(
            prioritize_cards={222},  # Prioritize card 222
            prioritize_order=[222],
        )
        select_data = {
            "cards": [{"code": 111}, {"code": 222}, {"code": 333}],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, [], select_data)

        # First branch should be the prioritized card
        first_code = harness.recorded_recurses[0][0].card_code
        assert first_code == 222

    def test_priority_order_respected(self):
        """Multiple prioritized cards should follow prioritize_order."""
        harness = HandlerHarness(
            prioritize_cards={111, 333},
            prioritize_order=[333, 111],  # 333 before 111
        )
        select_data = {
            "cards": [{"code": 111}, {"code": 222}, {"code": 333}],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, [], select_data)

        codes = [r[0].card_code for r in harness.recorded_recurses]
        # 333 should come before 111, both before 222
        assert codes.index(333) < codes.index(111)
        assert codes.index(111) < codes.index(222)

    def test_non_priority_cards_maintain_order(self):
        """Non-prioritized cards should maintain original order."""
        harness = HandlerHarness(
            prioritize_cards={999},  # Card not in list
            prioritize_order=[999],
        )
        select_data = {
            "cards": [{"code": 111}, {"code": 222}, {"code": 333}],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, [], select_data)

        codes = [r[0].card_code for r in harness.recorded_recurses]
        # Original order should be preserved
        assert codes == [111, 222, 333]


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectCardFailedFiltering:
    """Tests for _handle_select_card failed card filtering."""

    def test_failed_cards_excluded(self):
        """Cards that led to SELECT_SUM_CANCEL should be excluded."""
        harness = HandlerHarness()

        # Create action history with a SELECT_CARD -> SELECT_SUM_CANCEL pattern
        select_action = Action(
            action_type="SELECT_CARD",
            message_type=0,
            response_value=[0],
            response_bytes=b"",
            description="Select Card_111",
            card_code=111,  # This card led to cancel
        )
        cancel_action = Action(
            action_type="SELECT_SUM_CANCEL",
            message_type=0,
            response_value=-1,
            response_bytes=b"",
            description="Cancel",
        )
        action_history = [select_action, cancel_action]

        select_data = {
            "cards": [{"code": 111}, {"code": 222}, {"code": 333}],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, action_history, select_data)

        # Card 111 should be excluded
        codes = [r[-1].card_code for r in harness.recorded_recurses]
        assert 111 not in codes
        assert 222 in codes
        assert 333 in codes
        assert len(harness.recorded_recurses) == 2

    def test_non_failed_cards_included(self):
        """Cards without SELECT_SUM_CANCEL should not be excluded."""
        harness = HandlerHarness()

        # SELECT_CARD without a following SELECT_SUM_CANCEL
        select_action = Action(
            action_type="SELECT_CARD",
            message_type=0,
            response_value=[0],
            response_bytes=b"",
            description="Select Card_111",
            card_code=111,
        )
        other_action = Action(
            action_type="SELECT_SUM",  # Not CANCEL
            message_type=0,
            response_value=[0],
            response_bytes=b"",
            description="Sum select",
        )
        action_history = [select_action, other_action]

        select_data = {
            "cards": [{"code": 111}, {"code": 222}],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, action_history, select_data)

        # Card 111 should NOT be excluded
        codes = [r[-1].card_code for r in harness.recorded_recurses]
        assert 111 in codes


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectCardMultiSelect:
    """Tests for _handle_select_card with multi-card selection (min < max)."""

    def test_multi_select_creates_combinations(self):
        """Multi-select should create branches for each valid combination."""
        harness = HandlerHarness()
        select_data = {
            "cards": [{"code": 111}, {"code": 222}, {"code": 333}],
            "min": 2,
            "max": 2,
        }

        harness._handle_select_card(None, [], select_data)

        # C(3,2) = 3 combinations
        assert len(harness.recorded_recurses) == 3

    def test_multi_select_range(self):
        """Multi-select with min != max should create all valid sizes."""
        harness = HandlerHarness()
        select_data = {
            "cards": [{"code": 111}, {"code": 222}, {"code": 333}],
            "min": 1,
            "max": 2,
        }

        harness._handle_select_card(None, [], select_data)

        # 3 single selections + 3 pairs = 6 total
        assert len(harness.recorded_recurses) == 6

    def test_multi_select_deduplication(self):
        """Multi-select should deduplicate by card code."""
        harness = HandlerHarness()
        select_data = {
            "cards": [
                {"code": 111},
                {"code": 111},  # Duplicate
                {"code": 222},
            ],
            "min": 2,
            "max": 2,
        }

        harness._handle_select_card(None, [], select_data)

        # Only 2 unique codes, so only C(2,2) = 1 combination
        assert len(harness.recorded_recurses) == 1

    def test_multi_select_excludes_failed_cards(self):
        """Multi-select should exclude failed cards from combinations."""
        harness = HandlerHarness()

        # Mark card 111 as failed
        failed_select = Action(
            action_type="SELECT_CARD",
            message_type=0,
            response_value=[0],
            response_bytes=b"",
            description="",
            card_code=111,
        )
        cancel = Action(
            action_type="SELECT_SUM_CANCEL",
            message_type=0,
            response_value=-1,
            response_bytes=b"",
            description="",
        )

        select_data = {
            "cards": [{"code": 111}, {"code": 222}, {"code": 333}],
            "min": 2,
            "max": 2,
        }

        harness._handle_select_card(None, [failed_select, cancel], select_data)

        # Only 222 and 333 available, so C(2,2) = 1 combination
        assert len(harness.recorded_recurses) == 1


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectCardContextHash:
    """Tests for context hash tracking in _handle_select_card."""

    def test_action_includes_context_hash(self):
        """SELECT_CARD action should include context_hash for backtracking."""
        harness = HandlerHarness()
        select_data = {
            "cards": [{"code": 12345}],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, [], select_data)

        action = harness.recorded_recurses[0][0]
        assert action.context_hash is not None

    def test_same_data_same_hash(self):
        """Same select_data should produce same context hash."""
        harness = HandlerHarness()
        select_data = {
            "cards": [{"code": 111}, {"code": 222}],
            "min": 1,
            "max": 1,
        }

        harness._handle_select_card(None, [], select_data)

        # All actions from same call should have same context hash
        hashes = [r[0].context_hash for r in harness.recorded_recurses]
        assert len(set(hashes)) == 1  # All same


# =============================================================================
# Integration Tests
# =============================================================================

class TestActionHistoryChaining:
    """Tests that verify action history is properly maintained."""

    def test_multiple_handlers_chain_correctly(self):
        """Actions from multiple handler calls should chain correctly."""
        harness = HandlerHarness()

        # Simulate: position -> yes/no sequence
        harness._handle_select_position(None, [], {})
        first_action = harness.recorded_recurses[0][0]

        harness.recorded_recurses.clear()
        harness._handle_yes_no(None, [first_action], {}, 15)

        # Check that yes/no branches include the position action
        for recorded in harness.recorded_recurses:
            assert len(recorded) == 2
            assert recorded[0] is first_action
            assert recorded[1].action_type == "YES_NO"

    def test_action_history_not_mutated(self):
        """Original action history should not be mutated."""
        harness = HandlerHarness()
        original = [Action(
            action_type="TEST",
            message_type=0,
            response_value=0,
            response_bytes=b"",
            description="Original",
        )]
        original_copy = original.copy()

        harness._handle_yes_no(None, original, {}, 15)

        # Original should be unchanged
        assert len(original) == 1
        assert original == original_copy


# =============================================================================
# Tests for _handle_select_sum
# =============================================================================

@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectSumCancel:
    """Tests for SELECT_SUM_CANCEL branch in _handle_select_sum."""

    def test_cancel_branch_always_created(self):
        """Cancel branch should always be created, even with valid combos."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [
                {"code": 111, "value": 6},
                {"code": 222, "value": 6},
            ],
            "target_sum": 12,
        }

        harness._handle_select_sum(None, [], msg_data)

        # Should have cancel + valid combo branches
        assert len(harness.recorded_recurses) >= 1
        cancel_action = harness.recorded_recurses[0][0]
        assert cancel_action.action_type == "SELECT_SUM_CANCEL"

    def test_cancel_branch_first(self):
        """Cancel branch should be explored before valid combos."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [
                {"code": 111, "value": 6},
                {"code": 222, "value": 6},
            ],
            "target_sum": 12,
        }

        harness._handle_select_sum(None, [], msg_data)

        first_action = harness.recorded_recurses[0][0]
        assert first_action.action_type == "SELECT_SUM_CANCEL"

    def test_cancel_response_format(self):
        """Cancel response should be struct.pack('<i', -1)."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [{"code": 111, "value": 6}],
            "target_sum": 6,
        }

        harness._handle_select_sum(None, [], msg_data)

        cancel_action = harness.recorded_recurses[0][0]
        assert cancel_action.response_value == -1
        assert struct.unpack("<i", cancel_action.response_bytes)[0] == -1


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectSumBasicCombinations:
    """Tests for basic combination finding in _handle_select_sum."""

    def test_single_valid_combo(self):
        """Two cards summing to target should create one combo branch."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [
                {"code": 111, "value": 6},
                {"code": 222, "value": 6},
            ],
            "target_sum": 12,
        }

        harness._handle_select_sum(None, [], msg_data)

        # Cancel + 1 combo
        assert len(harness.recorded_recurses) == 2
        combo_action = harness.recorded_recurses[1][0]
        assert combo_action.action_type == "SELECT_SUM"

    def test_multiple_valid_combos(self):
        """Three cards with C(3,2) valid combos should create 3 branches."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [
                {"code": 111, "value": 6},
                {"code": 222, "value": 6},
                {"code": 333, "value": 6},
            ],
            "target_sum": 12,
        }

        harness._handle_select_sum(None, [], msg_data)

        # Cancel + 3 combos (C(3,2) = 3)
        assert len(harness.recorded_recurses) == 4
        combo_actions = [r[0] for r in harness.recorded_recurses[1:]]
        assert all(a.action_type == "SELECT_SUM" for a in combo_actions)

    def test_no_valid_combos_only_cancel(self):
        """When no combos possible, only cancel branch (+ fallback) created."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [
                {"code": 111, "value": 3},
                {"code": 222, "value": 4},
            ],
            "target_sum": 100,  # Impossible
        }

        harness._handle_select_sum(None, [], msg_data)

        # Cancel + fallback (when no valid combos)
        assert len(harness.recorded_recurses) >= 1
        assert harness.recorded_recurses[0][0].action_type == "SELECT_SUM_CANCEL"


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectSumDeduplication:
    """Tests for deduplication by card code in _handle_select_sum."""

    def test_deduplication_by_code(self):
        """Duplicate code pairs should result in one combo branch."""
        harness = HandlerHarness()
        # Setup: 3 copies of same card (code 111), value 4 each
        # Valid combos (indices): [0,1], [0,2], [1,2] all sum to 8
        # After dedup by sorted codes: all produce (111, 111), so only 1 unique
        msg_data = {
            "can_select": [
                {"code": 111, "value": 4},
                {"code": 111, "value": 4},
                {"code": 111, "value": 4},
            ],
            "target_sum": 8,
        }

        harness._handle_select_sum(None, [], msg_data)

        # Should have only 1 unique combo after dedup (all combos are (111, 111))
        combo_actions = [r[0] for r in harness.recorded_recurses if r[0].action_type == "SELECT_SUM"]
        assert len(combo_actions) == 1

    def test_different_codes_different_branches(self):
        """Different card codes should create separate branches."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [
                {"code": 111, "value": 6},
                {"code": 222, "value": 6},
                {"code": 333, "value": 6},
            ],
            "target_sum": 12,
        }

        harness._handle_select_sum(None, [], msg_data)

        combo_actions = [r[0] for r in harness.recorded_recurses if r[0].action_type == "SELECT_SUM"]
        # C(3,2) = 3 unique combinations
        assert len(combo_actions) == 3


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectSumFailedCardMarking:
    """Tests for failed card marking in _handle_select_sum."""

    def test_marks_preceding_select_card_failed(self):
        """Should mark preceding SELECT_CARD as failed at its context."""
        harness = HandlerHarness()

        # Create action history with SELECT_CARD
        select_action = Action(
            action_type="SELECT_CARD",
            message_type=0,
            response_value=[0],
            response_bytes=b"",
            description="Select card",
            card_code=12345,
            context_hash=999,
        )
        action_history = [select_action]

        msg_data = {
            "can_select": [{"code": 111, "value": 6}],
            "target_sum": 6,
        }

        harness._handle_select_sum(None, action_history, msg_data)

        # Should have marked the card as failed
        assert len(harness.marked_failed) == 1
        assert harness.marked_failed[0] == (999, 12345)

    def test_no_marking_without_select_card(self):
        """Should not mark anything if no preceding SELECT_CARD."""
        harness = HandlerHarness()

        # Action history without SELECT_CARD
        other_action = Action(
            action_type="ACTIVATE",
            message_type=0,
            response_value=0,
            response_bytes=b"",
            description="Activate",
        )
        action_history = [other_action]

        msg_data = {
            "can_select": [{"code": 111, "value": 6}],
            "target_sum": 6,
        }

        harness._handle_select_sum(None, action_history, msg_data)

        # Should not have marked anything
        assert len(harness.marked_failed) == 0

    def test_no_marking_without_context_hash(self):
        """Should not mark if SELECT_CARD has no context_hash."""
        harness = HandlerHarness()

        select_action = Action(
            action_type="SELECT_CARD",
            message_type=0,
            response_value=[0],
            response_bytes=b"",
            description="Select card",
            card_code=12345,
            context_hash=None,  # No context hash
        )
        action_history = [select_action]

        msg_data = {
            "can_select": [{"code": 111, "value": 6}],
            "target_sum": 6,
        }

        harness._handle_select_sum(None, action_history, msg_data)

        # Should not have marked anything
        assert len(harness.marked_failed) == 0


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectSumFallback:
    """Tests for fallback behavior in _handle_select_sum."""

    def test_fallback_when_no_valid_combos(self):
        """Should create fallback branch when no valid combinations."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [
                {"code": 111, "value": 3},
            ],
            "target_sum": 100,  # Impossible
        }

        harness._handle_select_sum(None, [], msg_data)

        # Should have cancel + fallback
        action_types = [r[0].action_type for r in harness.recorded_recurses]
        assert "SELECT_SUM_CANCEL" in action_types
        assert "SELECT_SUM_FALLBACK" in action_types

    def test_no_fallback_when_valid_combos(self):
        """Should not create fallback when valid combinations exist."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [
                {"code": 111, "value": 6},
                {"code": 222, "value": 6},
            ],
            "target_sum": 12,
        }

        harness._handle_select_sum(None, [], msg_data)

        action_types = [r[0].action_type for r in harness.recorded_recurses]
        assert "SELECT_SUM_FALLBACK" not in action_types

    def test_no_fallback_when_empty_can_select(self):
        """Should not create fallback when can_select is empty."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [],
            "target_sum": 12,
        }

        harness._handle_select_sum(None, [], msg_data)

        action_types = [r[0].action_type for r in harness.recorded_recurses]
        assert "SELECT_SUM_FALLBACK" not in action_types


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectSumResponseFormat:
    """Tests for SELECT_SUM response format."""

    def test_response_is_raw_u8_bytes(self):
        """Response should be raw u8 bytes, not struct-packed."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [
                {"code": 111, "value": 6},
                {"code": 222, "value": 6},
            ],
            "target_sum": 12,
        }

        harness._handle_select_sum(None, [], msg_data)

        # Get the SELECT_SUM action (not cancel)
        combo_action = None
        for r in harness.recorded_recurses:
            if r[0].action_type == "SELECT_SUM":
                combo_action = r[0]
                break

        assert combo_action is not None
        # Response format: [total_count] + [must_indices] + [selected_indices]
        # For 2 cards, no must_select: [2, 0, 1]
        response = combo_action.response_bytes
        assert len(response) == 3  # total_count + 2 indices
        assert response[0] == 2  # total count

    def test_response_includes_must_count(self):
        """Response should include must_select indices."""
        harness = HandlerHarness()
        msg_data = {
            "must_select": [{"code": 100, "value": 2}],
            "can_select": [
                {"code": 111, "value": 6},
            ],
            "target_sum": 8,
            "min": 2,  # Need at least 2 cards (1 must + 1 can)
            "max": 2,  # Allow 2 cards total
        }

        harness._handle_select_sum(None, [], msg_data)

        # Find SELECT_SUM action
        combo_action = None
        for r in harness.recorded_recurses:
            if r[0].action_type == "SELECT_SUM":
                combo_action = r[0]
                break

        assert combo_action is not None
        response = combo_action.response_bytes
        # Format: [total_count=2] + [must_index=0] + [selected_index=0]
        assert response[0] == 2  # total count (1 must + 1 selected)
        assert response[1] == 0  # must index 0

    def test_fallback_response_format(self):
        """Fallback response should also use raw u8 format."""
        harness = HandlerHarness()
        msg_data = {
            "can_select": [{"code": 111, "value": 3}],
            "target_sum": 100,  # Impossible
        }

        harness._handle_select_sum(None, [], msg_data)

        fallback_action = None
        for r in harness.recorded_recurses:
            if r[0].action_type == "SELECT_SUM_FALLBACK":
                fallback_action = r[0]
                break

        assert fallback_action is not None
        response = fallback_action.response_bytes
        # Format: [total_count=1] + [selected_index=0]
        assert response[0] == 1  # total count
        assert response[1] == 0  # card index 0


# =============================================================================
# Tests for _handle_idle
# =============================================================================

class MockIntermediateState:
    """Mock IntermediateState for testing transposition table behavior."""

    def __init__(self, hash_value=12345):
        self._hash_value = hash_value

    def zobrist_hash(self):
        return self._hash_value


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleIdleBranching:
    """Tests for _handle_idle branching on different action types."""

    def test_branches_on_activatable(self):
        """Handler should create one branch per activatable card."""
        harness = HandlerHarness()
        idle_data = {
            "activatable": [
                {"code": 111, "loc": 2, "desc": 0},
                {"code": 222, "loc": 4, "desc": 1},
            ],
            "spsummon": [],
            "summonable": [],
            "to_ep": False,
        }

        harness._handle_idle(None, [], idle_data)

        # Should have 2 branches for activatable cards
        assert len(harness.recorded_recurses) == 2
        action_types = [r[0].action_type for r in harness.recorded_recurses]
        assert action_types == ["ACTIVATE", "ACTIVATE"]

    def test_branches_on_spsummon(self):
        """Handler should create one branch per special summon."""
        harness = HandlerHarness()
        idle_data = {
            "activatable": [],
            "spsummon": [
                {"code": 333},
                {"code": 444},
                {"code": 555},
            ],
            "summonable": [],
            "to_ep": False,
        }

        harness._handle_idle(None, [], idle_data)

        assert len(harness.recorded_recurses) == 3
        action_types = [r[0].action_type for r in harness.recorded_recurses]
        assert action_types == ["SPSUMMON", "SPSUMMON", "SPSUMMON"]

    def test_branches_on_summonable(self):
        """Handler should create one branch per normal summon."""
        harness = HandlerHarness()
        idle_data = {
            "activatable": [],
            "spsummon": [],
            "summonable": [{"code": 666}],
            "to_ep": False,
        }

        harness._handle_idle(None, [], idle_data)

        assert len(harness.recorded_recurses) == 1
        assert harness.recorded_recurses[0][0].action_type == "SUMMON"
        assert harness.recorded_recurses[0][0].card_code == 666

    def test_pass_when_to_ep_true(self):
        """Handler should create PASS terminal when to_ep is true."""
        harness = HandlerHarness()
        idle_data = {
            "activatable": [],
            "spsummon": [],
            "summonable": [],
            "to_ep": True,
        }

        harness._handle_idle(None, [], idle_data)

        # PASS should be recorded as terminal, not recurse
        assert len(harness.recorded_terminals) == 1
        action = harness.recorded_terminals[0][0][0]  # (history, reason)[0][0]
        assert action.action_type == "PASS"
        assert "End Phase" in action.description


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleIdleActionFormat:
    """Tests for _handle_idle action response formats."""

    def test_activate_action_format(self):
        """ACTIVATE action should have correct response format."""
        harness = HandlerHarness()
        idle_data = {
            "activatable": [{"code": 12345, "loc": 2, "desc": 3}],
            "spsummon": [],
            "summonable": [],
            "to_ep": False,
        }

        harness._handle_idle(None, [], idle_data)

        action = harness.recorded_recurses[0][0]
        assert action.action_type == "ACTIVATE"
        assert action.card_code == 12345
        assert action.card_name == "Card_12345"
        # Response: (index << 16) | 5 (IDLE_RESPONSE_ACTIVATE)
        expected_value = (0 << 16) | 5
        assert action.response_value == expected_value
        assert struct.unpack("<I", action.response_bytes)[0] == expected_value

    def test_spsummon_action_format(self):
        """SPSUMMON action should have response_value = (i << 16) | 1."""
        harness = HandlerHarness()
        idle_data = {
            "activatable": [],
            "spsummon": [{"code": 111}, {"code": 222}],
            "summonable": [],
            "to_ep": False,
        }

        harness._handle_idle(None, [], idle_data)

        # Check second SPSUMMON (index 1)
        action = harness.recorded_recurses[1][0]
        assert action.action_type == "SPSUMMON"
        expected_value = (1 << 16) | 1  # index 1, SPSUMMON type
        assert action.response_value == expected_value
        assert struct.unpack("<I", action.response_bytes)[0] == expected_value

    def test_summon_action_format(self):
        """SUMMON action should have response_value = (i << 16) | 0."""
        harness = HandlerHarness()
        idle_data = {
            "activatable": [],
            "spsummon": [],
            "summonable": [{"code": 333}, {"code": 444}],
            "to_ep": False,
        }

        harness._handle_idle(None, [], idle_data)

        # Check second SUMMON (index 1)
        action = harness.recorded_recurses[1][0]
        assert action.action_type == "SUMMON"
        expected_value = (1 << 16) | 0  # index 1, SUMMON type
        assert action.response_value == expected_value
        assert struct.unpack("<I", action.response_bytes)[0] == expected_value


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleIdleDeduplication:
    """Tests for _handle_idle transposition table deduplication."""

    @patch('src.ygo_combo.enumeration.handlers.IntermediateState')
    def test_deduplication_enabled_skips_duplicate_state(self, mock_state_class):
        """Handler should skip processing when state is already in transposition table."""
        harness = HandlerHarness(dedupe_intermediate=True)

        # Set up mock to return a state with known hash
        mock_state = MockIntermediateState(hash_value=99999)
        mock_state_class.from_engine.return_value = mock_state

        # Pre-populate transposition table with this hash
        harness.transposition_table.stored[99999] = "existing_entry"

        idle_data = {
            "activatable": [{"code": 111, "loc": 2, "desc": 0}],
            "spsummon": [],
            "summonable": [],
            "to_ep": False,
        }

        harness._handle_idle(None, [], idle_data)

        # Should return early - no branches created
        assert len(harness.recorded_recurses) == 0
        assert harness.intermediate_states_pruned == 1

    @patch('src.ygo_combo.enumeration.handlers.IntermediateState')
    def test_deduplication_disabled_no_pruning(self, mock_state_class):
        """Handler should not prune when dedupe_intermediate is False."""
        harness = HandlerHarness(dedupe_intermediate=False)

        idle_data = {
            "activatable": [{"code": 111, "loc": 2, "desc": 0}],
            "spsummon": [],
            "summonable": [],
            "to_ep": False,
        }

        harness._handle_idle(None, [], idle_data)

        # Should process - IntermediateState.from_engine never called
        mock_state_class.from_engine.assert_not_called()
        assert len(harness.recorded_recurses) == 1

    @patch('src.ygo_combo.enumeration.handlers.IntermediateState')
    def test_stores_state_in_transposition_table(self, mock_state_class):
        """Handler should store new states in transposition table."""
        harness = HandlerHarness(dedupe_intermediate=True)

        mock_state = MockIntermediateState(hash_value=77777)
        mock_state_class.from_engine.return_value = mock_state

        idle_data = {
            "activatable": [{"code": 111, "loc": 2, "desc": 0}],
            "spsummon": [],
            "summonable": [],
            "to_ep": False,
        }

        harness._handle_idle(None, [], idle_data)

        # State should be stored
        assert 77777 in harness.transposition_table.stored
        # Branch should be created
        assert len(harness.recorded_recurses) == 1


# =============================================================================
# Tests for _handle_select_unselect_card
# =============================================================================

@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectUnselectCardBasic:
    """Tests for _handle_select_unselect_card basic functionality."""

    def test_branches_on_each_unique_card(self):
        """Handler should create one branch per unique card code."""
        harness = HandlerHarness()
        msg_data = {
            "finishable": 0,
            "select_cards": [
                {"code": 111},
                {"code": 222},
                {"code": 333},
            ],
            "unselect_cards": [],
        }

        harness._handle_select_unselect_card(None, [], msg_data)

        assert len(harness.recorded_recurses) == 3
        codes = [r[0].card_code for r in harness.recorded_recurses]
        assert set(codes) == {111, 222, 333}

    def test_finish_option_when_finishable_with_unselect(self):
        """Handler should create finish branch when finishable=True with unselect cards."""
        harness = HandlerHarness()
        msg_data = {
            "finishable": 1,
            "select_cards": [{"code": 111}],
            "unselect_cards": [{"code": 999}],  # Has unselect cards
        }

        harness._handle_select_unselect_card(None, [], msg_data)

        # Should have finish + select branches
        assert len(harness.recorded_recurses) == 2
        action_types = [r[0].action_type for r in harness.recorded_recurses]
        assert "SELECT_UNSELECT_FINISH" in action_types
        assert "SELECT_UNSELECT_SELECT" in action_types

        # Finish should be first
        assert harness.recorded_recurses[0][0].action_type == "SELECT_UNSELECT_FINISH"
        assert harness.recorded_recurses[0][0].response_value == -1

    def test_no_finish_when_not_finishable(self):
        """Handler should not create finish branch when finishable=False."""
        harness = HandlerHarness()
        msg_data = {
            "finishable": 0,
            "select_cards": [{"code": 111}],
            "unselect_cards": [{"code": 999}],
        }

        harness._handle_select_unselect_card(None, [], msg_data)

        # Only select branches
        assert len(harness.recorded_recurses) == 1
        assert harness.recorded_recurses[0][0].action_type == "SELECT_UNSELECT_SELECT"


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectUnselectCardDeduplication:
    """Tests for _handle_select_unselect_card deduplication behavior."""

    def test_duplicate_codes_one_branch(self):
        """Duplicate card codes should create only one branch."""
        harness = HandlerHarness()
        msg_data = {
            "finishable": 0,
            "select_cards": [
                {"code": 111},
                {"code": 111},  # Duplicate
                {"code": 222},
                {"code": 111},  # Another duplicate
            ],
            "unselect_cards": [],
        }

        harness._handle_select_unselect_card(None, [], msg_data)

        # Should dedupe to 2 unique codes
        assert len(harness.recorded_recurses) == 2
        codes = [r[0].card_code for r in harness.recorded_recurses]
        assert set(codes) == {111, 222}

    def test_response_format_correct(self):
        """Response should be struct.pack('<ii', 1, index)."""
        harness = HandlerHarness()
        msg_data = {
            "finishable": 0,
            "select_cards": [
                {"code": 111},
                {"code": 222},  # index 1
            ],
            "unselect_cards": [],
        }

        harness._handle_select_unselect_card(None, [], msg_data)

        # Check second card response (index 1)
        action = harness.recorded_recurses[1][0]
        assert action.action_type == "SELECT_UNSELECT_SELECT"
        count, index = struct.unpack("<ii", action.response_bytes)
        assert count == 1
        assert index == 1  # Second card


# =============================================================================
# Tests for _handle_select_tribute
# =============================================================================

@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectTributeBasic:
    """Tests for _handle_select_tribute basic functionality."""

    @patch('src.ygo_combo.enumeration.handlers.find_valid_tribute_combinations')
    def test_creates_tribute_branches(self, mock_find_combos):
        """Handler should create one branch per valid tribute combination."""
        mock_find_combos.return_value = [[0], [1], [0, 1]]

        harness = HandlerHarness()
        msg_data = {
            "cards": [
                {"index": 0, "code": 111, "release_param": 1},
                {"index": 1, "code": 222, "release_param": 1},
            ],
            "min": 1,
            "max": 2,
            "cancelable": False,
        }

        harness._handle_select_tribute(None, [], msg_data)

        # Should have 3 branches (3 unique combos)
        assert len(harness.recorded_recurses) == 3
        action_types = [r[0].action_type for r in harness.recorded_recurses]
        assert all(t == "SELECT_TRIBUTE" for t in action_types)

    @patch('src.ygo_combo.enumeration.handlers.find_valid_tribute_combinations')
    def test_cancel_when_cancelable(self, mock_find_combos):
        """Handler should create cancel branch when cancelable=True."""
        mock_find_combos.return_value = [[0]]

        harness = HandlerHarness()
        msg_data = {
            "cards": [{"index": 0, "code": 111, "release_param": 1}],
            "min": 1,
            "max": 1,
            "cancelable": True,
        }

        harness._handle_select_tribute(None, [], msg_data)

        # Should have tribute + cancel
        assert len(harness.recorded_recurses) == 2
        action_types = [r[0].action_type for r in harness.recorded_recurses]
        assert "SELECT_TRIBUTE" in action_types
        assert "SELECT_TRIBUTE_CANCEL" in action_types

    @patch('src.ygo_combo.enumeration.handlers.find_valid_tribute_combinations')
    def test_no_cancel_when_not_cancelable(self, mock_find_combos):
        """Handler should not create cancel branch when cancelable=False."""
        mock_find_combos.return_value = [[0]]

        harness = HandlerHarness()
        msg_data = {
            "cards": [{"index": 0, "code": 111, "release_param": 1}],
            "min": 1,
            "max": 1,
            "cancelable": False,
        }

        harness._handle_select_tribute(None, [], msg_data)

        # Only tribute branch
        assert len(harness.recorded_recurses) == 1
        assert harness.recorded_recurses[0][0].action_type == "SELECT_TRIBUTE"


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectTributeDeduplication:
    """Tests for _handle_select_tribute deduplication behavior."""

    @patch('src.ygo_combo.enumeration.handlers.find_valid_tribute_combinations')
    def test_dedupe_by_sorted_codes(self, mock_find_combos):
        """Same card codes should produce one branch (deduplication)."""
        # Two combos with same codes but different indices
        mock_find_combos.return_value = [[0, 2], [1, 3]]  # Both produce (111, 111)

        harness = HandlerHarness()
        msg_data = {
            "cards": [
                {"index": 0, "code": 111, "release_param": 1},
                {"index": 1, "code": 111, "release_param": 1},
                {"index": 2, "code": 111, "release_param": 1},
                {"index": 3, "code": 111, "release_param": 1},
            ],
            "min": 2,
            "max": 2,
            "cancelable": False,
        }

        harness._handle_select_tribute(None, [], msg_data)

        # Should dedupe to 1 branch (all same codes)
        assert len(harness.recorded_recurses) == 1
        assert harness.recorded_recurses[0][0].action_type == "SELECT_TRIBUTE"

    @patch('src.ygo_combo.enumeration.handlers.find_valid_tribute_combinations')
    def test_different_codes_different_branches(self, mock_find_combos):
        """Different card codes should produce separate branches."""
        mock_find_combos.return_value = [[0], [1]]  # Different codes

        harness = HandlerHarness()
        msg_data = {
            "cards": [
                {"index": 0, "code": 111, "release_param": 1},
                {"index": 1, "code": 222, "release_param": 1},
            ],
            "min": 1,
            "max": 1,
            "cancelable": False,
        }

        harness._handle_select_tribute(None, [], msg_data)

        # 2 unique code combos
        assert len(harness.recorded_recurses) == 2


@patch('src.ygo_combo.enumeration.handlers.get_card_name', mock_get_card_name)
class TestHandleSelectTributeFallback:
    """Tests for _handle_select_tribute fallback behavior."""

    @patch('src.ygo_combo.enumeration.handlers.find_valid_tribute_combinations')
    def test_fallback_when_no_valid_combos(self, mock_find_combos):
        """Handler should create fallback when no valid combos and not cancelable."""
        mock_find_combos.return_value = []  # No valid combos

        harness = HandlerHarness()
        msg_data = {
            "cards": [
                {"index": 0, "code": 111, "release_param": 1},
                {"index": 1, "code": 222, "release_param": 1},
            ],
            "min": 1,
            "max": 2,
            "cancelable": False,
        }

        harness._handle_select_tribute(None, [], msg_data)

        assert len(harness.recorded_recurses) == 1
        assert harness.recorded_recurses[0][0].action_type == "SELECT_TRIBUTE_FALLBACK"
        assert "Fallback" in harness.recorded_recurses[0][0].description

    @patch('src.ygo_combo.enumeration.handlers.find_valid_tribute_combinations')
    def test_no_fallback_when_cancelable(self, mock_find_combos):
        """Handler should not create fallback when cancelable (cancel option exists)."""
        mock_find_combos.return_value = []  # No valid combos

        harness = HandlerHarness()
        msg_data = {
            "cards": [{"index": 0, "code": 111, "release_param": 1}],
            "min": 1,
            "max": 1,
            "cancelable": True,
        }

        harness._handle_select_tribute(None, [], msg_data)

        # Should have cancel only, no fallback
        assert len(harness.recorded_recurses) == 1
        assert harness.recorded_recurses[0][0].action_type == "SELECT_TRIBUTE_CANCEL"
