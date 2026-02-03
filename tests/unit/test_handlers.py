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
