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
from engine_interface import (
    init_card_database, load_library, preload_utility_scripts,
    py_card_reader, py_card_reader_done, py_script_reader, py_log_handler,
    ffi, get_card_name, set_lib,
)
# All constants come from ocg_bindings - the canonical source
from ocg_bindings import (
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
from state_representation import (
    BoardSignature, IntermediateState, ActionSpec,
    evaluate_board_quality, BOSS_MONSTERS, INTERACTION_PIECES,
)
from transposition_table import TranspositionTable, TranspositionEntry


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
) -> List[List[int]]:
    """Find all valid combinations of cards that sum to target value.
    
    Used for Xyz summon material selection, Synchro tuning, ritual tributes, etc.
    
    Args:
        must_select: Cards that MUST be included (from must_select in message)
        can_select: Cards that CAN be selected (from can_select in message)
        target_sum: Target sum value (e.g., 6 for Rank 6 Xyz, 12 for 2x Level 6)
        min_select: Minimum total cards to select
        max_select: Maximum total cards to select
        
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
    from itertools import combinations
    
    # Calculate sum from must_select cards (these are always included)
    must_sum = sum(card.get("value", 0) for card in must_select)
    must_count = len(must_select)
    
    # Remaining sum needed from can_select cards
    remaining_sum = target_sum - must_sum
    
    # Adjust selection bounds for can_select
    remaining_min = max(0, min_select - must_count)
    remaining_max = max(0, max_select - must_count)
    
    valid_combos = []
    
    # Edge case: if must_select already meets target
    if remaining_sum == 0 and remaining_min == 0:
        valid_combos.append([])  # Empty selection from can_select is valid
    
    # Try all combination sizes from remaining_min to remaining_max
    for size in range(remaining_min, min(remaining_max + 1, len(can_select) + 1)):
        if size == 0:
            continue  # Already handled above
            
        for combo_indices in combinations(range(len(can_select)), size):
            combo_sum = sum(can_select[i].get("value", 0) for i in combo_indices)
            
            # Check if this combination achieves the target sum
            # Note: Some mechanics allow "at least" target sum, but Xyz is exact
            if combo_sum == remaining_sum:
                valid_combos.append(list(combo_indices))
    
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

# Starting state
ENGRAVER = 60764609

# Standardized filler/dead card: Holactie cannot be summoned normally and has no
# relevant effects during combo testing. Use this for deck padding and hand filler.
HOLACTIE = 10000040  # Holactie the Creator of Light

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

    if library.get("_meta", {}).get("verification_required", True):
        logger.warning("Locked library not yet verified!")

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
# MESSAGE PARSING
# =============================================================================

def read_u8(buf: BinaryIO) -> int: return struct.unpack("<B", buf.read(1))[0]
def read_u16(buf: BinaryIO) -> int: return struct.unpack("<H", buf.read(2))[0]
def read_u32(buf: BinaryIO) -> int: return struct.unpack("<I", buf.read(4))[0]
def read_i32(buf: BinaryIO) -> int: return struct.unpack("<i", buf.read(4))[0]
def read_u64(buf: BinaryIO) -> int: return struct.unpack("<Q", buf.read(8))[0]


def parse_idle(data: Union[bytes, BinaryIO]) -> Dict[str, Any]:
    """Parse MSG_IDLE to extract all legal actions."""
    buf = io.BytesIO(data) if isinstance(data, bytes) else data

    player = read_u8(buf)

    def read_cardlist(extra=False, seq_u8=False):
        """Read a card list from IDLE message.

        Args:
            extra: If True, reads desc (u64) and mode (u8) for activatable cards
            seq_u8: If True, reads sequence as u8 (for repos), else u32
        """
        cards = []
        count = read_u32(buf)
        for _ in range(count):
            code = read_u32(buf)
            con = read_u8(buf)
            loc = read_u8(buf)
            seq = read_u8(buf) if seq_u8 else read_u32(buf)
            if extra:
                desc = read_u64(buf)
                mode = read_u8(buf)
                cards.append({"code": code, "con": con, "loc": loc, "seq": seq, "desc": desc, "mode": mode})
            else:
                cards.append({"code": code, "con": con, "loc": loc, "seq": seq})
        return cards

    return {
        "player": player,
        "summonable": read_cardlist(),
        "spsummon": read_cardlist(),
        "repos": read_cardlist(seq_u8=True),
        "mset": read_cardlist(),
        "sset": read_cardlist(),
        "activatable": read_cardlist(extra=True),
        "to_bp": read_u8(buf),
        "to_ep": read_u8(buf),
        "can_shuffle": read_u8(buf),
    }


def parse_select_card(data: Union[bytes, BinaryIO]) -> Dict[str, Any]:
    """Parse MSG_SELECT_CARD to extract selection options."""
    buf = io.BytesIO(data) if isinstance(data, bytes) else data

    player = read_u8(buf)
    cancelable = read_u8(buf)
    min_select = read_u32(buf)
    max_select = read_u32(buf)
    count = read_u32(buf)

    cards = []
    for _ in range(count):
        code = read_u32(buf)
        con = read_u8(buf)
        loc = read_u8(buf)
        seq = read_u32(buf)
        pos = read_u32(buf)
        cards.append({"code": code, "con": con, "loc": loc, "seq": seq})

    return {
        "player": player,
        "cancelable": cancelable,
        "min": min_select,
        "max": max_select,
        "cards": cards,
    }


def parse_select_chain(data: Union[bytes, BinaryIO]) -> Dict[str, Any]:
    """Parse MSG_SELECT_CHAIN."""
    buf = io.BytesIO(data) if isinstance(data, bytes) else data

    player = read_u8(buf)
    count = read_u8(buf)
    specount = read_u8(buf)
    forced = read_u8(buf)

    return {
        "player": player,
        "count": count,
        "forced": forced,
    }


def parse_select_place(data: Union[bytes, BinaryIO]) -> Dict[str, Any]:
    """Parse MSG_SELECT_PLACE."""
    buf = io.BytesIO(data) if isinstance(data, bytes) else data

    player = read_u8(buf)
    count = read_u8(buf)
    flag = read_u32(buf)

    return {
        "player": player,
        "count": count,
        "flag": flag,
    }


def parse_select_unselect_card(data: Union[bytes, BinaryIO]) -> Dict[str, Any]:
    """Parse MSG_SELECT_UNSELECT_CARD."""
    buf = io.BytesIO(data) if isinstance(data, bytes) else data

    player = read_u8(buf)
    finishable = read_u8(buf)
    cancelable = read_u8(buf)
    min_cards = read_u32(buf)
    max_cards = read_u32(buf)
    select_count = read_u32(buf)

    select_cards = []
    for _ in range(select_count):
        code = read_u32(buf)
        con = read_u8(buf)
        loc = read_u8(buf)
        seq = read_u32(buf)
        pos = read_u32(buf)
        select_cards.append({"code": code, "con": con, "loc": loc, "seq": seq, "pos": pos})

    unselect_count = read_u32(buf)
    unselect_cards = []
    for _ in range(unselect_count):
        code = read_u32(buf)
        con = read_u8(buf)
        loc = read_u8(buf)
        seq = read_u32(buf)
        pos = read_u32(buf)
        unselect_cards.append({"code": code, "con": con, "loc": loc, "seq": seq, "pos": pos})

    return {
        "player": player,
        "finishable": finishable,
        "cancelable": cancelable,
        "min": min_cards,
        "max": max_cards,
        "select_cards": select_cards,
        "unselect_cards": unselect_cards,
    }


def parse_select_option(data: Union[bytes, BinaryIO]) -> Dict[str, Any]:
    """Parse MSG_SELECT_OPTION to extract available options.

    Format:
    - player (1 byte)
    - count (1 byte)
    - options[] (count * 8 bytes each - u64 desc for each option)
    """
    buf = io.BytesIO(data) if isinstance(data, bytes) else data

    player = read_u8(buf)
    count = read_u8(buf)

    options = []
    for i in range(count):
        desc = read_u64(buf)
        options.append({"index": i, "desc": desc})

    return {
        "player": player,
        "count": count,
        "options": options,
    }


def parse_select_tribute(data: Union[bytes, BinaryIO]) -> Dict[str, Any]:
    """Parse MSG_SELECT_TRIBUTE message.

    Format:
    - player: 1 byte
    - cancelable: 1 byte
    - min: 1 byte
    - max: 1 byte
    - count: 1 byte
    - cards[count]: each card is 11 bytes
        - code: 4 bytes
        - controller: 1 byte
        - location: 1 byte
        - sequence: 1 byte
        - release_param: 4 bytes (tribute value, usually 1)
    """
    buf = io.BytesIO(data) if isinstance(data, bytes) else data

    player = read_u8(buf)
    cancelable = read_u8(buf)
    min_tributes = read_u8(buf)
    max_tributes = read_u8(buf)
    count = read_u8(buf)

    cards = []
    for i in range(count):
        code = read_u32(buf)
        controller = read_u8(buf)
        location = read_u8(buf)
        sequence = read_u8(buf)
        release_param = read_u32(buf)
        cards.append({
            'index': i,
            'code': code,
            'controller': controller,
            'location': location,
            'sequence': sequence,
            'release_param': release_param,
        })

    return {
        'player': player,
        'cancelable': bool(cancelable),
        'min': min_tributes,
        'max': max_tributes,
        'count': count,
        'cards': cards,
    }


def find_valid_tribute_combinations(cards: list, min_req: int, max_req: int) -> list:
    """Find all valid combinations of cards to tribute.

    Most tribute summons need count (1 for Level 5-6, 2 for Level 7+).
    Some cards have release_param > 1 (count as 2 tributes).

    Returns list of card index lists.
    """
    from itertools import combinations

    valid_combos = []

    # Try all combination sizes from 1 to total cards
    for size in range(1, len(cards) + 1):
        for combo in combinations(range(len(cards)), size):
            # Calculate total tribute value
            total_value = sum(
                max(1, cards[i].get('release_param', 1) & 0xFF)
                for i in combo
            )

            if min_req <= total_value <= max_req:
                valid_combos.append(list(combo))

    return valid_combos


def build_select_tribute_response(selected_indices: list) -> bytes:
    """Build response for MSG_SELECT_TRIBUTE.

    Format: 1-byte count + 1-byte indices
    """
    count = len(selected_indices)
    return struct.pack('<B' + 'B' * count, count, *selected_indices)


def parse_select_sum(data: Union[bytes, BinaryIO]) -> Dict[str, Any]:
    """Parse MSG_SELECT_SUM to extract sum selection options.

    Note: The message format varies by ygopro-core version. This parser
    reads the raw bytes and extracts what we can, falling back to safe defaults.

    The target sum and card values are used to find valid combinations.
    """
    buf = io.BytesIO(data) if isinstance(data, bytes) else data
    raw_data = data if isinstance(data, bytes) else buf.read()
    buf.seek(0)

    # Try to extract basic info from the message
    # Format seems to be: player(1) + mode(1) + min(1) + max(1) + ...
    try:
        player = read_u8(buf)
        mode = read_u8(buf)
        min_sel = read_u8(buf)
        max_sel = read_u8(buf)

        # The rest of the format is unclear, so we'll scan for card codes
        # Card codes are typically 8-digit numbers that we can recognize
        remaining = raw_data[4:]

        # For now, use a simplified approach:
        # The target_sum is likely in bytes 4-7 (as u32)
        target_sum = struct.unpack_from('<I', raw_data, 4)[0] if len(raw_data) >= 8 else 0

        # Extract readable values - target_sum of 16777216 suggests byte order issue
        # Try interpreting as bytes 4-7 in different ways
        if target_sum > 65535:  # Seems too large for a level sum
            # Maybe it's really bytes 4-5 as u16?
            target_sum = struct.unpack_from('<H', raw_data, 4)[0] if len(raw_data) >= 6 else 1

        # Can't reliably parse cards, so return minimal info
        # The handler will use cancel or fallback
        return {
            "player": player,
            "select_mode": mode,
            "min": min_sel,
            "max": max_sel,
            "must_count": 0,
            "can_count": 0,
            "target_sum": target_sum if target_sum <= 255 else 12,  # Reasonable default
            "must_select": [],
            "can_select": [],
            "_parse_error": "simplified_parse",
        }

    except Exception as e:
        # Fallback to minimal info
        return {
            "player": 0,
            "select_mode": 0,
            "min": 1,
            "max": 2,
            "must_count": 0,
            "can_count": 0,
            "target_sum": 12,  # Reasonable default for Xyz
            "must_select": [],
            "can_select": [],
            "_parse_error": str(e),
        }


# =============================================================================
# RESPONSE BUILDERS
# =============================================================================

# IDLE response types (from field_processor.cpp OCG_DuelSetResponse for MSG_SELECT_IDLECMD)
# =============================================================================
# RESPONSE FORMAT DOCUMENTATION
# =============================================================================
# Response formats are based on ygopro-core ocgapi.cpp and playerop.cpp.
# Reference: https://github.com/edo9300/ygopro-core
#
# MSG_IDLE (MSG_SELECT_IDLECMD = 11):
#   Response: u32 with format: (index << 16) | action_type
#   Where action_type is one of IDLE_RESPONSE_* constants below.
#   For ACTIVATE: index is position in activatable[] list (0-indexed).
#   For SPSUMMON: index is position in spsummon[] list.
#   For TO_END: no index needed, just the action type.
#
# MSG_SELECT_CARD (15):
#   Response: i32(cancelable?) + u32(count) + count*u32(indices)
#   First i32: 0 = not canceling, -1 = cancel (if cancelable)
#   Second u32: number of selected cards
#   Remaining u32s: 0-indexed positions in the selectable[] list
#
# MSG_SELECT_CHAIN (16):
#   Response: i32 - chain index (0-indexed from chainable list) or -1 to decline
#
# MSG_SELECT_PLACE (18):
#   Response: u8(player) + u8(location) + u8(sequence)
#   player: 0 or 1
#   location: LOCATION_* constant (MZONE=0x04, SZONE=0x08)
#   sequence: zone index (0-4 for main zones, 5-6 for EMZ)
#
# MSG_SELECT_POSITION (19):
#   Response: u32 with position flags (POS_FACEUP_ATTACK=0x1, etc)
#
# MSG_SELECT_EFFECTYN (21):
#   Response: u32 - 1 for yes, 0 for no
#
# MSG_SELECT_YESNO (22):
#   Response: u32 - 1 for yes, 0 for no
#
# MSG_SELECT_OPTION (23):
#   Response: u32 - 0-indexed option number
#
# MSG_SELECT_UNSELECT_CARD (25):
#   Response: i32 - selected card index (0-indexed) or -1 to finish
#
# =============================================================================

IDLE_RESPONSE_SUMMON = 0       # Normal summon
IDLE_RESPONSE_SPSUMMON = 1     # Special summon
IDLE_RESPONSE_REPOSITION = 2   # Change position
IDLE_RESPONSE_MSET = 3         # Monster set
IDLE_RESPONSE_SSET = 4         # Spell/trap set
IDLE_RESPONSE_ACTIVATE = 5     # Activate effect
IDLE_RESPONSE_TO_BATTLE = 6    # Go to battle phase
IDLE_RESPONSE_TO_END = 7       # End turn / pass


def build_activate_response(index: int) -> Tuple[int, bytes]:
    """Build response to activate effect from IDLE.

    Args:
        index: 0-indexed position in activatable[] list.

    Returns:
        (value, bytes) - the response value and packed bytes.
    """
    value = (index << 16) | IDLE_RESPONSE_ACTIVATE
    return value, struct.pack("<I", value)


def build_pass_response() -> Tuple[int, bytes]:
    """Build response to end main phase (PASS).

    Returns:
        (IDLE_RESPONSE_TO_END, packed bytes).
    """
    return IDLE_RESPONSE_TO_END, struct.pack("<I", IDLE_RESPONSE_TO_END)


def build_select_card_response(indices: List[int]) -> Tuple[List[int], bytes]:
    """Build response to select cards (MSG_SELECT_CARD).

    Args:
        indices: List of 0-indexed card positions from selectable[] list.

    Returns:
        (indices, packed bytes) - the selected indices and response bytes.
    """
    data = struct.pack("<iI", 0, len(indices))  # 0 = not canceling, count
    for idx in indices:
        data += struct.pack("<I", idx)
    return indices, data


def build_decline_chain_response() -> Tuple[int, bytes]:
    """Build response to decline chain opportunity (MSG_SELECT_CHAIN).

    Returns:
        (-1, packed bytes) - decline response.
    """
    return -1, struct.pack("<i", -1)


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

    def __init__(self, lib, main_deck, extra_deck, verbose=False, dedupe_boards=True, dedupe_intermediate=True):
        self.lib = lib
        self.main_deck = main_deck
        self.extra_deck = extra_deck
        self.verbose = verbose
        self.dedupe_boards = dedupe_boards  # Skip duplicate terminal board states
        self.dedupe_intermediate = dedupe_intermediate  # Skip duplicate intermediate states

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
        """

        depth = len(action_history)
        cards = select_data["cards"]
        min_sel = select_data["min"]
        max_sel = select_data["max"]

        self.log(f"SELECT_CARD: {len(cards)} cards, select {min_sel}-{max_sel}", depth)

        # For simplicity, enumerate single selections if min==max==1
        if min_sel == 1 and max_sel == 1:
            # Deduplicate by card code - only branch on first instance of each unique card
            seen_codes = set()
            for i, card in enumerate(cards):
                code = card["code"]
                if code in seen_codes:
                    continue  # Skip duplicate card instances
                seen_codes.add(code)

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

                self.log(f"Branch: Select {name} (idx {i}, {len(seen_codes)} unique)", depth)
                self._recurse(action_history + [action])
        else:
            # Multi-select: enumerate combinations of unique card codes
            from itertools import combinations

            # Group cards by code, keeping first index for each
            code_to_indices = {}
            for i, card in enumerate(cards):
                code = card["code"]
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
        
        self.log(f"SELECT_SUM: target={target_sum}, must={must_count}, can={can_count}", depth)

        # Debug: show raw bytes if available
        if self.verbose and "_raw" in msg_data:
            self.log(f"  RAW: {msg_data['_raw']}", depth)

        # Debug: show available cards
        if self.verbose:
            for i, card in enumerate(must_select):
                name = get_card_name(card.get("code", 0))
                self.log(f"  must[{i}]: {name} (value={card.get('value', 0)})", depth)
            for i, card in enumerate(can_select):
                name = get_card_name(card.get("code", 0))
                self.log(f"  can[{i}]: {name} (value={card.get('value', 0)})", depth)

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
        valid_combos = find_valid_sum_combinations(
            must_select=must_select,
            can_select=can_select,
            target_sum=target_sum,
            min_select=1,  # At least 1 card
            max_select=len(can_select),  # At most all available
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
            
            # Build response: type(0) + count + indices
            # Note: indices are relative to can_select list, but response expects
            # indices into the FULL selectable list (must + can concatenated)
            # Since must cards are auto-included, we just send can_select indices
            full_indices = list(combo_indices)  # Indices into can_select
            
            response = struct.pack("<iI", 0, len(full_indices))
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
    args = parser.parse_args()

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
        dedupe_intermediate=dedupe_intermediate
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
