"""
Board state capture utilities.

Functions for querying and capturing the current duel board state,
computing board signatures for deduplication, and parsing query responses.
"""

import io
import logging
import struct
from typing import Dict, List, Optional, Any, Union

# Support both relative imports (package) and absolute imports (sys.path)
try:
    from .bindings import (
        ffi,
        LOCATION_HAND, LOCATION_MZONE, LOCATION_SZONE,
        LOCATION_GRAVE, LOCATION_REMOVED, LOCATION_EXTRA,
        QUERY_CODE, QUERY_POSITION, QUERY_ATTACK, QUERY_DEFENSE, QUERY_END,
    )
    from .interface import get_card_name
    from .state import BoardSignature, IntermediateState
    from .board_types import BoardState
    from ..enumeration.parsers import read_u32, read_i32
except ImportError:
    from engine.bindings import (
        ffi,
        LOCATION_HAND, LOCATION_MZONE, LOCATION_SZONE,
        LOCATION_GRAVE, LOCATION_REMOVED, LOCATION_EXTRA,
        QUERY_CODE, QUERY_POSITION, QUERY_ATTACK, QUERY_DEFENSE, QUERY_END,
    )
    from engine.interface import get_card_name
    from engine.state import BoardSignature, IntermediateState
    from engine.board_types import BoardState
    from enumeration.parsers import read_u32, read_i32

logger = logging.getLogger(__name__)


def parse_query_response(data: bytes) -> List[Optional[Dict[str, Any]]]:
    """Parse OCG_DuelQueryLocation response to extract card codes.

    Format:
    - Total size (u32)
    - Per card: either int16(0) for empty slot, or field blocks ending with QUERY_END
    - Field block: [size(u16)][flag(u32)][value(varies)]

    Args:
        data: Raw bytes from OCG_DuelQueryLocation

    Returns:
        List of card info dicts (or None for empty slots)
    """
    if len(data) < 4:
        logger.warning(f"parse_query_response: data too short ({len(data)} bytes), expected at least 4")
        return []

    buf = io.BytesIO(data)
    total_size = read_u32(buf)

    cards: List[Optional[Dict[str, Any]]] = []
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
        card_info: Dict[str, Any] = {}
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


def compute_board_signature(board_state: Union[Dict[str, Any], BoardState]) -> str:
    """Compute a unique signature for a board state.

    Used to detect duplicate board states reached via different paths.
    Only considers player0's board (we're doing solitaire combo evaluation).

    Uses BoardSignature from state_representation for structured representation.

    Args:
        board_state: Dict or BoardState with player0/player1 zones

    Returns:
        MD5 hash string of the board state
    """
    # Convert BoardState to dict if needed (BoardSignature expects dict)
    if isinstance(board_state, BoardState):
        board_state = board_state.to_dict()
    sig = BoardSignature.from_board_state(board_state)
    return sig.hash()


def compute_idle_state_hash(idle_data: Dict[str, Any], board_state: Union[Dict[str, Any], BoardState]) -> str:
    """Compute a unique hash for an intermediate game state at MSG_IDLE.

    This hash captures:
    - Board state (cards in each zone)
    - Available actions (which encodes OPT usage implicitly)

    Two states with identical hash will have identical future action spaces,
    so we only need to explore one of them.

    Uses IntermediateState from state_representation for structured representation.

    Args:
        idle_data: Parsed MSG_IDLE data with available actions
        board_state: Current board state (Dict or BoardState)

    Returns:
        MD5 hash string of the intermediate state
    """
    # Convert BoardState to dict if needed (IntermediateState expects dict)
    if isinstance(board_state, BoardState):
        board_state = board_state.to_dict()
    state = IntermediateState.from_idle_data(idle_data, board_state)
    return state.hash()


def capture_board_state(lib, duel) -> BoardState:
    """Capture complete board state at current duel position.

    Queries all relevant zones for both players and extracts card information.
    Returns a validated BoardState object that prevents invalid field access.

    Args:
        lib: CFFI library handle
        duel: Duel handle from OCG_CreateDuel

    Returns:
        Validated BoardState with player0/player1 zones
    """
    state: Dict[str, Any] = {
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
                        card_entry: Dict[str, Any] = {
                            "code": code,
                            "name": name,
                        }
                        if "attack" in card:
                            card_entry["atk"] = card["attack"]
                        if "defense" in card:
                            card_entry["def"] = card["defense"]
                        state[player_key][loc_name].append(card_entry)

    # Validate and return as BoardState (this is the anti-hallucination boundary)
    return BoardState.from_dict(state)


__all__ = [
    'parse_query_response',
    'compute_board_signature',
    'compute_idle_state_hash',
    'capture_board_state',
    'BoardState',
]
