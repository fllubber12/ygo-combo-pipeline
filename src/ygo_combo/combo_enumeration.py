#!/usr/bin/env python3
"""
Exhaustive Combo Enumeration Engine

Explores ALL possible action sequences from a starting game state.
No AI makes decisions - code explores every legal path.

Key design:
- Forward replay (no save/restore)
- Branch at IDLE (all actions + PASS) and SELECT_CARD (all choices)
- Auto-decline chains (opponent has no responses)
- PASS creates terminal states

TODO (Phase 6 Refactoring):
    Consider splitting this module for parallelization:
    - enumeration_engine.py: Core EnumerationEngine class
    - message_handlers.py: _handle_idle, _handle_select_card, etc.
    - response_builders.py: build_activate_response, build_pass_response, etc.
    - message_parsers.py: parse_idle, parse_select_card, etc.
"""

import json
import struct
import hashlib
import io
import logging
import signal
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple, Union, BinaryIO
from datetime import datetime

# Import shared types to avoid circular imports
# These are re-exported for backwards compatibility
try:
    from .types import Action, TerminalState
except ImportError:
    from types import Action, TerminalState

# Configure module logger
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
_shutdown_requested = False


def _signal_handler(signum, frame):
    """Handle interrupt signals for graceful shutdown."""
    global _shutdown_requested
    if not _shutdown_requested:
        print("\n\nShutdown requested - finishing current path and saving results...")
        _shutdown_requested = True
    else:
        print("\nForce quit - results may be incomplete.")
        raise KeyboardInterrupt

# Import from engine interface (production code, not test file)
# Support both relative imports (package) and absolute imports (sys.path)
try:
    from .engine.interface import (
        init_card_database, load_library, preload_utility_scripts,
        py_card_reader, py_card_reader_done, py_script_reader, py_log_handler,
        ffi, get_card_name, set_lib,
    )
    from .engine.bindings import (
        LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA, LOCATION_MZONE,
        LOCATION_GRAVE, LOCATION_SZONE, LOCATION_REMOVED,
        POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
        QUERY_CODE, QUERY_POSITION, QUERY_ATTACK, QUERY_DEFENSE, QUERY_END,
        MSG_SELECT_BATTLECMD, MSG_IDLE, MSG_SELECT_CARD, MSG_SELECT_CHAIN,
        MSG_SELECT_PLACE, MSG_SELECT_POSITION, MSG_SELECT_TRIBUTE,
        MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO, MSG_SELECT_OPTION,
        MSG_SELECT_COUNTER, MSG_SELECT_UNSELECT_CARD, MSG_SELECT_SUM,
        MSG_SORT_CARD, MSG_SELECT_DISFIELD,
        MSG_RETRY, MSG_HINT, MSG_WAITING, MSG_START, MSG_WIN,
        MSG_UPDATE_DATA, MSG_UPDATE_CARD,
        MSG_CONFIRM_DECKTOP, MSG_CONFIRM_CARDS, MSG_SHUFFLE_DECK, MSG_SHUFFLE_HAND,
        MSG_REFRESH_DECK, MSG_SWAP_GRAVE_DECK, MSG_SHUFFLE_SET_CARD, MSG_REVERSE_DECK,
        MSG_DECK_TOP, MSG_SHUFFLE_EXTRA,
        MSG_NEW_TURN, MSG_NEW_PHASE, MSG_CONFIRM_EXTRATOP,
        MSG_MOVE, MSG_POS_CHANGE, MSG_SET, MSG_SWAP, MSG_FIELD_DISABLED,
        MSG_SUMMONING, MSG_SUMMONED, MSG_SPSUMMONING, MSG_SPSUMMONED,
        MSG_FLIPSUMMONING, MSG_FLIPSUMMONED,
        MSG_CHAINING, MSG_CHAINED, MSG_CHAIN_SOLVING, MSG_CHAIN_SOLVED,
        MSG_CHAIN_END, MSG_CHAIN_NEGATED, MSG_CHAIN_DISABLED,
        MSG_CARD_SELECTED, MSG_RANDOM_SELECTED, MSG_BECOME_TARGET,
        MSG_DRAW, MSG_DAMAGE, MSG_RECOVER, MSG_EQUIP, MSG_LPUPDATE, MSG_UNEQUIP,
        MSG_CARD_TARGET, MSG_CANCEL_TARGET, MSG_PAY_LPCOST,
        MSG_ADD_COUNTER, MSG_REMOVE_COUNTER,
        MSG_ATTACK, MSG_BATTLE, MSG_ATTACK_DISABLED,
        MSG_DAMAGE_STEP_START, MSG_DAMAGE_STEP_END,
        MSG_MISSED_EFFECT, MSG_BE_CHAIN_TARGET, MSG_CREATE_RELATION, MSG_RELEASE_RELATION,
        MSG_TOSS_COIN, MSG_TOSS_DICE, MSG_ROCK_PAPER_SCISSORS, MSG_HAND_RES,
        MSG_ANNOUNCE_RACE, MSG_ANNOUNCE_ATTRIB, MSG_ANNOUNCE_CARD, MSG_ANNOUNCE_NUMBER,
        MSG_CARD_HINT, MSG_TAG_SWAP, MSG_RELOAD_FIELD, MSG_AI_NAME,
        MSG_SHOW_HINT, MSG_PLAYER_HINT, MSG_MATCH_KILL, MSG_CUSTOM_MSG, MSG_REMOVE_CARDS,
    )
    from .engine.state import (
        BoardSignature, IntermediateState, ActionSpec,
        evaluate_board_quality, BOSS_MONSTERS, INTERACTION_PIECES,
    )
    from .engine.board_capture import (
        parse_query_response, compute_board_signature,
        compute_idle_state_hash, capture_board_state,
    )
    from .engine.duel_factory import (
        ENGRAVER, HOLACTIE,
        load_locked_library, get_deck_lists, create_duel,
    )
    from .search.transposition import TranspositionTable, TranspositionEntry
    from .cards.validator import CardValidator
    from .enumeration import (
        read_u8, read_u16, read_u32, read_i32, read_u64,
        parse_idle, parse_select_card, parse_select_chain, parse_select_place,
        parse_select_unselect_card, parse_select_option, parse_select_tribute,
        parse_select_sum, find_valid_tribute_combinations,
        find_valid_sum_combinations, find_sum_combinations_flexible,
        IDLE_RESPONSE_SUMMON, IDLE_RESPONSE_SPSUMMON, IDLE_RESPONSE_REPOSITION,
        IDLE_RESPONSE_MSET, IDLE_RESPONSE_SSET, IDLE_RESPONSE_ACTIVATE,
        IDLE_RESPONSE_TO_BATTLE, IDLE_RESPONSE_TO_END,
        build_activate_response, build_pass_response, build_select_card_response,
        build_decline_chain_response, build_select_tribute_response,
    )
    from .enumeration.handlers import MessageHandlerMixin
except ImportError:
    # Fallback for direct execution (sys.path includes src/ygo_combo)
    from engine.interface import (
        init_card_database, load_library, preload_utility_scripts,
        py_card_reader, py_card_reader_done, py_script_reader, py_log_handler,
        ffi, get_card_name, set_lib,
    )
    from engine.bindings import (
        LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA, LOCATION_MZONE,
        LOCATION_GRAVE, LOCATION_SZONE, LOCATION_REMOVED,
        POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
        QUERY_CODE, QUERY_POSITION, QUERY_ATTACK, QUERY_DEFENSE, QUERY_END,
        MSG_SELECT_BATTLECMD, MSG_IDLE, MSG_SELECT_CARD, MSG_SELECT_CHAIN,
        MSG_SELECT_PLACE, MSG_SELECT_POSITION, MSG_SELECT_TRIBUTE,
        MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO, MSG_SELECT_OPTION,
        MSG_SELECT_COUNTER, MSG_SELECT_UNSELECT_CARD, MSG_SELECT_SUM,
        MSG_SORT_CARD, MSG_SELECT_DISFIELD,
        MSG_RETRY, MSG_HINT, MSG_WAITING, MSG_START, MSG_WIN,
        MSG_UPDATE_DATA, MSG_UPDATE_CARD,
        MSG_CONFIRM_DECKTOP, MSG_CONFIRM_CARDS, MSG_SHUFFLE_DECK, MSG_SHUFFLE_HAND,
        MSG_REFRESH_DECK, MSG_SWAP_GRAVE_DECK, MSG_SHUFFLE_SET_CARD, MSG_REVERSE_DECK,
        MSG_DECK_TOP, MSG_SHUFFLE_EXTRA,
        MSG_NEW_TURN, MSG_NEW_PHASE, MSG_CONFIRM_EXTRATOP,
        MSG_MOVE, MSG_POS_CHANGE, MSG_SET, MSG_SWAP, MSG_FIELD_DISABLED,
        MSG_SUMMONING, MSG_SUMMONED, MSG_SPSUMMONING, MSG_SPSUMMONED,
        MSG_FLIPSUMMONING, MSG_FLIPSUMMONED,
        MSG_CHAINING, MSG_CHAINED, MSG_CHAIN_SOLVING, MSG_CHAIN_SOLVED,
        MSG_CHAIN_END, MSG_CHAIN_NEGATED, MSG_CHAIN_DISABLED,
        MSG_CARD_SELECTED, MSG_RANDOM_SELECTED, MSG_BECOME_TARGET,
        MSG_DRAW, MSG_DAMAGE, MSG_RECOVER, MSG_EQUIP, MSG_LPUPDATE, MSG_UNEQUIP,
        MSG_CARD_TARGET, MSG_CANCEL_TARGET, MSG_PAY_LPCOST,
        MSG_ADD_COUNTER, MSG_REMOVE_COUNTER,
        MSG_ATTACK, MSG_BATTLE, MSG_ATTACK_DISABLED,
        MSG_DAMAGE_STEP_START, MSG_DAMAGE_STEP_END,
        MSG_MISSED_EFFECT, MSG_BE_CHAIN_TARGET, MSG_CREATE_RELATION, MSG_RELEASE_RELATION,
        MSG_TOSS_COIN, MSG_TOSS_DICE, MSG_ROCK_PAPER_SCISSORS, MSG_HAND_RES,
        MSG_ANNOUNCE_RACE, MSG_ANNOUNCE_ATTRIB, MSG_ANNOUNCE_CARD, MSG_ANNOUNCE_NUMBER,
        MSG_CARD_HINT, MSG_TAG_SWAP, MSG_RELOAD_FIELD, MSG_AI_NAME,
        MSG_SHOW_HINT, MSG_PLAYER_HINT, MSG_MATCH_KILL, MSG_CUSTOM_MSG, MSG_REMOVE_CARDS,
    )
    from engine.state import (
        BoardSignature, IntermediateState, ActionSpec,
        evaluate_board_quality, BOSS_MONSTERS, INTERACTION_PIECES,
    )
    from engine.board_capture import (
        parse_query_response, compute_board_signature,
        compute_idle_state_hash, capture_board_state,
    )
    from engine.duel_factory import (
        ENGRAVER, HOLACTIE,
        load_locked_library, get_deck_lists, create_duel,
    )
    from search.transposition import TranspositionTable, TranspositionEntry
    from cards.validator import CardValidator
    from enumeration import (
        read_u8, read_u16, read_u32, read_i32, read_u64,
        parse_idle, parse_select_card, parse_select_chain, parse_select_place,
        parse_select_unselect_card, parse_select_option, parse_select_tribute,
        parse_select_sum, find_valid_tribute_combinations,
        find_valid_sum_combinations, find_sum_combinations_flexible,
        IDLE_RESPONSE_SUMMON, IDLE_RESPONSE_SPSUMMON, IDLE_RESPONSE_REPOSITION,
        IDLE_RESPONSE_MSET, IDLE_RESPONSE_SSET, IDLE_RESPONSE_ACTIVATE,
        IDLE_RESPONSE_TO_BATTLE, IDLE_RESPONSE_TO_END,
        build_activate_response, build_pass_response, build_select_card_response,
        build_decline_chain_response, build_select_tribute_response,
    )
    from enumeration.handlers import MessageHandlerMixin


# =============================================================================
# MESSAGE TYPE NAMES (for debugging)
# =============================================================================

MSG_TYPE_NAMES = {
    11: "MSG_IDLE",
    12: "MSG_SELECT_EFFECTYN",
    13: "MSG_SELECT_YESNO",
    14: "MSG_SELECT_OPTION",
    15: "MSG_SELECT_CARD",
    16: "MSG_SELECT_CHAIN",
    17: "MSG_SELECT_TRIBUTE",
    18: "MSG_SELECT_PLACE",
    19: "MSG_SELECT_POSITION",
    22: "MSG_SELECT_COUNTER",
    23: "MSG_SELECT_SUM",
    24: "MSG_SELECT_DISFIELD",
    25: "MSG_SORT_CARD",
    26: "MSG_SELECT_UNSELECT_CARD",
}


# =============================================================================
# CONFIGURATION
# =============================================================================

MAX_DEPTH = 50          # Maximum actions per path
MAX_PATHS = 100000      # Maximum paths to explore (safety limit)
MAX_ITERATIONS = 1000   # Maximum engine iterations per action

# Informational messages that don't require responses (for _explore_from_state)
INFORMATIONAL_MESSAGES = {
    MSG_HINT, MSG_WAITING, MSG_START, MSG_WIN, MSG_UPDATE_DATA, MSG_UPDATE_CARD,
    MSG_CONFIRM_DECKTOP, MSG_CONFIRM_CARDS, MSG_SHUFFLE_DECK, MSG_SHUFFLE_HAND,
    MSG_REFRESH_DECK, MSG_SWAP_GRAVE_DECK, MSG_SHUFFLE_SET_CARD, MSG_REVERSE_DECK,
    MSG_DECK_TOP, MSG_SHUFFLE_EXTRA, MSG_NEW_TURN, MSG_NEW_PHASE, MSG_CONFIRM_EXTRATOP,
    MSG_MOVE, MSG_POS_CHANGE, MSG_SET, MSG_SWAP, MSG_FIELD_DISABLED,
    MSG_SUMMONING, MSG_SUMMONED, MSG_SPSUMMONING, MSG_SPSUMMONED,
    MSG_FLIPSUMMONING, MSG_FLIPSUMMONED, MSG_CHAINING, MSG_CHAINED,
    MSG_CHAIN_SOLVING, MSG_CHAIN_SOLVED, MSG_CHAIN_END, MSG_CHAIN_NEGATED, MSG_CHAIN_DISABLED,
    MSG_CARD_SELECTED, MSG_RANDOM_SELECTED, MSG_BECOME_TARGET,
    MSG_DRAW, MSG_DAMAGE, MSG_RECOVER, MSG_EQUIP, MSG_LPUPDATE, MSG_UNEQUIP,
    MSG_CARD_TARGET, MSG_CANCEL_TARGET, MSG_PAY_LPCOST, MSG_ADD_COUNTER, MSG_REMOVE_COUNTER,
    MSG_ATTACK, MSG_BATTLE, MSG_ATTACK_DISABLED, MSG_DAMAGE_STEP_START, MSG_DAMAGE_STEP_END,
    MSG_MISSED_EFFECT, MSG_BE_CHAIN_TARGET, MSG_CREATE_RELATION, MSG_RELEASE_RELATION,
    MSG_TOSS_COIN, MSG_TOSS_DICE, MSG_ROCK_PAPER_SCISSORS, MSG_HAND_RES,
    MSG_ANNOUNCE_RACE, MSG_ANNOUNCE_ATTRIB, MSG_ANNOUNCE_CARD, MSG_ANNOUNCE_NUMBER,
    MSG_CARD_HINT, MSG_TAG_SWAP, MSG_RELOAD_FIELD, MSG_AI_NAME, MSG_SHOW_HINT, MSG_PLAYER_HINT,
    MSG_MATCH_KILL, MSG_CUSTOM_MSG, MSG_REMOVE_CARDS,
}


# =============================================================================
# ENUMERATION ENGINE
# =============================================================================

class EnumerationEngine(MessageHandlerMixin):
    """Exhaustive combo path enumeration with deduplication optimizations.

    Inherits message handling methods from MessageHandlerMixin.
    """

    def __init__(self, lib, main_deck, extra_deck, verbose=False, dedupe_boards=True, dedupe_intermediate=True,
                 prioritize_cards=None):
        self.lib = lib
        self.main_deck = main_deck
        self.extra_deck = extra_deck
        self.verbose = verbose
        self.dedupe_boards = dedupe_boards  # Skip duplicate terminal board states
        self.dedupe_intermediate = dedupe_intermediate  # Skip duplicate intermediate states

        # Card prioritization for SELECT_CARD - these codes are explored first
        # Format: list of card passcodes to prioritize (explored in order given)
        self.prioritize_cards = set(prioritize_cards) if prioritize_cards else set()
        self.prioritize_order = list(prioritize_cards) if prioritize_cards else []

        self.terminals = []         # All terminal states found
        self.paths_explored = 0     # Counter
        self.max_depth_seen = 0     # Deepest path
        self.seen_board_sigs = set()  # Board signatures already recorded (terminals)

        # Transposition table for intermediate state deduplication
        self.transposition_table = TranspositionTable(max_size=1_000_000)

        # Group terminals by board signature
        self.terminal_boards: Dict[str, List] = {}  # board_hash -> list of action sequences

        self.duplicate_boards_skipped = 0  # Counter for stats
        self.intermediate_states_pruned = 0  # Counter for intermediate pruning

        # Failed choice tracking for SELECT_SUM_CANCEL backtracking
        # Maps (context_hash) -> set of failed card codes
        # Context hash identifies the SELECT_CARD prompt (based on available cards)
        self.failed_at_context: Dict[int, set] = {}

        # Custom starting hand (None = use default)
        self._starting_hand = None

    def _recurse(self, action_history: List[Action]):
        """Call the appropriate recursive method based on whether custom hand is set."""
        if self._starting_hand is not None:
            self._enumerate_recursive_with_hand(action_history)
        else:
            self._enumerate_recursive(action_history)

    def log(self, msg, depth=0):
        if self.verbose:
            indent = "  " * depth
            print(f"{indent}{msg}")

    def _compute_select_card_context(self, select_data: dict) -> int:
        """Compute a context hash for a SELECT_CARD prompt.

        The context identifies this specific decision point based on:
        - Which cards are available to select
        - The selection constraints (min/max)

        This allows us to track which cards have failed at THIS decision point,
        even if we reach it via different paths.
        """
        cards = select_data.get("cards", [])
        codes = tuple(sorted(card.get("code", 0) for card in cards))
        min_sel = select_data.get("min", 1)
        max_sel = select_data.get("max", 1)
        return hash((codes, min_sel, max_sel))

    def _mark_card_failed_at_context(self, context_hash: int, card_code: int):
        """Mark a card as failed at a specific SELECT_CARD context.

        Called when a SELECT_CARD choice leads to SELECT_SUM_CANCEL.
        """
        if context_hash not in self.failed_at_context:
            self.failed_at_context[context_hash] = set()
        self.failed_at_context[context_hash].add(card_code)

    def _get_failed_cards_at_context(self, context_hash: int) -> set:
        """Get the set of cards that have failed at this context."""
        return self.failed_at_context.get(context_hash, set())

    def enumerate_all(self):
        """Main entry point - enumerate all paths from starting state."""
        print("=" * 80)
        print("STARTING ENUMERATION")
        print(f"Max depth: {MAX_DEPTH}")
        print(f"Max paths: {MAX_PATHS}")
        print("=" * 80)

        self._enumerate_recursive([])

        print("\n" + "=" * 80)
        print("ENUMERATION COMPLETE")
        print(f"Paths explored: {self.paths_explored}")
        print(f"Terminal states: {len(self.terminals)} unique boards")
        print(f"Unique board signatures: {len(self.terminal_boards)}")
        if self.dedupe_boards:
            print(f"Duplicate terminal boards skipped: {self.duplicate_boards_skipped}")
        if self.dedupe_intermediate:
            tt_stats = self.transposition_table.stats()
            print(f"Intermediate states pruned: {self.intermediate_states_pruned}")
            print(f"Transposition table: {tt_stats['size']} entries, "
                  f"{tt_stats['hit_rate']:.1%} hit rate")
        print(f"Max depth seen: {self.max_depth_seen}")
        print("=" * 80)

        return self.terminals

    def enumerate_from_hand(self, starting_hand: List[int]) -> List[TerminalState]:
        """
        Enumerate combos from a specific starting hand.

        Args:
            starting_hand: List of up to 5 card passcodes for starting hand.
                          Will be padded with HOLACTIE if less than 5 cards.

        Returns:
            List of terminal states (completed combo boards).

        Example:
            # Test Engraver + Terrortop opener
            hand = [60764609, 81275020, 14558127, 14558127, 14558127]
            results = engine.enumerate_from_hand(hand)
        """
        if not starting_hand:
            raise ValueError("Hand cannot be empty")

        if len(starting_hand) > 5:
            logger.warning(f"Hand has {len(starting_hand)} cards, truncating to 5")
            starting_hand = starting_hand[:5]

        # Store the starting hand for create_duel calls
        self._starting_hand = list(starting_hand)

        # Reset state for fresh enumeration
        self.terminals = []
        self.paths_explored = 0
        self.max_depth_seen = 0
        self.seen_board_sigs = set()
        self.terminal_boards = {}
        self.duplicate_boards_skipped = 0
        self.intermediate_states_pruned = 0
        self.transposition_table = TranspositionTable(max_size=1_000_000)

        print("=" * 80)
        print("ENUMERATE FROM HAND")
        print(f"Hand: {starting_hand}")
        print(f"Max depth: {MAX_DEPTH}")
        print(f"Max paths: {MAX_PATHS}")
        print("=" * 80)

        self._enumerate_recursive_with_hand([])

        print("\n" + "=" * 80)
        print("ENUMERATION COMPLETE")
        print(f"Paths explored: {self.paths_explored}")
        print(f"Terminal states: {len(self.terminals)} unique boards")
        print(f"Max depth seen: {self.max_depth_seen}")
        print("=" * 80)

        return self.terminals

    def _enumerate_recursive_with_hand(self, action_history: List[Action]):
        """Recursively explore all paths using stored starting hand."""
        global _shutdown_requested

        # Check for graceful shutdown
        if _shutdown_requested:
            return

        # Safety limits
        if len(action_history) >= MAX_DEPTH:
            self._record_terminal(action_history, "MAX_DEPTH")
            return

        if self.paths_explored >= MAX_PATHS:
            return

        self.paths_explored += 1
        self.max_depth_seen = max(self.max_depth_seen, len(action_history))

        if self.paths_explored % 100 == 0:
            print(f"  Progress: {self.paths_explored} paths, {len(self.terminals)} terminals")

        # Create fresh duel with the specific starting hand
        duel = create_duel(self.lib, self.main_deck, self.extra_deck,
                           starting_hand=self._starting_hand)

        try:
            # Start duel
            self.lib.OCG_StartDuel(duel)

            # Replay all previous actions
            for action in action_history:
                if not self._replay_action(duel, action):
                    self.log(f"Replay failed at action: {action.description}", len(action_history))
                    return

            # Now explore from current state
            self._explore_from_state(duel, action_history)

        finally:
            self.lib.OCG_DestroyDuel(duel)

    def _enumerate_recursive(self, action_history: List[Action]):
        """Recursively explore all paths from current action history."""
        global _shutdown_requested

        # Check for graceful shutdown
        if _shutdown_requested:
            return

        # Safety limits
        if len(action_history) >= MAX_DEPTH:
            self._record_terminal(action_history, "MAX_DEPTH")
            return

        if self.paths_explored >= MAX_PATHS:
            return

        self.paths_explored += 1
        self.max_depth_seen = max(self.max_depth_seen, len(action_history))

        if self.paths_explored % 100 == 0:
            print(f"  Progress: {self.paths_explored} paths, {len(self.terminals)} terminals")

        # Create fresh duel and replay action history
        duel = create_duel(self.lib, self.main_deck, self.extra_deck)

        try:
            # Start duel
            self.lib.OCG_StartDuel(duel)

            # Replay all previous actions
            for action in action_history:
                if not self._replay_action(duel, action):
                    self.log(f"Replay failed at action: {action.description}", len(action_history))
                    return

            # Now explore from current state
            self._explore_from_state(duel, action_history)

        finally:
            self.lib.OCG_DestroyDuel(duel)

    def _replay_action(self, duel, action: Action) -> bool:
        """Replay a single action, handling any intermediate prompts."""

        # Process until we need the action's response
        for _ in range(MAX_ITERATIONS):
            status = self.lib.OCG_DuelProcess(duel)
            messages = self._get_messages(duel)

            for msg_type, msg_data in messages:
                if msg_type == MSG_SELECT_CHAIN:
                    # Auto-decline chains during replay
                    _, response = build_decline_chain_response()
                    self.lib.OCG_DuelSetResponse(duel, response, len(response))
                    break
                elif msg_type == action.message_type:
                    # This is the prompt we need to respond to
                    self.lib.OCG_DuelSetResponse(duel, action.response_bytes, len(action.response_bytes))
                    return True

            if status == 0:  # DUEL_END
                return True
            elif status == 1 and not messages:  # AWAITING but no messages?
                return False

        return False  # Max iterations

    def _explore_from_state(self, duel, action_history: List[Action]):
        """Explore all branches from current duel state."""
        for iteration in range(MAX_ITERATIONS):
            status = self.lib.OCG_DuelProcess(duel)
            messages = self._get_messages(duel)

            decision_found = False

            for msg_type, msg_data in messages:

                # Skip informational messages
                if msg_type in INFORMATIONAL_MESSAGES:
                    continue

                if msg_type == MSG_IDLE:
                    self._handle_idle(duel, action_history, msg_data)
                    return  # Branching handled

                elif msg_type == MSG_SELECT_CARD:
                    self._handle_select_card(duel, action_history, msg_data)
                    return  # Branching handled

                elif msg_type == MSG_SELECT_CHAIN:
                    # Auto-decline chain (opponent has no responses)
                    _, response = build_decline_chain_response()
                    self.lib.OCG_DuelSetResponse(duel, response, len(response))
                    decision_found = True
                    # Continue processing - don't return, need to process more

                elif msg_type == MSG_SELECT_PLACE:
                    self._handle_select_place(duel, action_history, msg_data)
                    return

                elif msg_type == MSG_SELECT_POSITION:
                    self._handle_select_position(duel, action_history, msg_data)
                    return

                elif msg_type in (MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO):
                    self._handle_yes_no(duel, action_history, msg_data, msg_type)
                    return

                elif msg_type == MSG_SELECT_OPTION:
                    self._handle_select_option(duel, action_history, msg_data)
                    return

                elif msg_type == MSG_SELECT_UNSELECT_CARD:
                    self._handle_select_unselect_card(duel, action_history, msg_data)
                    return

                elif msg_type == MSG_SELECT_SUM:
                    self._handle_select_sum(duel, action_history, msg_data)
                    return

                elif msg_type == MSG_SELECT_TRIBUTE:
                    self._handle_select_tribute(duel, action_history, msg_data)
                    return

                elif msg_type == 12:
                    # Legacy message type - treat as yes/no or option selection
                    # Some ygopro-core versions use 12 for effect confirmation
                    self._handle_legacy_message_12(duel, action_history, msg_data)
                    return

                elif msg_type == MSG_RETRY:
                    self.log(f"RETRY: Invalid response at depth {len(action_history)}", len(action_history))
                    return  # Stop this path

                else:
                    # Unknown message type - log with name if known
                    msg_name = MSG_TYPE_NAMES.get(msg_type, "UNKNOWN")
                    self.log(f"Unhandled message type {msg_type} ({msg_name})", len(action_history))

            if status == 0:  # DUEL_END
                self._record_terminal(action_history, "DUEL_END")
                return
            elif status == 1 and not decision_found:  # AWAITING but nothing handled
                if not messages:
                    self.log(f"AWAITING with no messages at depth {len(action_history)}", len(action_history))
                return
            # status == 2 means CONTINUE - keep processing

    # =========================================================================
    # MESSAGE HANDLERS - Now in enumeration/handlers.py
    # =========================================================================
    # All _handle_* methods are now inherited from MessageHandlerMixin.
    # See: src/ygo_combo/enumeration/handlers.py
    #
    # Methods provided by mixin:
    #   _handle_idle, _handle_select_card, _handle_select_place,
    #   _handle_select_position, _handle_yes_no, _handle_select_option,
    #   _handle_select_unselect_card, _handle_select_sum, _handle_select_tribute,
    #   _handle_legacy_message_12

    def _get_messages(self, duel):
        """Get all pending messages from engine."""
        messages = []

        length = ffi.new("uint32_t*")
        buf = self.lib.OCG_DuelGetMessage(duel, length)

        if length[0] == 0:
            return messages

        data = bytes(ffi.buffer(buf, length[0]))
        stream = io.BytesIO(data)

        while stream.tell() < len(data):
            # Each message has length prefix
            if stream.tell() + 4 > len(data):
                break
            msg_len = read_u32(stream)
            if msg_len == 0:
                break

            msg_start = stream.tell()
            msg_type = read_u8(stream)

            # Read message body
            remaining = msg_len - 1  # Already read msg_type
            msg_body = stream.read(remaining)

            if msg_type == MSG_IDLE:
                msg_data = parse_idle(msg_body)
                messages.append((MSG_IDLE, msg_data))
            elif msg_type == MSG_SELECT_CARD:
                msg_data = parse_select_card(msg_body)
                messages.append((MSG_SELECT_CARD, msg_data))
            elif msg_type == MSG_SELECT_CHAIN:
                msg_data = parse_select_chain(msg_body)
                messages.append((MSG_SELECT_CHAIN, msg_data))
            elif msg_type == MSG_SELECT_PLACE:
                msg_data = parse_select_place(msg_body)
                messages.append((MSG_SELECT_PLACE, msg_data))
            elif msg_type == MSG_SELECT_UNSELECT_CARD:
                msg_data = parse_select_unselect_card(msg_body)
                messages.append((MSG_SELECT_UNSELECT_CARD, msg_data))
            elif msg_type == MSG_SELECT_OPTION:
                msg_data = parse_select_option(msg_body)
                messages.append((MSG_SELECT_OPTION, msg_data))
            elif msg_type == MSG_SELECT_SUM:
                msg_data = parse_select_sum(msg_body)
                msg_data["_raw"] = msg_body.hex()  # Debug: include raw bytes
                messages.append((MSG_SELECT_SUM, msg_data))
            elif msg_type == MSG_SELECT_TRIBUTE:
                msg_data = parse_select_tribute(msg_body)
                messages.append((MSG_SELECT_TRIBUTE, msg_data))
            elif msg_type == 12:
                # Legacy message type - pass raw data for handler
                msg_data = {"raw": msg_body}
                messages.append((12, msg_data))
            else:
                # Unhandled message type
                messages.append((msg_type, None))

        return messages

    def _record_terminal(self, action_history: List[Action], reason: str):
        """Record a terminal state with full board capture.

        If dedupe_boards is enabled, skips recording if we've already
        seen an identical board state (reached via a different path).
        """

        # Create state hash from action sequence
        action_str = "|".join(a.description for a in action_history)
        state_hash = hashlib.md5(action_str.encode()).hexdigest()[:16]

        # Capture board state by replaying actions
        board_state = {}
        if action_history:
            duel = create_duel(self.lib, self.main_deck, self.extra_deck)
            try:
                self.lib.OCG_StartDuel(duel)
                # Replay all actions
                for action in action_history:
                    self._replay_action(duel, action)
                # Capture the final board state
                board_state = capture_board_state(self.lib, duel)
            except Exception as e:
                self.log(f"Board capture failed: {e}", len(action_history))
            finally:
                self.lib.OCG_DestroyDuel(duel)

        # Check for duplicate board state using BoardSignature
        board_hash = None
        if board_state:
            sig = BoardSignature.from_board_state(board_state)
            board_hash = sig.hash()

            # Group by board signature
            if board_hash not in self.terminal_boards:
                self.terminal_boards[board_hash] = []
            self.terminal_boards[board_hash].append(action_history)

            if self.dedupe_boards:
                if board_hash in self.seen_board_sigs:
                    self.duplicate_boards_skipped += 1
                    if self.verbose:
                        logger.debug(f"SKIPPED duplicate board at depth {len(action_history)}")
                    return  # Skip recording this duplicate
                self.seen_board_sigs.add(board_hash)

        terminal = TerminalState(
            action_sequence=action_history,
            board_state=board_state,
            depth=len(action_history),
            state_hash=state_hash,
            termination_reason=reason,
            board_hash=board_hash,  # Add board hash for reference
        )

        self.terminals.append(terminal)

        if self.verbose:
            # Show board summary
            p0 = board_state.get("player0", {})
            monsters = [c["name"] for c in p0.get("monsters", [])]
            gy = [c["name"] for c in p0.get("graveyard", [])]
            print(f"  TERMINAL [{reason}] depth={len(action_history)}: "
                  f"Field={monsters}, GY={gy}")


# =============================================================================
# PARALLEL WORKER ENTRY POINT
# =============================================================================

def enumerate_from_hand(
    hand: Tuple[int, ...],
    deck: List[int] = None,
    max_depth: int = 25,
    max_paths: int = 0,
) -> Dict[str, Any]:
    """Enumerate all combos from a specific starting hand.

    This is the worker-compatible entry point for parallel enumeration.
    Creates a fresh engine context, sets up the hand, and runs DFS.

    Args:
        hand: Tuple of card passcodes for starting hand.
        deck: Full deck list (optional, uses locked library if None).
        max_depth: Maximum search depth.
        max_paths: Maximum paths to explore (0 = unlimited).

    Returns:
        Dict with:
            - terminal_hashes: List of unique terminal board hashes
            - best_score: Highest board evaluation score
            - paths_explored: Number of paths explored
            - max_depth_reached: Deepest point in search tree
    """
    global MAX_DEPTH, MAX_PATHS

    # Override global limits with function parameters
    original_max_depth = MAX_DEPTH
    original_max_paths = MAX_PATHS
    MAX_DEPTH = max_depth
    MAX_PATHS = max_paths if max_paths > 0 else 100000

    terminal_hashes: List[str] = []
    best_score = 0.0
    paths_explored = 0
    max_depth_reached = 0

    try:
        # Initialize card database if not already done
        init_card_database()

        # Load library and get deck lists
        library = load_locked_library()
        main_deck, extra_deck = get_deck_lists(library)

        # Load the shared library
        lib = load_library()
        set_lib(lib)

        # Create engine with library deck
        engine = EnumerationEngine(
            lib=lib,
            main_deck=main_deck,
            extra_deck=extra_deck,
            verbose=False,
            dedupe_boards=True,
            dedupe_intermediate=True,
        )

        # Run enumeration from specific hand
        terminals = engine.enumerate_from_hand(list(hand))

        # Extract results
        paths_explored = engine.paths_explored
        max_depth_reached = engine.max_depth_seen

        # Collect terminal hashes and find best score
        for terminal in terminals:
            if terminal.board_hash:
                terminal_hashes.append(terminal.board_hash)

            # Evaluate board quality if we have board state
            if terminal.board_state:
                try:
                    # Build signature for evaluation
                    player_data = terminal.board_state.get("player0", {})
                    monsters = frozenset(m.get("code", 0) for m in player_data.get("monsters", []))
                    sig = BoardSignature(
                        monsters=monsters,
                        spells=frozenset(),
                        graveyard=frozenset(),
                        hand=frozenset(),
                        banished=frozenset(),
                        extra_deck=frozenset(),
                        equips=frozenset(),
                    )
                    eval_result = evaluate_board_quality(sig)
                    score = eval_result.get("score", 0.0)
                    if score > best_score:
                        best_score = score
                except Exception:
                    pass

    except Exception as e:
        logger.warning(f"Enumeration error for hand {hand}: {e}")

    finally:
        # Restore global limits
        MAX_DEPTH = original_max_depth
        MAX_PATHS = original_max_paths

    return {
        "terminal_hashes": terminal_hashes,
        "best_score": best_score,
        "paths_explored": paths_explored,
        "max_depth_reached": max_depth_reached,
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    global MAX_DEPTH, MAX_PATHS
    import argparse

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    parser = argparse.ArgumentParser(description="Exhaustive combo enumeration")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--max-depth", type=int, default=MAX_DEPTH, help="Max actions per path")
    parser.add_argument("--max-paths", type=int, default=MAX_PATHS, help="Max paths to explore")
    parser.add_argument("--output", "-o", type=str, default="enumeration_results.json",
                        help="Output file")
    parser.add_argument("--no-dedupe", action="store_true",
                        help="Disable terminal board state deduplication")
    parser.add_argument("--no-dedupe-intermediate", action="store_true",
                        help="Disable intermediate state pruning")
    parser.add_argument("--prioritize-cards", type=str, default="",
                        help="Comma-separated list of card passcodes to explore first during SELECT_CARD")
    args = parser.parse_args()

    # Parse prioritized cards
    prioritize_cards = []
    if args.prioritize_cards:
        prioritize_cards = [int(x.strip()) for x in args.prioritize_cards.split(",") if x.strip()]
        if prioritize_cards:
            print(f"Card prioritization enabled: {prioritize_cards}")

    # Update limits
    MAX_DEPTH = args.max_depth
    MAX_PATHS = args.max_paths

    # Initialize
    logger.info("Loading card database...")
    if not init_card_database():
        logger.error("Failed to load card database")
        return 1

    print("Loading library...")
    lib = load_library()

    # Set the library reference for callbacks in engine_interface
    set_lib(lib)

    print("Loading locked library...")
    library = load_locked_library()
    main_deck, extra_deck = get_deck_lists(library)

    print(f"Main deck: {len(main_deck)} cards")
    print(f"Extra deck: {len(extra_deck)} cards")

    # Run enumeration
    dedupe_terminals = not args.no_dedupe
    dedupe_intermediate = not args.no_dedupe_intermediate
    engine = EnumerationEngine(
        lib, main_deck, extra_deck,
        verbose=args.verbose,
        dedupe_boards=dedupe_terminals,
        dedupe_intermediate=dedupe_intermediate,
        prioritize_cards=prioritize_cards if prioritize_cards else None
    )
    terminals = engine.enumerate_all()

    # Save results
    output_path = Path(args.output)
    tt_stats = engine.transposition_table.stats()
    results = {
        "meta": {
            "timestamp": datetime.now().isoformat(),
            "max_depth": MAX_DEPTH,
            "max_paths": MAX_PATHS,
            "paths_explored": engine.paths_explored,
            "terminals_found": len(terminals),
            "unique_board_signatures": len(engine.terminal_boards),
            "duplicate_boards_skipped": engine.duplicate_boards_skipped,
            "intermediate_states_pruned": engine.intermediate_states_pruned,
            "transposition_table_size": tt_stats["size"],
            "transposition_hit_rate": tt_stats["hit_rate"],
            "dedupe_terminals_enabled": dedupe_terminals,
            "dedupe_intermediate_enabled": dedupe_intermediate,
            "prioritize_cards": prioritize_cards if prioritize_cards else [],
            "max_depth_seen": engine.max_depth_seen,
        },
        "terminals": [t.to_dict() for t in terminals],
        "board_groups": {k: len(v) for k, v in engine.terminal_boards.items()},
    }

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {output_path}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    by_reason = {}
    by_depth = {}
    for t in terminals:
        by_reason[t.termination_reason] = by_reason.get(t.termination_reason, 0) + 1
        by_depth[t.depth] = by_depth.get(t.depth, 0) + 1

    print("\nBy termination reason:")
    for reason, count in sorted(by_reason.items()):
        print(f"  {reason}: {count}")

    print("\nBy depth:")
    for depth in sorted(by_depth.keys()):
        print(f"  Depth {depth}: {by_depth[depth]}")

    return 0


if __name__ == "__main__":
    exit(main())
