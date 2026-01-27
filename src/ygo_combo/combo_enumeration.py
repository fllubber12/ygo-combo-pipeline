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
from .engine.interface import (
    init_card_database, load_library, preload_utility_scripts,
    py_card_reader, py_card_reader_done, py_script_reader, py_log_handler,
    ffi, get_card_name, set_lib,
)
# All constants come from engine.bindings - the canonical source
from .engine.bindings import (
    # Location constants
    LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA, LOCATION_MZONE,
    LOCATION_GRAVE, LOCATION_SZONE, LOCATION_REMOVED,
    # Position constants
    POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
    # Query flags
    QUERY_CODE, QUERY_POSITION, QUERY_ATTACK, QUERY_DEFENSE, QUERY_END,
    # Selection messages (require player response)
    MSG_SELECT_BATTLECMD, MSG_IDLE, MSG_SELECT_CARD, MSG_SELECT_CHAIN,
    MSG_SELECT_PLACE, MSG_SELECT_POSITION, MSG_SELECT_TRIBUTE,
    MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO, MSG_SELECT_OPTION,
    MSG_SELECT_COUNTER, MSG_SELECT_UNSELECT_CARD, MSG_SELECT_SUM,
    MSG_SORT_CARD, MSG_SELECT_DISFIELD,
    # Core messages
    MSG_RETRY, MSG_HINT, MSG_WAITING, MSG_START, MSG_WIN,
    MSG_UPDATE_DATA, MSG_UPDATE_CARD,
    # Deck/hand operations
    MSG_CONFIRM_DECKTOP, MSG_CONFIRM_CARDS, MSG_SHUFFLE_DECK, MSG_SHUFFLE_HAND,
    MSG_REFRESH_DECK, MSG_SWAP_GRAVE_DECK, MSG_SHUFFLE_SET_CARD, MSG_REVERSE_DECK,
    MSG_DECK_TOP, MSG_SHUFFLE_EXTRA,
    # Turn/phase messages
    MSG_NEW_TURN, MSG_NEW_PHASE, MSG_CONFIRM_EXTRATOP,
    # Card movement
    MSG_MOVE, MSG_POS_CHANGE, MSG_SET, MSG_SWAP, MSG_FIELD_DISABLED,
    # Summoning messages
    MSG_SUMMONING, MSG_SUMMONED, MSG_SPSUMMONING, MSG_SPSUMMONED,
    MSG_FLIPSUMMONING, MSG_FLIPSUMMONED,
    # Chain messages
    MSG_CHAINING, MSG_CHAINED, MSG_CHAIN_SOLVING, MSG_CHAIN_SOLVED,
    MSG_CHAIN_END, MSG_CHAIN_NEGATED, MSG_CHAIN_DISABLED,
    # Selection feedback
    MSG_CARD_SELECTED, MSG_RANDOM_SELECTED, MSG_BECOME_TARGET,
    # LP and damage
    MSG_DRAW, MSG_DAMAGE, MSG_RECOVER, MSG_EQUIP, MSG_LPUPDATE, MSG_UNEQUIP,
    MSG_CARD_TARGET, MSG_CANCEL_TARGET, MSG_PAY_LPCOST,
    MSG_ADD_COUNTER, MSG_REMOVE_COUNTER,
    # Battle
    MSG_ATTACK, MSG_BATTLE, MSG_ATTACK_DISABLED,
    MSG_DAMAGE_STEP_START, MSG_DAMAGE_STEP_END,
    # Effect messages
    MSG_MISSED_EFFECT, MSG_BE_CHAIN_TARGET, MSG_CREATE_RELATION, MSG_RELEASE_RELATION,
    # Random events
    MSG_TOSS_COIN, MSG_TOSS_DICE, MSG_ROCK_PAPER_SCISSORS, MSG_HAND_RES,
    # Announcements
    MSG_ANNOUNCE_RACE, MSG_ANNOUNCE_ATTRIB, MSG_ANNOUNCE_CARD, MSG_ANNOUNCE_NUMBER,
    # Hints and UI
    MSG_CARD_HINT, MSG_TAG_SWAP, MSG_RELOAD_FIELD, MSG_AI_NAME,
    MSG_SHOW_HINT, MSG_PLAYER_HINT, MSG_MATCH_KILL, MSG_CUSTOM_MSG, MSG_REMOVE_CARDS,
)
from .engine.state import (
    BoardSignature, IntermediateState, ActionSpec,
    evaluate_board_quality, BOSS_MONSTERS, INTERACTION_PIECES,
)
from .search.transposition import TranspositionTable, TranspositionEntry
from .cards.validator import CardValidator

# Import parsers and response builders from enumeration submodule
from .enumeration import (
    # Binary readers
    read_u8, read_u16, read_u32, read_i32, read_u64,
    # Message parsers
    parse_idle, parse_select_card, parse_select_chain, parse_select_place,
    parse_select_unselect_card, parse_select_option, parse_select_tribute,
    parse_select_sum, find_valid_tribute_combinations,
    # Response constants
    IDLE_RESPONSE_SUMMON, IDLE_RESPONSE_SPSUMMON, IDLE_RESPONSE_REPOSITION,
    IDLE_RESPONSE_MSET, IDLE_RESPONSE_SSET, IDLE_RESPONSE_ACTIVATE,
    IDLE_RESPONSE_TO_BATTLE, IDLE_RESPONSE_TO_END,
    # Response builders
    build_activate_response, build_pass_response, build_select_card_response,
    build_decline_chain_response, build_select_tribute_response,
)


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
# SUM ENUMERATION HELPERS
# =============================================================================

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
    from itertools import combinations, product

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

    valid_combos = []

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
        exact: If True, sum must equal target. If False, sum must be >= target.
    """
    from itertools import combinations
    
    must_sum = sum(card.get("value", 0) for card in must_select)
    must_count = len(must_select)
    remaining_sum = target_sum - must_sum
    remaining_min = max(0, min_select - must_count)
    remaining_max = max(0, max_select - must_count)
    
    valid_combos = []
    
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


# =============================================================================
# CONFIGURATION - SINGLE SOURCE OF TRUTH
# =============================================================================

# Load from locked library
LOCKED_LIBRARY_PATH = Path(__file__).parents[2] / "config" / "locked_library.json"
CONSTANTS_PATH = Path(__file__).parents[2] / "config" / "constants.json"

# Load constants from config file (anti-hallucination: no hardcoded card IDs)
def _load_constants() -> dict:
    """Load pipeline constants from config/constants.json."""
    if not CONSTANTS_PATH.exists():
        raise FileNotFoundError(
            f"constants.json not found at {CONSTANTS_PATH}. "
            "This file is required - do not use hardcoded card IDs."
        )
    with open(CONSTANTS_PATH) as f:
        return json.load(f)

_CONSTANTS = _load_constants()

# Starting state - loaded from config (verified against cards.cdb)
ENGRAVER = _CONSTANTS["default_hand"]["starter"]  # Fiendsmith Engraver

# Standardized filler/dead card: Holactie cannot be summoned normally and has no
# relevant effects during combo testing. Use this for deck padding and hand filler.
HOLACTIE = _CONSTANTS["default_hand"]["filler"]  # Holactie the Creator of Light

# Limits
MAX_DEPTH = 50          # Maximum actions per path
MAX_PATHS = 100000      # Maximum paths to explore (safety limit)
MAX_ITERATIONS = 1000   # Maximum engine iterations per action

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class Action:
    """A single action in a combo sequence."""
    action_type: str
    message_type: int
    response_value: Any       # The value before packing
    response_bytes: bytes     # Raw bytes sent to engine
    description: str
    card_code: int = None
    card_name: str = None

    def to_dict(self):
        d = asdict(self)
        d['response_bytes'] = self.response_bytes.hex()
        return d


@dataclass
class TerminalState:
    """A terminal state reached by PASS."""
    action_sequence: List[Action]
    board_state: Dict
    depth: int
    state_hash: str
    termination_reason: str   # "PASS", "NO_ACTIONS", "MAX_DEPTH"
    board_hash: Optional[str] = None  # BoardSignature hash for grouping

    def to_dict(self):
        return {
            "action_sequence": [a.to_dict() for a in self.action_sequence],
            "board_state": self.board_state,
            "depth": self.depth,
            "state_hash": self.state_hash,
            "termination_reason": self.termination_reason,
            "board_hash": self.board_hash,
        }


# =============================================================================
# LIBRARY LOADING
# =============================================================================

def load_locked_library():
    """Load the verified locked library."""
    if not LOCKED_LIBRARY_PATH.exists():
        raise FileNotFoundError(f"Locked library not found: {LOCKED_LIBRARY_PATH}")

    with open(LOCKED_LIBRARY_PATH) as f:
        library = json.load(f)

    meta = library.get("_meta", {})
    if not meta.get("verified", False):
        logger.warning("Locked library not yet verified!")
    if library.get("_LOCKED", False):
        logger.info("Using LOCKED library - do not modify without user approval")

    return library


def get_deck_lists(library):
    """Extract main deck and extra deck card lists from library."""
    main_deck = []
    extra_deck = []

    for passcode_str, card in library["cards"].items():
        passcode = int(passcode_str)
        if card["is_extra_deck"]:
            extra_deck.append(passcode)
        else:
            main_deck.append(passcode)

    return main_deck, extra_deck


# =============================================================================
# DUEL CREATION
# =============================================================================

def create_duel(lib, main_deck_cards, extra_deck_cards, starting_hand=None):
    """Create a fresh duel with the starting state.

    Args:
        lib: CFFI library handle
        main_deck_cards: List of main deck passcodes
        extra_deck_cards: List of extra deck passcodes
        starting_hand: Optional list of 5 passcodes for starting hand.
                       If None, uses default [ENGRAVER, HOLACTIE, HOLACTIE, HOLACTIE, HOLACTIE]
    """

    options = ffi.new("OCG_DuelOptions*")

    # Fixed seed for reproducibility
    options.seed[0] = 12345
    options.seed[1] = 67890
    options.seed[2] = 11111
    options.seed[3] = 22222

    options.flags = (5 << 16)  # MR5

    # Player 0 (us)
    options.team1.startingLP = 8000
    options.team1.startingDrawCount = 0  # Hand set manually
    options.team1.drawCountPerTurn = 0   # No draws during combo

    # Player 1 (opponent - does nothing)
    options.team2.startingLP = 8000
    options.team2.startingDrawCount = 5
    options.team2.drawCountPerTurn = 1

    # Callbacks
    options.cardReader = py_card_reader
    options.scriptReader = py_script_reader
    options.logHandler = py_log_handler
    options.cardReaderDone = py_card_reader_done

    duel_ptr = ffi.new("OCG_Duel*")
    result = lib.OCG_CreateDuel(duel_ptr, options)

    if result != 0:
        raise RuntimeError(f"Failed to create duel: {result}")

    duel = duel_ptr[0]
    preload_utility_scripts(lib, duel)

    # === HAND: Use provided hand or default ===
    if starting_hand is not None:
        hand_cards = list(starting_hand)
        # Pad with HOLACTIE if less than 5 cards
        while len(hand_cards) < 5:
            hand_cards.append(HOLACTIE)
        # Truncate if more than 5 cards
        hand_cards = hand_cards[:5]
    else:
        # Default: 1 Engraver + 4 Holactie (original behavior)
        hand_cards = [ENGRAVER, HOLACTIE, HOLACTIE, HOLACTIE, HOLACTIE]
    for i, code in enumerate(hand_cards):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_HAND
        card_info.seq = i
        card_info.pos = POS_FACEUP_ATTACK
        lib.OCG_DuelNewCard(duel, card_info)

    # === MAIN DECK ===
    # Include all main deck cards, pad to 40 with Holactie
    deck = list(main_deck_cards)
    while len(deck) < 40:
        deck.append(HOLACTIE)

    for i, code in enumerate(deck):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_DECK
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        lib.OCG_DuelNewCard(duel, card_info)

    # === EXTRA DECK ===
    for i, code in enumerate(extra_deck_cards):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_EXTRA
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        lib.OCG_DuelNewCard(duel, card_info)

    # === OPPONENT DECK (Holactie filler) ===
    for i in range(40):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 1
        card_info.duelist = 0
        card_info.code = HOLACTIE
        card_info.con = 1
        card_info.loc = LOCATION_DECK
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        lib.OCG_DuelNewCard(duel, card_info)

    return duel


# =============================================================================
# MESSAGE PARSING - Moved to enumeration/parsers.py
# =============================================================================
# Functions: read_u8, read_u16, read_u32, read_i32, read_u64
#            parse_idle, parse_select_card, parse_select_chain, parse_select_place,
#            parse_select_unselect_card, parse_select_option, parse_select_tribute,
#            parse_select_sum, find_valid_tribute_combinations
# Import from: enumeration.parsers


# Legacy definitions removed - now imported from enumeration submodule
# (Keeping parse_query_response here as it uses QUERY_* constants)

# Marker for parser removal start
# (Functions removed - now imported from enumeration submodule)


# =============================================================================
# BOARD STATE CAPTURE
# =============================================================================

def parse_query_response(data: bytes) -> list:
    """Parse OCG_DuelQueryLocation response to extract card codes.

    Format:
    - Total size (u32)
    - Per card: either int16(0) for empty slot, or field blocks ending with QUERY_END
    - Field block: [size(u16)][flag(u32)][value(varies)]
    """
    if len(data) < 4:
        logger.warning(f"parse_query_response: data too short ({len(data)} bytes), expected at least 4")
        return []

    buf = io.BytesIO(data)
    total_size = read_u32(buf)

    cards = []
    while buf.tell() < len(data):
        start_pos = buf.tell()

        # Read first u16 - if 0, empty slot
        if buf.tell() + 2 > len(data):
            break
        first_u16 = struct.unpack("<H", buf.read(2))[0]

        if first_u16 == 0:
            # Empty slot
            cards.append(None)
            continue

        # Non-empty slot: first_u16 is the size of the first field block
        # Parse field blocks
        card_info = {}
        buf.seek(start_pos)  # Rewind to read properly

        while buf.tell() < len(data):
            if buf.tell() + 2 > len(data):
                break
            block_size = struct.unpack("<H", buf.read(2))[0]

            if block_size < 4:
                break

            if buf.tell() + block_size > len(data):
                break

            flag = read_u32(buf)

            if flag == QUERY_END:
                break
            elif flag == QUERY_CODE:
                card_info["code"] = read_u32(buf)
            elif flag == QUERY_POSITION:
                card_info["position"] = read_u32(buf)
            elif flag == QUERY_ATTACK:
                card_info["attack"] = read_i32(buf)
            elif flag == QUERY_DEFENSE:
                card_info["defense"] = read_i32(buf)
            else:
                # Skip unknown field
                remaining = block_size - 4
                if remaining > 0:
                    buf.read(remaining)

        cards.append(card_info if card_info else None)

    return cards


def compute_board_signature(board_state: dict) -> str:
    """Compute a unique signature for a board state.

    Used to detect duplicate board states reached via different paths.
    Only considers player0's board (we're doing solitaire combo evaluation).

    Uses BoardSignature from state_representation for structured representation.
    """
    sig = BoardSignature.from_board_state(board_state)
    return sig.hash()


def compute_idle_state_hash(idle_data: dict, board_state: dict) -> str:
    """Compute a unique hash for an intermediate game state at MSG_IDLE.

    This hash captures:
    - Board state (cards in each zone)
    - Available actions (which encodes OPT usage implicitly)

    Two states with identical hash will have identical future action spaces,
    so we only need to explore one of them.

    Uses IntermediateState from state_representation for structured representation.
    """
    state = IntermediateState.from_idle_data(idle_data, board_state)
    return state.hash()


def capture_board_state(lib, duel) -> dict:
    """Capture complete board state at current duel position."""

    state = {
        "player0": {
            "hand": [],
            "monsters": [],
            "spells": [],
            "graveyard": [],
            "banished": [],
            "extra": [],
        },
        "player1": {
            "hand": [],
            "monsters": [],
            "spells": [],
            "graveyard": [],
            "banished": [],
            "extra": [],
        },
    }

    locations = [
        ("hand", LOCATION_HAND),
        ("monsters", LOCATION_MZONE),
        ("spells", LOCATION_SZONE),
        ("graveyard", LOCATION_GRAVE),
        ("banished", LOCATION_REMOVED),
        ("extra", LOCATION_EXTRA),
    ]

    for player in [0, 1]:
        player_key = f"player{player}"

        for loc_name, loc_value in locations:
            # Query this location
            query_info = ffi.new("OCG_QueryInfo*")
            query_info.flags = QUERY_CODE | QUERY_POSITION | QUERY_ATTACK | QUERY_DEFENSE
            query_info.con = player
            query_info.loc = loc_value
            query_info.seq = 0
            query_info.overlay_seq = 0

            length = ffi.new("uint32_t*")
            buf = lib.OCG_DuelQueryLocation(duel, length, query_info)

            if length[0] > 0:
                data = bytes(ffi.buffer(buf, length[0]))
                cards = parse_query_response(data)

                for card in cards:
                    if card and "code" in card:
                        code = card["code"]
                        name = get_card_name(code)
                        card_entry = {
                            "code": code,
                            "name": name,
                        }
                        if "attack" in card:
                            card_entry["atk"] = card["attack"]
                        if "defense" in card:
                            card_entry["def"] = card["defense"]
                        state[player_key][loc_name].append(card_entry)

    return state


# =============================================================================
# ENUMERATION ENGINE
# =============================================================================

class EnumerationEngine:
    """Exhaustive combo path enumeration with deduplication optimizations."""

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

        # Informational message types that don't require responses
        INFORMATIONAL = {
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

        for iteration in range(MAX_ITERATIONS):
            status = self.lib.OCG_DuelProcess(duel)
            messages = self._get_messages(duel)

            decision_found = False

            for msg_type, msg_data in messages:

                # Skip informational messages
                if msg_type in INFORMATIONAL:
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

    def _handle_idle(self, duel, action_history: List[Action], idle_data: dict):
        """Handle MSG_IDLE - branch on all actions + PASS.

        With intermediate state pruning enabled, we check if this exact game state
        (board + available actions) has been explored before. If so, we skip it
        since all future paths from this state are identical.
        """

        depth = len(action_history)

        # Intermediate state pruning using transposition table
        if self.dedupe_intermediate:
            # Compute intermediate state hash
            state = IntermediateState.from_engine(self.lib, duel, idle_data, capture_board_state)
            state_hash = state.hash()

            # Check transposition table
            cached = self.transposition_table.lookup(state_hash)
            if cached is not None:
                self.intermediate_states_pruned += 1
                self.log(f"PRUNED: duplicate intermediate state at depth {depth}", depth)
                return  # Already explored from this state

            # Store in transposition table (will be updated with results later if needed)
            self.transposition_table.store(state_hash, TranspositionEntry(
                state_hash=state_hash,
                best_terminal_hash="",
                best_terminal_value=0.0,
                creation_depth=depth,
                visit_count=1,
            ))

        self.log(f"IDLE: {len(idle_data.get('activatable', []))} activatable, "
                 f"{len(idle_data.get('spsummon', []))} spsummon", depth)

        # Enumerate all activatable effects
        for i, card in enumerate(idle_data.get("activatable", [])):
            code = card["code"]
            name = get_card_name(code)
            loc = card.get("loc", 0)
            desc = card.get("desc", 0)
            # desc format: (code << 20) | effect_index
            effect_idx = desc & 0xF
            value, response = build_activate_response(i)

            # Location names for clearer descriptions
            loc_name = {2: "hand", 4: "field", 8: "S/T", 16: "GY", 64: "Extra"}.get(loc, f"loc{loc}")

            action = Action(
                action_type="ACTIVATE",
                message_type=MSG_IDLE,
                response_value=value,
                response_bytes=response,
                description=f"Activate {name} ({loc_name} eff{effect_idx})",
                card_code=code,
                card_name=name,
            )

            self.log(f"Branch: Activate {name} ({loc_name} eff{effect_idx}) (idx {i})", depth)
            self._recurse(action_history + [action])

        # Enumerate special summons
        for i, card in enumerate(idle_data.get("spsummon", [])):
            code = card["code"]
            name = get_card_name(code)
            value = (i << 16) | 1  # Special summon response
            response = struct.pack("<I", value)

            action = Action(
                action_type="SPSUMMON",
                message_type=MSG_IDLE,
                response_value=value,
                response_bytes=response,
                description=f"Special Summon {name}",
                card_code=code,
                card_name=name,
            )

            self.log(f"Branch: SpSummon {name} (idx {i})", depth)
            self._recurse(action_history + [action])

        # Enumerate normal summons
        for i, card in enumerate(idle_data.get("summonable", [])):
            code = card["code"]
            name = get_card_name(code)
            value = (i << 16) | 0  # Normal summon response
            response = struct.pack("<I", value)

            action = Action(
                action_type="SUMMON",
                message_type=MSG_IDLE,
                response_value=value,
                response_bytes=response,
                description=f"Normal Summon {name}",
                card_code=code,
                card_name=name,
            )

            self.log(f"Branch: Summon {name} (idx {i})", depth)
            self._recurse(action_history + [action])

        # PASS option (terminal)
        if idle_data.get("to_ep"):
            value, response = build_pass_response()
            action = Action(
                action_type="PASS",
                message_type=MSG_IDLE,
                response_value=value,
                response_bytes=response,
                description="Pass (End Phase)",
            )

            self.log(f"Branch: PASS (terminal)", depth)
            self._record_terminal(action_history + [action], "PASS")

    def _handle_select_card(self, duel, action_history: List[Action], select_data: dict):
        """Handle MSG_SELECT_CARD - branch on unique card codes only.

        Optimization: Selecting Holactie #1 vs Holactie #2 produces identical outcomes,
        so we deduplicate by card code and only branch on the first instance of each.
        This reduces branching significantly (e.g., 5 Holacties -> 1 branch instead of 5).

        Card Prioritization: If prioritize_cards is set, those cards are explored first
        in the order specified. This ensures specific combo paths are explored before
        the search budget is exhausted.

        SELECT_SUM_CANCEL Backtracking: If a SELECT_CARD choice led to SELECT_SUM_CANCEL,
        we exclude that card from subsequent SELECT_CARD prompts in the same path. This
        prevents degenerate loops where DFS repeatedly selects a card whose materials
        can't be satisfied.
        """

        depth = len(action_history)
        cards = select_data["cards"]
        min_sel = select_data["min"]
        max_sel = select_data["max"]

        self.log(f"SELECT_CARD: {len(cards)} cards, select {min_sel}-{max_sel}", depth)

        # Find cards that led to SELECT_SUM_CANCEL in this path
        # Pattern: SELECT_CARD(code X) followed by SELECT_SUM_CANCEL
        failed_codes = set()
        for i in range(len(action_history) - 1):
            action = action_history[i]
            next_action = action_history[i + 1]
            if (action.action_type == "SELECT_CARD" and
                next_action.action_type == "SELECT_SUM_CANCEL" and
                action.card_code is not None):
                failed_codes.add(action.card_code)

        if failed_codes:
            failed_names = [get_card_name(c) for c in failed_codes]
            self.log(f"  Excluding failed SELECT_SUM cards: {failed_names}", depth)

        # For simplicity, enumerate single selections if min==max==1
        if min_sel == 1 and max_sel == 1:
            # Build list of (index, code) pairs, deduplicating by code
            unique_cards = []
            seen_codes = set()
            for i, card in enumerate(cards):
                code = card["code"]
                if code in seen_codes:
                    continue
                # Skip cards that led to SELECT_SUM_CANCEL in this path
                if code in failed_codes:
                    continue
                seen_codes.add(code)
                unique_cards.append((i, code))

            # Sort to put prioritized cards first
            if self.prioritize_cards:
                def priority_key(item):
                    idx, code = item
                    if code in self.prioritize_cards:
                        # Prioritized cards come first, in the order specified
                        try:
                            return (0, self.prioritize_order.index(code))
                        except ValueError:
                            return (0, 999)
                    return (1, idx)  # Non-prioritized cards keep original order
                unique_cards.sort(key=priority_key)

            # Branch on each unique card (now in priority order)
            for i, code in unique_cards:

                name = get_card_name(code)
                indices, response = build_select_card_response([i])

                action = Action(
                    action_type="SELECT_CARD",
                    message_type=MSG_SELECT_CARD,
                    response_value=indices,
                    response_bytes=response,
                    description=f"Select {name}",
                    card_code=code,
                    card_name=name,
                )

                self.log(f"Branch: Select {name} (idx {i}, {len(unique_cards)} unique)", depth)
                self._recurse(action_history + [action])
        else:
            # Multi-select: enumerate combinations of unique card codes
            from itertools import combinations

            # Group cards by code, keeping first index for each
            code_to_indices = {}
            for i, card in enumerate(cards):
                code = card["code"]
                # Skip cards that led to SELECT_SUM_CANCEL in this path
                if code in failed_codes:
                    continue
                if code not in code_to_indices:
                    code_to_indices[code] = []
                code_to_indices[code].append(i)

            unique_codes = list(code_to_indices.keys())

            for r in range(min_sel, max_sel + 1):
                for code_combo in combinations(unique_codes, r):
                    # Use first index for each selected code
                    combo = [code_to_indices[code][0] for code in code_combo]
                    indices, response = build_select_card_response(combo)
                    names = [get_card_name(code) for code in code_combo]

                    action = Action(
                        action_type="SELECT_CARD",
                        message_type=MSG_SELECT_CARD,
                        response_value=combo,
                        response_bytes=response,
                        description=f"Select {', '.join(names)}",
                    )

                    self.log(f"Branch: Select {names}", depth)
                    self._recurse(action_history + [action])

    def _handle_select_place(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_PLACE - select zone for card."""
        depth = len(action_history)

        # msg_data format: player(1) + count(1) + flag(4)
        # Flag bits indicate occupied zones; we need to find a free one
        player = msg_data.get("player", 0)
        flag = msg_data.get("flag", 0)

        self.log(f"SELECT_PLACE: flag=0x{flag:08x}", depth)

        # Find first available zone
        # S/T zone bits: 8-12 (flag & (1 << (8 + i)))
        # Monster zone bits: 0-4 (flag & (1 << i))
        location = 0x08  # S/T zone first
        sequence = 0
        for i in range(5):
            if not (flag & (1 << (8 + i))):
                sequence = i
                break
        else:
            # No S/T zone available, try monster zone
            location = 0x04
            for i in range(5):
                if not (flag & (1 << i)):
                    sequence = i
                    break

        # Response format: player(1) + location(1) + sequence(1) = 3 bytes
        response = struct.pack("<BBB", player, location, sequence)
        action = Action(
            action_type="SELECT_PLACE",
            message_type=MSG_SELECT_PLACE,
            response_value=f"zone_{location:02x}_{sequence}",
            response_bytes=response,
            description=f"Select zone ({location:02x}, {sequence})",
        )
        self._recurse(action_history + [action])

    def _handle_select_position(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_POSITION - always select ATK.

        Analysis showed position choices don't affect final board states
        for this library, so we skip branching to reduce search space.
        """
        response = struct.pack("<I", 0x1)  # ATK position
        action = Action(
            action_type="SELECT_POSITION",
            message_type=MSG_SELECT_POSITION,
            response_value=0x1,
            response_bytes=response,
            description="Position: ATK (auto)",
        )
        self._recurse(action_history + [action])

    def _handle_yes_no(self, duel, action_history, msg_data, msg_type):
        """Handle yes/no prompts - branch on both options."""
        depth = len(action_history)

        for choice, choice_name in [(1, "Yes"), (0, "No")]:
            response = struct.pack("<I", choice)
            action = Action(
                action_type="YES_NO",
                message_type=msg_type,
                response_value=choice,
                response_bytes=response,
                description=f"Choose: {choice_name}",
            )
            self.log(f"Branch: {choice_name}", depth)
            self._recurse(action_history + [action])

    def _handle_select_option(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_OPTION - select from multiple options."""
        depth = len(action_history)
        count = msg_data.get("count", 2) if msg_data else 2  # Fallback to 2 if parsing failed
        options = msg_data.get("options", []) if msg_data else []

        self.log(f"SELECT_OPTION: {count} options available", depth)

        for opt in range(count):
            desc = options[opt]["desc"] if opt < len(options) else 0
            response = struct.pack("<I", opt)
            action = Action(
                action_type="SELECT_OPTION",
                message_type=MSG_SELECT_OPTION,
                response_value=opt,
                response_bytes=response,
                description=f"Option {opt} (desc={desc})",
            )
            self.log(f"Branch: Option {opt}", depth)
            self._recurse(action_history + [action])

    def _handle_select_unselect_card(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_UNSELECT_CARD - select/unselect cards.

        Optimization: Deduplicate by card code to avoid redundant branches
        when selecting identical cards (e.g., multiple Holacties).
        """
        depth = len(action_history)
        finishable = msg_data.get("finishable", 0)
        select_cards = msg_data.get("select_cards", [])
        unselect_cards = msg_data.get("unselect_cards", [])

        self.log(f"SELECT_UNSELECT: {len(select_cards)} select, {len(unselect_cards)} unselect, finishable={finishable}", depth)

        # If finishable and we have unselect options, we can finish
        if finishable and unselect_cards:
            # Response -1 (signed int32) signals finish per ygopro-core
            response = struct.pack("<i", -1)
            action = Action(
                action_type="SELECT_UNSELECT_FINISH",
                message_type=MSG_SELECT_UNSELECT_CARD,
                response_value=-1,
                response_bytes=response,
                description="Finish selection",
            )
            self.log(f"Branch: Finish selection", depth)
            self._recurse(action_history + [action])

        # Enumerate selectable cards - deduplicate by card code
        seen_codes = set()
        for i, card in enumerate(select_cards):
            code = card["code"]
            if code in seen_codes:
                continue  # Skip duplicate card instances
            seen_codes.add(code)

            name = get_card_name(code)
            # Response is just the index (single int32) per ygopro-core field_processor.cpp
            response = struct.pack("<i", i)
            action = Action(
                action_type="SELECT_UNSELECT_SELECT",
                message_type=MSG_SELECT_UNSELECT_CARD,
                response_value=i,
                response_bytes=response,
                description=f"Select {name}",
                card_code=code,
                card_name=name,
            )
            self.log(f"Branch: Select {name} ({len(seen_codes)} unique)", depth)
            self._recurse(action_history + [action])


    def _handle_select_sum(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_SUM - select cards whose levels sum to target.

        Used for Xyz summon material selection, Synchro tuning, and similar mechanics.

        Response format (per ygopro-core playerop.cpp parse_response_cards):
        - int32_t type: -1 to cancel (if allowed), 0 for 32-bit indices
        - uint32_t count: number of selected cards (if type != -1)
        - uint32_t indices[count]: 0-indexed positions in the selectable cards

        This handler enumerates ALL valid sum combinations to explore all possible
        Xyz/Synchro lines, not just the first valid selection.
        """
        depth = len(action_history)
        
        # Extract parsed data
        must_select = msg_data.get("must_select", [])
        can_select = msg_data.get("can_select", [])
        target_sum = msg_data.get("target_sum", 0)
        must_count = msg_data.get("must_count", 0)
        can_count = msg_data.get("can_count", 0)
        
        select_mode = msg_data.get("select_mode", 0)
        min_cards = msg_data.get("min", 1)
        max_cards = msg_data.get("max", len(can_select) if can_select else 2)
        mode_str = "exact" if select_mode == 0 else "at_least"
        self.log(f"SELECT_SUM: target={target_sum} ({mode_str}), select {min_cards}-{max_cards} cards", depth)

        # DEBUG: Always show raw hex for analysis
        if self.verbose and "_raw_hex" in msg_data:
            raw_hex = msg_data['_raw_hex']
            raw_len = msg_data.get('_raw_len', len(raw_hex)//2)
            self.log(f"  RAW ({raw_len} bytes): {raw_hex[:80]}{'...' if len(raw_hex) > 80 else ''}", depth)
            # Show first card's bytes (offset 15, 18 bytes per card)
            # Format: code(4) + controller(1) + location(1) + sequence(4) + position(4) + sum_param(4)
            if raw_len >= 33:  # 15 header + 18 card bytes
                self.log(f"  Card0 bytes (offset 15): {raw_hex[30:66]}", depth)

        # Check for parse errors
        if "_parse_error" in msg_data:
            self.log(f"  PARSE ERROR: {msg_data['_parse_error']}", depth)

        # Debug: show available cards with their levels
        if self.verbose:
            for i, card in enumerate(must_select):
                name = get_card_name(card.get("code", 0))
                self.log(f"  must[{i}]: {name} level={card.get('level', 0)} (sum_param=0x{card.get('sum_param', 0):08x})", depth)
            for i, card in enumerate(can_select):
                name = get_card_name(card.get("code", 0))
                self.log(f"  can[{i}]: {name} level={card.get('level', 0)} (sum_param=0x{card.get('sum_param', 0):08x})", depth)

        # Branch 1: Cancel the selection (valid for optional effects)
        # Many Fiendsmith effects are optional, so canceling is a valid path
        cancel_response = struct.pack("<i", -1)
        cancel_action = Action(
            action_type="SELECT_SUM_CANCEL",
            message_type=MSG_SELECT_SUM,
            response_value=-1,
            response_bytes=cancel_response,
            description="Cancel sum selection",
        )
        self.log(f"Branch: Cancel sum selection", depth)
        self._recurse(action_history + [cancel_action])

        # Branch 2+: Find and explore all valid sum combinations
        # For Xyz: need cards whose levels sum to target (e.g., 2x Level 6 = 12)

        # Handle case where target_sum seems to be number of cards, not level sum
        # The ygopro-core format varies - target may be:
        # 1. Actual level sum (e.g., 12 for 2x Level 6)
        # 2. Number of cards to select (e.g., 2 for 2 materials)
        # 3. Something else encoded
        actual_target = target_sum
        if can_select and target_sum > 0:
            first_card_value = can_select[0].get("value", 0)

            # If target matches number of cards and cards have consistent values,
            # treat target as card count and compute sum
            if target_sum <= len(can_select) and first_card_value > 0:
                expected_sum = first_card_value * target_sum
                # Use the computed sum if it makes sense
                actual_target = expected_sum
                self.log(f"  Adjusted target: {target_sum} -> {actual_target} (card_value={first_card_value})", depth)

        valid_combos = find_valid_sum_combinations(
            must_select=must_select,
            can_select=can_select,
            target_sum=actual_target,
            min_select=min_cards,
            max_select=max_cards,
            mode=select_mode,
        )
        
        self.log(f"  Found {len(valid_combos)} valid sum combinations", depth)
        
        # Deduplicate combinations by card codes to avoid redundant branches
        # (selecting Token A + Requiem vs Token B + Requiem with same codes)
        seen_code_combos = set()
        
        for combo_indices in valid_combos:
            # Get card codes for this combination
            combo_codes = tuple(sorted(can_select[i].get("code", 0) for i in combo_indices))
            
            if combo_codes in seen_code_combos:
                continue  # Skip duplicate code combination
            seen_code_combos.add(combo_codes)
            
            # Build response for MSG_SELECT_SUM
            # Try format: must_count (always 0) + select_count + indices
            # Or just count + indices as u32s
            full_indices = list(combo_indices)

            # Format: int32(-1) to cancel, or int32(0) + count + indices
            # Try simpler: just u32 indices
            response = struct.pack("<I", len(full_indices))
            for idx in full_indices:
                response += struct.pack("<I", idx)
            
            # Build description
            card_names = [get_card_name(can_select[i].get("code", 0)) for i in combo_indices]
            total_sum = sum(can_select[i].get("value", 0) for i in combo_indices)
            desc = f"Sum select: {', '.join(card_names)} (sum={total_sum})"
            
            action = Action(
                action_type="SELECT_SUM",
                message_type=MSG_SELECT_SUM,
                response_value=full_indices,
                response_bytes=response,
                description=desc,
            )
            
            self.log(f"Branch: {desc}", depth)
            self._recurse(action_history + [action])
        
        # If no valid combinations found and cancel didn't work, try index 0 as fallback
        if not valid_combos and can_select:
            self.log(f"  No valid combos, trying fallback (index 0)", depth)
            fallback_response = struct.pack("<iII", 0, 1, 0)
            fallback_action = Action(
                action_type="SELECT_SUM_FALLBACK",
                message_type=MSG_SELECT_SUM,
                response_value=[0],
                response_bytes=fallback_response,
                description="Sum select fallback: card 0",
            )
            self._recurse(action_history + [fallback_action])


    def _handle_select_tribute(self, duel, action_history, msg_data):
        """Handle MSG_SELECT_TRIBUTE - enumerate all valid tribute combinations."""
        depth = len(action_history)

        cards = msg_data.get('cards', [])
        min_req = msg_data.get('min', 1)
        max_req = msg_data.get('max', 2)
        cancelable = msg_data.get('cancelable', False)

        self.log(f"SELECT_TRIBUTE: {len(cards)} cards, need {min_req}-{max_req} tributes", depth)

        # Debug: show available cards
        if self.verbose:
            for card in cards:
                name = get_card_name(card.get("code", 0))
                self.log(f"  [{card['index']}]: {name} (release_param={card.get('release_param', 1)})", depth)

        responses = []

        # Find all valid tribute combinations
        valid_combos = find_valid_tribute_combinations(cards, min_req, max_req)

        # Deduplicate by card codes to avoid redundant branches
        seen_code_combos = set()

        for combo in valid_combos:
            combo_codes = tuple(sorted(cards[i].get("code", 0) for i in combo))

            if combo_codes in seen_code_combos:
                continue
            seen_code_combos.add(combo_codes)

            response = build_select_tribute_response(combo)
            card_names = [get_card_name(cards[i].get("code", 0)) for i in combo]
            desc = f"Tribute {len(combo)} card(s): {', '.join(card_names)}"

            action = Action(
                action_type="SELECT_TRIBUTE",
                message_type=MSG_SELECT_TRIBUTE,
                response_value=combo,
                response_bytes=response,
                description=desc,
            )

            self.log(f"Branch: {desc}", depth)
            self._recurse(action_history + [action])

        # If cancelable, add cancel option
        if cancelable:
            cancel_response = struct.pack('<B', 0)
            cancel_action = Action(
                action_type="SELECT_TRIBUTE_CANCEL",
                message_type=MSG_SELECT_TRIBUTE,
                response_value=0,
                response_bytes=cancel_response,
                description="Cancel tribute",
            )
            self.log(f"Branch: Cancel tribute", depth)
            self._recurse(action_history + [cancel_action])

        # Fallback if no valid combos found
        if not valid_combos and not cancelable and cards:
            fallback_indices = list(range(min(min_req, len(cards))))
            fallback_response = build_select_tribute_response(fallback_indices)
            fallback_action = Action(
                action_type="SELECT_TRIBUTE_FALLBACK",
                message_type=MSG_SELECT_TRIBUTE,
                response_value=fallback_indices,
                response_bytes=fallback_response,
                description=f"Fallback: tribute first {len(fallback_indices)} cards",
            )
            self.log(f"Branch: Fallback tribute", depth)
            self._recurse(action_history + [fallback_action])

    def _handle_legacy_message_12(self, duel, action_history, msg_data):
        """Handle legacy message type 12.

        In some ygopro-core versions, message 12 is used for effect activation prompts.
        We treat it similar to yes/no but with simpler parsing.
        """
        depth = len(action_history)
        self.log(f"Legacy MSG 12 at depth {depth}", depth)

        # Try both yes (1) and no (0) options like yes/no handler
        for choice in [1, 0]:
            response = struct.pack("<I", choice)
            choice_name = "Yes" if choice else "No"
            action = Action(
                action_type="LEGACY_12",
                message_type=12,
                response_value=choice,
                response_bytes=response,
                description=f"Legacy choice: {choice_name}",
            )
            self.log(f"Branch: {choice_name}", depth)
            self._recurse(action_history + [action])

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
    deck: List[int],
    max_depth: int = 25,
    max_paths: int = 0,
) -> Dict[str, Any]:
    """Enumerate all combos from a specific starting hand.

    This is the worker-compatible entry point for parallel enumeration.
    Creates a fresh engine context, sets up the hand, and runs DFS.

    Args:
        hand: Tuple of card passcodes for starting hand.
        deck: Full deck list (for extra deck setup).
        max_depth: Maximum search depth.
        max_paths: Maximum paths to explore (0 = unlimited).

    Returns:
        Dict with:
            - terminal_hashes: List of unique terminal board hashes
            - best_score: Highest board evaluation score
            - paths_explored: Number of paths explored
            - max_depth_reached: Deepest point in search tree
    """
    terminal_hashes: List[str] = []
    best_score = 0.0
    paths_explored = 0
    max_depth_reached = 0

    # Create transposition table for this hand
    tt = TranspositionTable(max_size=100_000)

    try:
        # Placeholder: actual enumeration logic goes here
        # For now, return empty results
        #
        # TODO: Implement full enumeration with specific hand setup:
        # 1. Create duel with exact hand cards (not random draw)
        # 2. Run DFS enumeration from that state
        # 3. Collect terminal board hashes and scores
        # 4. Return serializable results
        pass

    except Exception as e:
        logger.warning(f"Enumeration error for hand {hand}: {e}")

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
