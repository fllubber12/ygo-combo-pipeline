"""
Message parsers for combo enumeration.

Parse binary messages from ygopro-core engine into Python dictionaries.
"""
import io
import struct
from typing import Union, Dict, Any, Tuple, List, BinaryIO

from card_validator import CardValidator


# =============================================================================
# BINARY READERS
# =============================================================================

def read_u8(buf: BinaryIO) -> int:
    return struct.unpack("<B", buf.read(1))[0]


def read_u16(buf: BinaryIO) -> int:
    return struct.unpack("<H", buf.read(2))[0]


def read_u32(buf: BinaryIO) -> int:
    return struct.unpack("<I", buf.read(4))[0]


def read_i32(buf: BinaryIO) -> int:
    return struct.unpack("<i", buf.read(4))[0]


def read_u64(buf: BinaryIO) -> int:
    return struct.unpack("<Q", buf.read(8))[0]


# =============================================================================
# MESSAGE PARSERS
# =============================================================================

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


# =============================================================================
# SELECT_SUM PARSING
# =============================================================================

# Global validator instance for level lookup
_card_validator = None


def _get_card_validator() -> CardValidator:
    """Get or create the global CardValidator instance."""
    global _card_validator
    if _card_validator is None:
        _card_validator = CardValidator()
    return _card_validator


def _parse_sum_card_11byte(data: bytes, offset: int, index: int) -> Tuple[dict, int]:
    """Parse a single card entry from MSG_SELECT_SUM (11-byte format).

    Card format per ygopro-core field.cpp:
    - code: 4 bytes LE (card passcode)
    - controller: 1 byte
    - location: 1 byte
    - sequence: 1 byte
    - sum_param: 4 bytes LE
      - Low 16 bits: primary level/value
      - High 16 bits: secondary level (for variable-level cards like Gagaga)

    Returns:
        Tuple of (card_dict, new_offset)
    """
    if offset + 11 > len(data):
        raise ValueError(f"Not enough data for card at offset {offset}")

    code = struct.unpack_from('<I', data, offset)[0]
    controller = data[offset + 4]
    location = data[offset + 5]
    sequence = data[offset + 6]  # 1 byte, NOT 4!
    sum_param = struct.unpack_from('<I', data, offset + 7)[0]

    # Extract level values from sum_param
    level1 = sum_param & 0xFFFF
    level2 = (sum_param >> 16) & 0xFFFF

    # Use level1 as primary value; level2 is for variable-level monsters
    effective_level = level1 if 1 <= level1 <= 12 else 0

    card = {
        'index': index,
        'code': code,
        'controller': controller,
        'location': location,
        'sequence': sequence,
        'sum_param': sum_param,
        'value': effective_level,
        'level': effective_level,
        'level2': level2 if 1 <= level2 <= 12 else effective_level,
    }

    return card, offset + 11


def _parse_sum_card_18byte(data: bytes, offset: int, index: int) -> Tuple[dict, int]:
    """Parse a single card entry from MSG_SELECT_SUM (18-byte format).

    Card format (18 bytes) - verified against ygopro-core source (card.h:26-31):
    - code: 4 bytes LE (card passcode)
    - controller: 1 byte
    - location: 1 byte
    - sequence: 4 bytes LE
    - position: 4 bytes LE (card position flags)
    - sum_param: 4 bytes LE (level for sum calculation)

    The loc_info struct in ygopro-core is:
        struct loc_info {
            uint8_t controler;   // 1 byte
            uint8_t location;    // 1 byte
            uint32_t sequence;   // 4 bytes
            uint32_t position;   // 4 bytes
        };
    Total: code(4) + loc_info(10) + sum_param(4) = 18 bytes

    NOTE: This ygopro-core build may not populate sum_param correctly.
    We fall back to verified_cards.json for level lookup when sum_param is 0.

    Returns:
        Tuple of (card_dict, new_offset)
    """
    if offset + 18 > len(data):
        raise ValueError(f"Not enough data for 18-byte card at offset {offset}")

    code = struct.unpack_from('<I', data, offset)[0]
    controller = data[offset + 4]
    location = data[offset + 5]
    sequence = struct.unpack_from('<I', data, offset + 6)[0]
    position = struct.unpack_from('<I', data, offset + 10)[0]
    sum_param = struct.unpack_from('<I', data, offset + 14)[0]

    # Extract level from sum_param (low 16 bits = primary level)
    level = sum_param & 0xFFFF
    level2 = (sum_param >> 16) & 0xFFFF

    # If sum_param is 0 or invalid, try to look up from verified cards
    if level == 0 or level > 12:
        validator = _get_card_validator()
        verified = validator.get_card(code)
        if verified and 'level' in verified:
            level = verified['level']
        elif verified and 'rank' in verified:
            level = verified['rank']  # For Xyz monsters
        elif verified and 'link_rating' in verified:
            level = verified['link_rating']  # For Link monsters

    card = {
        'index': index,
        'code': code,
        'controller': controller,
        'location': location,
        'sequence': sequence,
        'position': position,
        'sum_param': sum_param,
        'sum_param_raw': sum_param,  # Keep original for debugging
        'value': level if 1 <= level <= 12 else sum_param,
        'level': level if 1 <= level <= 12 else sum_param,
        'level2': level2 if 1 <= level2 <= 12 else 0,
    }

    return card, offset + 18


def _parse_sum_card_16byte(data: bytes, offset: int, index: int) -> Tuple[dict, int]:
    """Parse a single card entry from MSG_SELECT_SUM (16-byte format).

    Some ygopro-core builds use 16-byte card entries without the position field:
    - code: 4 bytes LE (card passcode)
    - controller: 1 byte
    - location: 1 byte
    - sequence: 4 bytes LE
    - sum_param: 4 bytes LE (level for sum calculation)
    - padding: 2 bytes

    Total: 16 bytes (vs 18 with position field)

    Returns:
        Tuple of (card_dict, new_offset)
    """
    if offset + 16 > len(data):
        raise ValueError(f"Not enough data for 16-byte card at offset {offset}")

    code = struct.unpack_from('<I', data, offset)[0]
    controller = data[offset + 4]
    location = data[offset + 5]
    sequence = struct.unpack_from('<I', data, offset + 6)[0]
    sum_param = struct.unpack_from('<I', data, offset + 10)[0]

    # Extract level from sum_param (low 16 bits = primary level)
    level = sum_param & 0xFFFF
    level2 = (sum_param >> 16) & 0xFFFF

    # If sum_param is 0 or invalid, try to look up from verified cards
    if level == 0 or level > 12:
        validator = _get_card_validator()
        verified = validator.get_card(code)
        if verified and 'level' in verified:
            level = verified['level']
        elif verified and 'rank' in verified:
            level = verified['rank']
        elif verified and 'link_rating' in verified:
            level = verified['link_rating']

    card = {
        'index': index,
        'code': code,
        'controller': controller,
        'location': location,
        'sequence': sequence,
        'position': 0,  # Not available in 16-byte format
        'sum_param': sum_param,
        'sum_param_raw': sum_param,
        'value': level if 1 <= level <= 12 else sum_param,
        'level': level if 1 <= level <= 12 else sum_param,
        'level2': level2 if 1 <= level2 <= 12 else 0,
    }

    return card, offset + 16


def parse_select_sum(data: Union[bytes, BinaryIO]) -> Dict[str, Any]:
    """Parse MSG_SELECT_SUM message for material/card selection.

    Format verified against ygopro-core source (playerop.cpp:796-819, card.h:26-31):
    - Header uses BIG-ENDIAN for target_sum and can_count
    - Card entries are 18 bytes (including 4-byte position field)

    Header format:
    - player: 1 byte (offset 0)
    - select_mode: 1 byte (offset 1) - 0 = exactly equal, 1 = at least equal
    - select_min: 1 byte (offset 2)
    - select_max: 1 byte (offset 3)
    - target_sum: 4 bytes BE (offset 4-7) - target sum
    - must_count: 4 bytes BE (offset 8-11) - treated as can_count
    - padding: 3 bytes (offset 12-14)
    - cards[]: 18 bytes each starting at offset 15

    Card format (18 bytes) from ygopro-core loc_info struct:
    - code: 4 bytes LE (card passcode)
    - controller: 1 byte
    - location: 1 byte
    - sequence: 4 bytes LE
    - position: 4 bytes LE (card position flags)
    - sum_param: 4 bytes LE (level for sum calculation)

    Note: sum_param encodes level in low 16 bits, optional secondary level in high 16 bits.

    Returns dict with parsed data for _handle_select_sum.
    """
    raw_data = data if isinstance(data, bytes) else data.read()

    try:
        offset = 0

        # Header
        player = raw_data[offset]; offset += 1
        select_mode = raw_data[offset]; offset += 1
        select_min = raw_data[offset]; offset += 1
        select_max = raw_data[offset]; offset += 1

        # Note: target_sum and card count are BIG-ENDIAN u32 in this ygopro-core build
        target_sum = struct.unpack_from('>I', raw_data, offset)[0]; offset += 4
        # The count at offset 8-11 appears to be the selectable card count
        can_count = struct.unpack_from('>I', raw_data, offset)[0]; offset += 4
        must_count = 0  # No must-select cards observed in this format
        offset += 3  # Skip padding bytes to align cards at offset 15

        # Cards (all are can-select in observed data)
        # Use 18-byte card entries; if message is truncated, parse only complete cards
        header_size = 15
        card_size = 18
        available_bytes = len(raw_data) - header_size
        max_complete_cards = available_bytes // card_size

        must_select = []
        can_select = []
        cards_to_parse = min(can_count, max_complete_cards)
        for i in range(cards_to_parse):
            card, offset = _parse_sum_card_18byte(raw_data, offset, i)
            can_select.append(card)

        # Note: can_count in result reflects header value for selection logic
        # Actual parsed cards may be fewer if message was truncated

        return {
            'player': player,
            'select_mode': select_mode,
            'target_sum': target_sum,
            'min': select_min,
            'max': select_max,
            'must_count': must_count,
            'must_select': must_select,
            'can_count': can_count,
            'can_select': can_select,
            '_raw_hex': raw_data.hex(),  # DEBUG: always include for analysis
            '_raw_len': len(raw_data),
        }

    except Exception as e:
        # Return error info for debugging
        return {
            'player': raw_data[0] if len(raw_data) > 0 else 0,
            'select_mode': 0,
            'target_sum': 0,
            'min': 0,
            'max': 0,
            'must_count': 0,
            'must_select': [],
            'can_count': 0,
            'can_select': [],
            '_parse_error': str(e),
            '_raw_hex': raw_data.hex() if raw_data else '',
        }
