"""
Engine interface module for ygopro-core CFFI bindings.

This module provides the production interface to ygopro-core, including:
- Card database initialization and lookup
- CFFI callback implementations
- Message parsing utilities
- Buffer reading utilities

All code previously imported from test_fiendsmith_duel.py should now
be imported from this module instead.
"""

import io
import logging
import sqlite3
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ocg_bindings import (
    ffi, load_library,
    LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA, LOCATION_MZONE,
    LOCATION_SZONE, LOCATION_GRAVE, LOCATION_REMOVED, LOCATION_OVERLAY,
    POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
    MSG_RETRY, MSG_HINT, MSG_START, MSG_WIN, MSG_SELECT_BATTLECMD,
    MSG_IDLE, MSG_SELECT_CARD, MSG_SELECT_CHAIN, MSG_SELECT_PLACE,
    MSG_SELECT_POSITION, MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO,
    MSG_SHUFFLE_DECK, MSG_NEW_TURN, MSG_NEW_PHASE, MSG_DRAW,
    TYPE_LINK, TYPE_SYNCHRO, TYPE_XYZ, TYPE_FUSION,
)
from paths import CDB_PATH, get_scripts_path, verify_scripts_path


# Re-export commonly used items from ocg_bindings for convenience
__all__ = [
    # From this module
    'EngineContext',  # Context manager for safe state management
    'init_card_database', 'close_card_database', 'get_card_name', 'location_name',
    'set_lib', 'get_lib',
    'preload_utility_scripts', 'process_messages', 'parse_msg_idle',
    'read_u8', 'read_u16', 'read_u32', 'read_u64', 'read_i32', 'read_cardlist',
    'get_setcodes', 'get_setcode_array', 'clear_setcode_cache',
    'py_card_reader', 'py_card_reader_done', 'py_script_reader', 'py_log_handler',
    # Re-exported from ocg_bindings
    'ffi', 'load_library',
    'LOCATION_DECK', 'LOCATION_HAND', 'LOCATION_EXTRA', 'LOCATION_MZONE',
    'LOCATION_SZONE', 'LOCATION_GRAVE', 'LOCATION_REMOVED', 'LOCATION_OVERLAY',
    'POS_FACEDOWN_DEFENSE', 'POS_FACEUP_ATTACK',
]


# =============================================================================
# Global State
# =============================================================================

_card_db: Optional[sqlite3.Connection] = None
_lib = None  # Library reference for callbacks
_setcode_cache: Dict[int, List[int]] = {}
_setcode_arrays: Dict[Tuple[int, ...], Any] = {}


def get_card_db() -> Optional[sqlite3.Connection]:
    """Get the current card database connection."""
    return _card_db


def set_lib(lib) -> None:
    """Set the library reference for callbacks."""
    global _lib
    _lib = lib


def get_lib():
    """Get the current library reference."""
    return _lib


class EngineContext:
    """Context manager for safe engine state management.

    Ensures library and database are properly initialized and cleaned up.

    Usage:
        with EngineContext() as ctx:
            duel = ctx.create_duel(options)
            # ... use duel ...
        # Library and database automatically cleaned up

    Or for manual control:
        with EngineContext(auto_init_db=False) as ctx:
            ctx.init_database(custom_path)
            # ...
    """

    def __init__(self, auto_init_db: bool = True, cdb_path: Optional[Path] = None):
        """Initialize the engine context.

        Args:
            auto_init_db: If True, automatically initialize the card database.
            cdb_path: Optional custom path to cards.cdb.
        """
        self._auto_init_db = auto_init_db
        self._cdb_path = cdb_path
        self._lib = None
        self._duels: List[Any] = []

    def __enter__(self) -> "EngineContext":
        """Enter the context, loading library and optionally database."""
        self._lib = load_library()
        set_lib(self._lib)

        if self._auto_init_db:
            if not init_card_database(self._cdb_path):
                raise FileNotFoundError(
                    f"Card database not found at {self._cdb_path or CDB_PATH}"
                )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context, cleaning up all resources."""
        # Destroy any active duels
        for duel in self._duels:
            try:
                self._lib.OCG_DestroyDuel(duel)
            except Exception:
                pass
        self._duels.clear()

        # Close database
        close_card_database()

        # Clear library reference
        set_lib(None)
        self._lib = None

        return False  # Don't suppress exceptions

    @property
    def lib(self):
        """Get the library handle."""
        return self._lib

    def create_duel(self, options) -> Any:
        """Create a duel and track it for cleanup.

        Args:
            options: OCG_DuelOptions structure.

        Returns:
            Duel handle.

        Raises:
            RuntimeError: If duel creation fails.
        """
        duel_ptr = ffi.new("OCG_Duel*")
        result = self._lib.OCG_CreateDuel(duel_ptr, options)

        if result != 0:
            error_names = [
                "SUCCESS", "NO_OUTPUT", "NOT_CREATED",
                "NULL_DATA_READER", "NULL_SCRIPT_READER",
                "INCOMPATIBLE_LUA_API", "NULL_RNG_SEED"
            ]
            error_name = error_names[result] if result < len(error_names) else "UNKNOWN"
            raise RuntimeError(f"Failed to create duel: {error_name} ({result})")

        duel = duel_ptr[0]
        self._duels.append(duel)
        return duel

    def destroy_duel(self, duel) -> None:
        """Destroy a duel and remove from tracking."""
        if duel in self._duels:
            self._lib.OCG_DestroyDuel(duel)
            self._duels.remove(duel)

    def init_database(self, cdb_path: Optional[Path] = None) -> bool:
        """Manually initialize the card database."""
        return init_card_database(cdb_path)


# =============================================================================
# Card Database Functions
# =============================================================================

def init_card_database(cdb_path: Optional[Path] = None) -> bool:
    """Initialize the card database connection.

    Args:
        cdb_path: Optional path to cards.cdb. Defaults to CDB_PATH from paths module.

    Returns:
        True if database loaded successfully, False otherwise.
    """
    global _card_db

    if cdb_path is None:
        cdb_path = CDB_PATH

    if cdb_path.exists():
        _card_db = sqlite3.connect(str(cdb_path))
        _card_db.row_factory = sqlite3.Row
        return True
    else:
        return False


def close_card_database() -> None:
    """Close the card database connection."""
    global _card_db
    if _card_db is not None:
        _card_db.close()
        _card_db = None


def get_card_name(code: int) -> str:
    """Look up card name from database."""
    global _card_db
    if _card_db is None:
        return f"Card#{code}"

    try:
        cursor = _card_db.execute(
            "SELECT name FROM texts WHERE id = ?", (code,)
        )
        row = cursor.fetchone()
        if row:
            return row[0]
    except (sqlite3.Error, TypeError, KeyError):
        pass
    return f"Card#{code}"


def location_name(loc: int) -> str:
    """Convert location constant to human-readable name."""
    names = {
        0x01: "Deck",
        0x02: "Hand",
        0x04: "MZone",
        0x08: "SZone",
        0x10: "Grave",
        0x20: "Banished",
        0x40: "Extra",
        0x80: "Overlay",
    }
    return names.get(loc, f"Loc{loc}")


# =============================================================================
# Setcode Handling
# =============================================================================

def get_setcodes(setcode_value: int) -> List[int]:
    """Parse setcode value into array of setcodes.

    Setcodes are packed as multiple 16-bit values.
    """
    if setcode_value in _setcode_cache:
        return _setcode_cache[setcode_value]

    setcodes = []
    val = setcode_value
    while val:
        code = val & 0xFFFF
        if code:
            setcodes.append(code)
        val >>= 16

    _setcode_cache[setcode_value] = setcodes
    return setcodes


def get_setcode_array(setcodes: List[int]):
    """Get or create a persistent setcode array for CFFI.

    Pre-allocates setcode arrays to avoid GC issues during duel.
    Note: These persist for the process lifetime to prevent use-after-free.
    """
    key = tuple(setcodes)
    if key not in _setcode_arrays:
        # Create null-terminated array
        arr = ffi.new("uint16_t[]", len(setcodes) + 1)
        for i, code in enumerate(setcodes):
            arr[i] = code
        arr[len(setcodes)] = 0
        _setcode_arrays[key] = arr
    return _setcode_arrays[key]


def clear_setcode_cache() -> None:
    """Clear the setcode arrays cache.

    Call this between duels if memory is a concern, but only after
    ensuring no duel is referencing the arrays.
    """
    global _setcode_arrays
    _setcode_arrays.clear()


# =============================================================================
# CFFI Callbacks
# =============================================================================

@ffi.callback("void(void*, uint32_t, OCG_CardData*)")
def py_card_reader(payload, code, data):
    """Callback to provide card data to the engine."""
    global _card_db

    # Set defaults
    data.code = code
    data.alias = 0
    data.setcodes = ffi.NULL
    data.type = 0
    data.level = 0
    data.attribute = 0
    data.race = 0
    data.attack = 0
    data.defense = 0
    data.lscale = 0
    data.rscale = 0
    data.link_marker = 0

    if _card_db is None:
        return

    try:
        cursor = _card_db.execute(
            "SELECT * FROM datas WHERE id = ?", (code,)
        )
        row = cursor.fetchone()
        if row:
            data.code = row["id"]
            data.alias = row["alias"] or 0
            data.type = row["type"] or 0

            # Parse level field (contains level, lscale, rscale)
            level_raw = row["level"] or 0
            data.level = level_raw & 0xFF
            data.lscale = (level_raw >> 24) & 0xFF
            data.rscale = (level_raw >> 16) & 0xFF

            data.attribute = row["attribute"] or 0
            data.race = row["race"] or 0
            data.attack = row["atk"] if row["atk"] is not None else 0
            data.defense = row["def"] if row["def"] is not None else 0

            # Handle Link monsters
            if data.type & TYPE_LINK:
                data.link_marker = data.defense
                data.defense = 0

            # Parse setcodes
            setcode_raw = row["setcode"] or 0
            if setcode_raw:
                setcodes = get_setcodes(setcode_raw)
                if setcodes:
                    arr = get_setcode_array(setcodes)
                    data.setcodes = arr
    except Exception as e:
        logging.warning(f"Card reader error for code {code}: {e}")


@ffi.callback("void(void*, OCG_CardData*)")
def py_card_reader_done(payload, data):
    """Callback when card reading is complete."""
    pass


@ffi.callback("int(void*, OCG_Duel, const char*)")
def py_script_reader(payload, duel, name):
    """Callback to load Lua scripts for cards."""
    global _lib

    if _lib is None:
        return 0

    script_name = ffi.string(name).decode("utf-8")
    script_path = get_scripts_path()

    # Search paths in order
    search_paths = [
        script_path / "official" / script_name,
        script_path / "official" / f"{script_name}.lua",
        script_path / script_name,
        script_path / f"{script_name}.lua",
    ]

    # Also try utility scripts
    if not script_name.startswith("c"):
        search_paths.extend([
            script_path / script_name,
            script_path / f"{script_name}.lua",
        ])

    for script_file in search_paths:
        if script_file.exists():
            try:
                script_content = script_file.read_bytes()
                result = _lib.OCG_LoadScript(
                    duel,
                    script_content,
                    len(script_content),
                    name
                )
                return 1 if result == 1 else 0
            except Exception as e:
                logging.warning(f"Script load error for {script_name}: {e}")
                return 0

    # Script not found - this is normal for many cards
    return 0


@ffi.callback("void(void*, const char*, int)")
def py_log_handler(payload, string, log_type):
    """Callback for log messages from the engine."""
    msg = ffi.string(string).decode("utf-8") if string != ffi.NULL else ""
    log_types = {0: "ERROR", 1: "SCRIPT", 2: "DEBUG", 3: "UNDEFINED"}
    type_name = log_types.get(log_type, "UNKNOWN")

    if log_type == 0:  # ERROR
        logging.error(f"[OCG {type_name}] {msg}")
    elif log_type == 2:  # DEBUG
        logging.debug(f"[OCG {type_name}] {msg}")


# =============================================================================
# Buffer Reading Utilities
# =============================================================================

def read_u8(buf: io.BytesIO) -> int:
    """Read unsigned 8-bit integer from buffer."""
    return struct.unpack("<B", buf.read(1))[0]


def read_u16(buf: io.BytesIO) -> int:
    """Read unsigned 16-bit integer from buffer."""
    return struct.unpack("<H", buf.read(2))[0]


def read_u32(buf: io.BytesIO) -> int:
    """Read unsigned 32-bit integer from buffer."""
    return struct.unpack("<I", buf.read(4))[0]


def read_i32(buf: io.BytesIO) -> int:
    """Read signed 32-bit integer from buffer."""
    return struct.unpack("<i", buf.read(4))[0]


def read_u64(buf: io.BytesIO) -> int:
    """Read unsigned 64-bit integer from buffer."""
    return struct.unpack("<Q", buf.read(8))[0]


def read_cardlist(buf: io.BytesIO, extra: bool = False, seq_u8: bool = False) -> List[Tuple]:
    """Read a list of cards from message buffer.

    Args:
        buf: BytesIO buffer
        extra: If True, read extra uint64 + uint8 (for activatable effects)
        seq_u8: If True, sequence is uint8 (for repos), else uint32

    Returns:
        List of tuples: (code, controller, location, sequence, [effect_desc, client_mode])
    """
    cards = []
    count = read_u32(buf)

    for _ in range(count):
        code = read_u32(buf)
        controller = read_u8(buf)
        location = read_u8(buf)
        if seq_u8:
            sequence = read_u8(buf)
        else:
            sequence = read_u32(buf)

        if extra:
            effect_desc = read_u64(buf)
            client_mode = read_u8(buf)
            cards.append((code, controller, location, sequence, effect_desc, client_mode))
        else:
            cards.append((code, controller, location, sequence))

    return cards


# =============================================================================
# Message Parsing
# =============================================================================

def parse_msg_idle(data: bytes) -> Dict[str, Any]:
    """Parse MSG_IDLE message to extract legal actions.

    edo9300 format (from playerop.cpp):
    - player (u8)
    - summonable: count(u32), [code(u32), con(u8), loc(u8), seq(u32)]...
    - spsummon: count(u32), [code(u32), con(u8), loc(u8), seq(u32)]...
    - repos: count(u32), [code(u32), con(u8), loc(u8), seq(u8)]...  # Note: seq is u8!
    - mset: count(u32), [code(u32), con(u8), loc(u8), seq(u32)]...
    - sset: count(u32), [code(u32), con(u8), loc(u8), seq(u32)]...
    - activate: count(u32), [code(u32), con(u8), loc(u8), seq(u32), desc(u64), mode(u8)]...
    - to_bp (u8)
    - to_ep (u8)
    - can_shuffle (u8)
    """
    buf = io.BytesIO(data)

    player = read_u8(buf)
    summonable = read_cardlist(buf)
    spsummon = read_cardlist(buf)
    repos = read_cardlist(buf, seq_u8=True)  # repos uses u8 for sequence
    mset = read_cardlist(buf)
    sset = read_cardlist(buf)
    activatable = read_cardlist(buf, extra=True)
    to_bp = read_u8(buf)
    to_ep = read_u8(buf)
    can_shuffle = read_u8(buf)

    return {
        "player": player,
        "summonable": summonable,
        "spsummon": spsummon,
        "repos": repos,
        "mset": mset,
        "sset": sset,
        "activatable": activatable,
        "to_bp": bool(to_bp),
        "to_ep": bool(to_ep),
        "can_shuffle": bool(can_shuffle),
    }


def process_messages(lib, duel) -> List[Tuple[str, Any]]:
    """Process all pending messages from the duel.

    Returns:
        List of (message_type_name, parsed_data) tuples.
    """
    msg_len = ffi.new("uint32_t*")
    msg_ptr = lib.OCG_DuelGetMessage(duel, msg_len)

    if msg_len[0] == 0:
        return []

    # Copy message data
    msg_data = ffi.buffer(msg_ptr, msg_len[0])[:]
    buf = io.BytesIO(msg_data)

    messages = []

    # edo9300 format: messages are length-prefixed
    # Each message: [4 bytes length][1 byte type][data...]
    while buf.tell() < len(msg_data):
        remaining = len(msg_data) - buf.tell()
        if remaining < 4:
            break

        # Read message length (includes type byte)
        msg_length = read_u32(buf)
        if msg_length == 0 or msg_length > remaining:
            break

        # Read message type
        msg_type = read_u8(buf)
        data_length = msg_length - 1  # Subtract type byte

        # Read message data
        msg_body = buf.read(data_length)
        msg_buf = io.BytesIO(msg_body)

        try:
            if msg_type == MSG_IDLE:
                messages.append(("IDLE", parse_msg_idle(msg_body)))
            elif msg_type == MSG_START:
                messages.append(("START", None))
            elif msg_type == MSG_DRAW:
                player = read_u8(msg_buf)
                count = read_u32(msg_buf)
                cards = []
                for _ in range(count):
                    # Card code may have position info in high bits
                    code_raw = read_u32(msg_buf)
                    code = code_raw & 0x7FFFFFFF  # Mask to get card code
                    cards.append(code)
                messages.append(("DRAW", {"player": player, "count": count, "cards": cards}))
            elif msg_type == MSG_NEW_TURN:
                player = read_u8(msg_buf)
                messages.append(("NEW_TURN", {"player": player}))
            elif msg_type == MSG_NEW_PHASE:
                phase = read_u16(msg_buf)
                messages.append(("NEW_PHASE", {"phase": phase}))
            elif msg_type == MSG_SHUFFLE_DECK:
                player = read_u8(msg_buf)
                messages.append(("SHUFFLE_DECK", {"player": player}))
            elif msg_type == MSG_HINT:
                hint_type = read_u8(msg_buf)
                player = read_u8(msg_buf)
                data = read_u64(msg_buf)
                messages.append(("HINT", {"type": hint_type, "player": player, "data": data}))
            else:
                messages.append((f"MSG_{msg_type}", None))
        except Exception as e:
            messages.append((f"MSG_{msg_type}_ERROR", str(e)))

    return messages


# =============================================================================
# Duel Setup Utilities
# =============================================================================

def preload_utility_scripts(lib, duel) -> bool:
    """Load all required utility scripts before card scripts.

    Returns:
        True if at least one utility script was loaded.
    """
    # Verify scripts directory exists before attempting to load
    verify_scripts_path()
    script_path = get_scripts_path()

    # Order matters - load in dependency order
    utility_scripts = [
        "constant.lua",
        "utility.lua",
        "archetype_setcode_constants.lua",
        "proc_fusion.lua",
        "proc_link.lua",
        "proc_synchro.lua",
        "proc_xyz.lua",
        "proc_ritual.lua",
        "proc_pendulum.lua",
        "proc_normal.lua",
        "proc_equip.lua",
        "proc_gemini.lua",
        "proc_spirit.lua",
        "proc_union.lua",
        "cards_specific_functions.lua",
    ]

    loaded = 0
    for script_name in utility_scripts:
        full_path = script_path / script_name
        if full_path.exists():
            try:
                script_content = full_path.read_bytes()
                script_name_bytes = script_name.encode("utf-8")
                result = lib.OCG_LoadScript(
                    duel,
                    script_content,
                    len(script_content),
                    script_name_bytes
                )
                if result == 1:
                    loaded += 1
            except Exception as e:
                logging.warning(f"Error loading {script_name}: {e}")

    return loaded > 0


# =============================================================================
# Module Initialization
# =============================================================================

if __name__ == "__main__":
    # Quick self-test
    import sys

    print("Testing engine_interface module...")

    # Test database initialization
    if init_card_database():
        print(f"  Card database loaded from {CDB_PATH}")
        name = get_card_name(60764609)  # Fiendsmith Engraver
        print(f"  Card lookup test: {name}")
    else:
        print(f"  Card database not found at {CDB_PATH}")

    # Test library loading
    try:
        lib = load_library()
        major = ffi.new("int*")
        minor = ffi.new("int*")
        lib.OCG_GetVersion(major, minor)
        print(f"  OCG Core version: {major[0]}.{minor[0]}")
    except FileNotFoundError as e:
        print(f"  Library not found: {e}")

    print("engine_interface module OK")
