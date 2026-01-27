"""
Response builders for combo enumeration.

Build binary response messages for ygopro-core engine.
"""
import struct
from typing import Tuple, List


# =============================================================================
# IDLE RESPONSE TYPES
# =============================================================================
# From ygopro-core field_processor.cpp OCG_DuelSetResponse for MSG_SELECT_IDLECMD

IDLE_RESPONSE_SUMMON = 0       # Normal summon
IDLE_RESPONSE_SPSUMMON = 1     # Special summon
IDLE_RESPONSE_REPOSITION = 2   # Change position
IDLE_RESPONSE_MSET = 3         # Monster set
IDLE_RESPONSE_SSET = 4         # Spell/trap set
IDLE_RESPONSE_ACTIVATE = 5     # Activate effect
IDLE_RESPONSE_TO_BATTLE = 6    # Go to battle phase
IDLE_RESPONSE_TO_END = 7       # End turn / pass


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


def build_activate_response(index: int) -> Tuple[int, bytes]:
    """Build response to activate effect from IDLE.

    Args:
        index: 0-indexed position in activatable[] list.

    Returns:
        (value, bytes) - the response value and packed bytes.
    """
    value = (index << 16) | IDLE_RESPONSE_ACTIVATE
    return value, struct.pack("<I", value)


def build_summon_response(index: int) -> Tuple[int, bytes]:
    """Build response to normal summon from IDLE.

    Args:
        index: 0-indexed position in summonable[] list.

    Returns:
        (value, bytes) - the response value and packed bytes.
    """
    value = (index << 16) | IDLE_RESPONSE_SUMMON
    return value, struct.pack("<I", value)


def build_spsummon_response(index: int) -> Tuple[int, bytes]:
    """Build response to special summon from IDLE.

    Args:
        index: 0-indexed position in spsummon[] list.

    Returns:
        (value, bytes) - the response value and packed bytes.
    """
    value = (index << 16) | IDLE_RESPONSE_SPSUMMON
    return value, struct.pack("<I", value)


def build_mset_response(index: int) -> Tuple[int, bytes]:
    """Build response to set monster from IDLE.

    Args:
        index: 0-indexed position in mset[] list.

    Returns:
        (value, bytes) - the response value and packed bytes.
    """
    value = (index << 16) | IDLE_RESPONSE_MSET
    return value, struct.pack("<I", value)


def build_sset_response(index: int) -> Tuple[int, bytes]:
    """Build response to set spell/trap from IDLE.

    Args:
        index: 0-indexed position in sset[] list.

    Returns:
        (value, bytes) - the response value and packed bytes.
    """
    value = (index << 16) | IDLE_RESPONSE_SSET
    return value, struct.pack("<I", value)


def build_reposition_response(index: int) -> Tuple[int, bytes]:
    """Build response to change position from IDLE.

    Args:
        index: 0-indexed position in repos[] list.

    Returns:
        (value, bytes) - the response value and packed bytes.
    """
    value = (index << 16) | IDLE_RESPONSE_REPOSITION
    return value, struct.pack("<I", value)


def build_pass_response() -> Tuple[int, bytes]:
    """Build response to end main phase (PASS).

    Returns:
        (IDLE_RESPONSE_TO_END, packed bytes).
    """
    return IDLE_RESPONSE_TO_END, struct.pack("<I", IDLE_RESPONSE_TO_END)


def build_to_battle_response() -> Tuple[int, bytes]:
    """Build response to go to battle phase.

    Returns:
        (IDLE_RESPONSE_TO_BATTLE, packed bytes).
    """
    return IDLE_RESPONSE_TO_BATTLE, struct.pack("<I", IDLE_RESPONSE_TO_BATTLE)


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


def build_cancel_select_card_response() -> Tuple[int, bytes]:
    """Build response to cancel card selection (MSG_SELECT_CARD with cancelable=1).

    Returns:
        (-1, packed bytes) - cancel response.
    """
    return -1, struct.pack("<i", -1)


def build_decline_chain_response() -> Tuple[int, bytes]:
    """Build response to decline chain opportunity (MSG_SELECT_CHAIN).

    Returns:
        (-1, packed bytes) - decline response.
    """
    return -1, struct.pack("<i", -1)


def build_chain_response(index: int) -> Tuple[int, bytes]:
    """Build response to activate a chain (MSG_SELECT_CHAIN).

    Args:
        index: 0-indexed position in chainable list.

    Returns:
        (index, packed bytes) - the chain index and response bytes.
    """
    return index, struct.pack("<i", index)


def build_select_place_response(player: int, location: int, sequence: int) -> bytes:
    """Build response to select a zone (MSG_SELECT_PLACE).

    Args:
        player: 0 or 1
        location: LOCATION_* constant (e.g., LOCATION_MZONE=0x04)
        sequence: Zone index (0-4 for main, 5-6 for EMZ)

    Returns:
        Packed response bytes.
    """
    return struct.pack("<BBB", player, location, sequence)


def build_select_position_response(position: int) -> bytes:
    """Build response to select card position (MSG_SELECT_POSITION).

    Args:
        position: Position flags (POS_FACEUP_ATTACK=0x1, etc.)

    Returns:
        Packed response bytes.
    """
    return struct.pack("<I", position)


def build_yesno_response(yes: bool) -> bytes:
    """Build response to YES/NO prompt (MSG_SELECT_YESNO, MSG_SELECT_EFFECTYN).

    Args:
        yes: True for yes, False for no.

    Returns:
        Packed response bytes.
    """
    return struct.pack("<I", 1 if yes else 0)


def build_select_option_response(index: int) -> bytes:
    """Build response to select an option (MSG_SELECT_OPTION).

    Args:
        index: 0-indexed option number.

    Returns:
        Packed response bytes.
    """
    return struct.pack("<I", index)


def build_select_unselect_finish_response() -> Tuple[int, bytes]:
    """Build response to finish selection (MSG_SELECT_UNSELECT_CARD).

    Returns:
        (-1, packed bytes) - finish response.
    """
    return -1, struct.pack("<i", -1)


def build_select_unselect_card_response(index: int) -> Tuple[int, bytes]:
    """Build response to select a card (MSG_SELECT_UNSELECT_CARD).

    Args:
        index: 0-indexed card position.

    Returns:
        (index, packed bytes) - the selection and response bytes.
    """
    return index, struct.pack("<i", index)


def build_select_tribute_response(selected_indices: list) -> bytes:
    """Build response for MSG_SELECT_TRIBUTE.

    Format per ygopro-core parse_response_cards (playerop.cpp:237-275):
    - type (i32): 0 = u32 indices, 1 = u16 indices, 2 = u8 indices
    - count (u32): number of selected cards
    - indices: based on type (u32/u16/u8 each)

    We use type 0 (u32 indices) for consistency with SELECT_CARD.

    Args:
        selected_indices: List of 0-indexed tribute card indices.

    Returns:
        Packed response bytes.
    """
    count = len(selected_indices)
    data = struct.pack('<iI', 0, count)  # type=0, count
    for idx in selected_indices:
        data += struct.pack('<I', idx)  # u32 indices
    return data
