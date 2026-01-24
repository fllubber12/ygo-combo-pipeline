#!/usr/bin/env python3
"""
Test creating a duel with actual Fiendsmith cards.

This test validates that we can:
1. Load card data from CDB via callback
2. Load Lua scripts via callback
3. Create a duel with Fiendsmith deck
4. Start the duel and process initial game state
5. Parse MSG_IDLE to extract legal actions
"""

import io
import sqlite3
import struct
from pathlib import Path

from ocg_bindings import (
    ffi, load_library,
    LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA, LOCATION_MZONE,
    POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
)


# Paths
CDB_PATH = Path(__file__).parents[2] / "cards.cdb"
SCRIPT_PATH = Path("/tmp/ygopro-scripts")

# Fiendsmith card IDs (verified from cards.cdb)
ENGRAVER = 60764609      # Level 6 monster, hand effect to search
TRACT = 98567237         # Fiendsmith's Tract - Spell card
REQUIEM = 2463794        # Fiendsmith's Requiem - Link-1 monster
DESIRAE = 82135803       # Fiendsmith's Desirae - Level 9 Synchro
KYRIE = 26434972         # Fiendsmith Kyrie - Level 4 tuner
LACRIMA = 46640168       # Fiendsmith's Lacrima - Continuous Spell

# Card type flags
TYPE_LINK = 0x4000000
TYPE_SYNCHRO = 0x2000
TYPE_XYZ = 0x800000
TYPE_FUSION = 0x40

# Message types
MSG_RETRY = 1
MSG_HINT = 2
MSG_WIN = 5
MSG_SELECT_BATTLECMD = 10
MSG_IDLE = 11
MSG_SELECT_CARD = 15
MSG_SELECT_CHAIN = 16
MSG_SELECT_PLACE = 18
MSG_SELECT_POSITION = 19
MSG_SELECT_EFFECTYN = 21
MSG_SELECT_YESNO = 22
MSG_SHUFFLE_DECK = 32
MSG_NEW_TURN = 40
MSG_NEW_PHASE = 41
MSG_DRAW = 90
MSG_START = 4


# Global state
_card_db = None
_lib = None
_setcode_cache = {}


def init_card_database():
    """Initialize the card database connection."""
    global _card_db
    if CDB_PATH.exists():
        _card_db = sqlite3.connect(str(CDB_PATH))
        _card_db.row_factory = sqlite3.Row
        print(f"Card database loaded: {CDB_PATH}")
        return True
    else:
        print(f"Card database not found: {CDB_PATH}")
        return False


def get_setcodes(setcode_value):
    """
    Parse setcode value into array of setcodes.
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


# Pre-allocate setcode arrays to avoid GC issues
_setcode_arrays = {}

def get_setcode_array(setcodes):
    """Get or create a persistent setcode array."""
    key = tuple(setcodes)
    if key not in _setcode_arrays:
        # Create null-terminated array
        arr = ffi.new("uint16_t[]", len(setcodes) + 1)
        for i, code in enumerate(setcodes):
            arr[i] = code
        arr[len(setcodes)] = 0
        _setcode_arrays[key] = arr
    return _setcode_arrays[key]


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
        print(f"Card reader error for code {code}: {e}")


@ffi.callback("void(void*, OCG_CardData*)")
def py_card_reader_done(payload, data):
    """Callback when card reading is complete."""
    pass


@ffi.callback("int(void*, OCG_Duel, const char*)")
def py_script_reader(payload, duel, name):
    """Callback to load Lua scripts for cards."""
    global _lib

    script_name = ffi.string(name).decode("utf-8")

    # Search paths in order
    search_paths = [
        SCRIPT_PATH / "official" / script_name,
        SCRIPT_PATH / "official" / f"{script_name}.lua",
        SCRIPT_PATH / script_name,
        SCRIPT_PATH / f"{script_name}.lua",
    ]

    # Also try utility scripts
    if not script_name.startswith("c"):
        search_paths.extend([
            SCRIPT_PATH / script_name,
            SCRIPT_PATH / f"{script_name}.lua",
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
                print(f"Script load error for {script_name}: {e}")
                return 0

    # Script not found - this is normal for many cards
    return 0


@ffi.callback("void(void*, const char*, int)")
def py_log_handler(payload, string, log_type):
    """Callback for log messages from the engine."""
    msg = ffi.string(string).decode("utf-8") if string != ffi.NULL else ""
    log_types = ["ERROR", "SCRIPT", "DEBUG", "UNDEFINED"]
    type_name = log_types[log_type] if log_type < len(log_types) else "UNKNOWN"
    if log_type == 0:  # Only print errors
        print(f"[OCG {type_name}] {msg}")


def read_u8(buf):
    """Read unsigned 8-bit integer from buffer."""
    return struct.unpack("<B", buf.read(1))[0]


def read_u16(buf):
    """Read unsigned 16-bit integer from buffer."""
    return struct.unpack("<H", buf.read(2))[0]


def read_u32(buf):
    """Read unsigned 32-bit integer from buffer."""
    return struct.unpack("<I", buf.read(4))[0]


def read_u64(buf):
    """Read unsigned 64-bit integer from buffer."""
    return struct.unpack("<Q", buf.read(8))[0]


def read_cardlist(buf, extra=False, seq_u8=False):
    """
    Read a list of cards from message buffer.

    Args:
        buf: BytesIO buffer
        extra: If True, read extra uint64 + uint8 (for activatable effects)
        seq_u8: If True, sequence is uint8 (for repos), else uint32

    Returns list of tuples: (code, controller, location, sequence, [effect_desc, client_mode])
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


def get_card_name(code):
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
    except:
        pass
    return f"Card#{code}"


def location_name(loc):
    """Convert location constant to name."""
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


def parse_msg_idle(data):
    """
    Parse MSG_IDLE message to extract legal actions.

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


def print_legal_actions(idle_data):
    """Pretty print legal actions from MSG_IDLE."""
    print(f"\n=== Legal Actions for Player {idle_data['player']} ===")

    if idle_data["summonable"]:
        print("\nNormal Summonable:")
        for card in idle_data["summonable"]:
            code, con, loc, seq = card[:4]
            print(f"  - {get_card_name(code)} ({location_name(loc)} #{seq})")

    if idle_data["spsummon"]:
        print("\nSpecial Summonable:")
        for card in idle_data["spsummon"]:
            code, con, loc, seq = card[:4]
            print(f"  - {get_card_name(code)} ({location_name(loc)} #{seq})")

    if idle_data["activatable"]:
        print("\nActivatable Effects:")
        for card in idle_data["activatable"]:
            code, con, loc, seq, effect_desc, client_mode = card
            # Decode effect description - low 32 bits are string ID, high 32 bits are card code
            desc_id = effect_desc & 0xFFFFFFFF
            desc_card = (effect_desc >> 32) & 0xFFFFFFFF
            print(f"  - {get_card_name(code)} ({location_name(loc)} #{seq}) [desc: {desc_id}, mode: {client_mode}]")

    if idle_data["mset"]:
        print("\nMonster Settable:")
        for card in idle_data["mset"]:
            code, con, loc, seq = card[:4]
            print(f"  - {get_card_name(code)}")

    if idle_data["sset"]:
        print("\nSpell/Trap Settable:")
        for card in idle_data["sset"]:
            code, con, loc, seq = card[:4]
            print(f"  - {get_card_name(code)}")

    print(f"\nPhase options: to_bp={idle_data['to_bp']}, to_ep={idle_data['to_ep']}")


def process_messages(lib, duel):
    """Process all pending messages from the duel."""
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


def preload_utility_scripts(lib, duel):
    """Load all required utility scripts before card scripts."""
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
        script_path = SCRIPT_PATH / script_name
        if script_path.exists():
            try:
                script_content = script_path.read_bytes()
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
                print(f"Error loading {script_name}: {e}")

    print(f"Preloaded {loaded} utility scripts")
    return loaded > 0


def create_fiendsmith_duel():
    """Create and run a duel with Fiendsmith deck."""
    global _lib

    print("\n" + "=" * 60)
    print("Testing Fiendsmith Duel")
    print("=" * 60 + "\n")

    # Initialize
    has_cdb = init_card_database()
    if not has_cdb:
        print("Cannot proceed without card database")
        return False

    _lib = load_library()
    print("Library loaded")

    # Create duel options
    options = ffi.new("OCG_DuelOptions*")

    # Set seed
    options.seed[0] = 12345
    options.seed[1] = 67890
    options.seed[2] = 11111
    options.seed[3] = 22222

    # Set flags (MR5)
    options.flags = (5 << 16)

    # Set player info
    options.team1.startingLP = 8000
    options.team1.startingDrawCount = 2  # Draw 2 more (we put 3 in hand already)
    options.team1.drawCountPerTurn = 1

    options.team2.startingLP = 8000
    options.team2.startingDrawCount = 5
    options.team2.drawCountPerTurn = 1

    # Set callbacks
    options.cardReader = py_card_reader
    options.payload1 = ffi.NULL
    options.scriptReader = py_script_reader
    options.payload2 = ffi.NULL
    options.logHandler = py_log_handler
    options.payload3 = ffi.NULL
    options.cardReaderDone = py_card_reader_done
    options.payload4 = ffi.NULL
    options.enableUnsafeLibraries = 0

    # Create duel
    duel_ptr = ffi.new("OCG_Duel*")
    result = _lib.OCG_CreateDuel(duel_ptr, options)

    if result != 0:
        error_names = [
            "SUCCESS", "NO_OUTPUT", "NOT_CREATED",
            "NULL_DATA_READER", "NULL_SCRIPT_READER",
            "INCOMPATIBLE_LUA_API", "NULL_RNG_SEED"
        ]
        error_name = error_names[result] if result < len(error_names) else "UNKNOWN"
        print(f"Failed to create duel: {error_name} ({result})")
        return False

    duel = duel_ptr[0]
    print("Duel created successfully")

    # Preload utility scripts
    if not preload_utility_scripts(_lib, duel):
        print("Warning: Failed to load utility scripts")

    # Add cards to Player 0's deck
    print("\nAdding Fiendsmith deck to Player 0...")

    # Normal monster for filler (The 13th Grave = 32864)
    FILLER = 32864

    # Put Fiendsmith cards directly in hand for testing (deck gets shuffled)
    hand_cards = [
        ENGRAVER, ENGRAVER,  # 2x Fiendsmith Engraver in hand
        TRACT,               # 1x Fiendsmith's Tract in hand
    ]

    for i, code in enumerate(hand_cards):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_HAND
        card_info.seq = i
        card_info.pos = POS_FACEUP_ATTACK  # Face-up in hand
        _lib.OCG_DuelNewCard(duel, card_info)

    print(f"  Added {len(hand_cards)} cards to hand")

    # Build deck with some Fiendsmith Spells/Traps (for Engraver to search)
    main_deck = [
        TRACT, TRACT,     # 2x more Fiendsmith's Tract in deck
        KYRIE, KYRIE,     # 2x Fiendsmith Kyrie (Trap) in deck
    ]
    # Fill rest with normal monsters
    while len(main_deck) < 40:
        main_deck.append(FILLER)

    for i, code in enumerate(main_deck):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_DECK
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        _lib.OCG_DuelNewCard(duel, card_info)

    print(f"  Added {len(main_deck)} cards to deck")

    # Extra deck (Link and Synchro monsters)
    extra_deck = [
        REQUIEM,    # Fiendsmith's Requiem (Link-1)
        DESIRAE,    # Fiendsmith's Desirae (Level 9 Synchro)
        LACRIMA,    # Fiendsmith's Lacrima (Level 6 Synchro)
    ]

    for i, code in enumerate(extra_deck):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_EXTRA
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        _lib.OCG_DuelNewCard(duel, card_info)

    print(f"  Added {len(extra_deck)} cards to extra deck")

    # Player 1 also needs a deck (minimum 40)
    print("\nAdding filler deck to Player 1...")
    for i in range(40):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 1
        card_info.duelist = 0
        card_info.code = FILLER  # Normal monster
        card_info.con = 1
        card_info.loc = LOCATION_DECK
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        _lib.OCG_DuelNewCard(duel, card_info)

    print("  Added 40 cards to main deck")

    # Start duel
    print("\n" + "-" * 40)
    _lib.OCG_StartDuel(duel)
    print("Duel started!")

    # Process until we get MSG_IDLE or hit max iterations
    max_iterations = 100
    found_idle = False

    for i in range(max_iterations):
        status = _lib.OCG_DuelProcess(duel)
        status_names = ["END", "AWAITING", "CONTINUE"]
        status_name = status_names[status] if status < len(status_names) else "UNKNOWN"

        messages = process_messages(_lib, duel)

        for msg_type, msg_data in messages:
            if msg_type == "IDLE":
                print("\n" + "-" * 40)
                print("Received MSG_IDLE - extracting legal actions")
                print_legal_actions(msg_data)
                found_idle = True
                break
            elif msg_type == "DRAW":
                player = msg_data["player"]
                count = msg_data["count"]
                cards = msg_data["cards"]
                card_names = [get_card_name(c) for c in cards]
                print(f"Player {player} drew {count} card(s): {', '.join(card_names)}")
            elif msg_type == "NEW_TURN":
                print(f"Turn start: Player {msg_data['player']}")
            elif msg_type == "NEW_PHASE":
                phase = msg_data["phase"]
                phase_names = {0x01: "Draw", 0x02: "Standby", 0x04: "Main1",
                               0x08: "Battle", 0x10: "Main2", 0x20: "End"}
                print(f"Phase: {phase_names.get(phase, phase)}")

        if found_idle:
            break

        if status == 0:  # OCG_DUEL_STATUS_END
            print("Duel ended unexpectedly")
            break
        elif status == 1:  # OCG_DUEL_STATUS_AWAITING
            # Need to provide a response - for now just continue
            print(f"Awaiting response at iteration {i}")
            break

    # Cleanup
    _lib.OCG_DestroyDuel(duel)
    print("\n" + "=" * 60)
    if found_idle:
        print("Fiendsmith duel test completed successfully!")
    else:
        print("Test completed but MSG_IDLE not found")
    print("=" * 60)

    return found_idle


if __name__ == "__main__":
    success = create_fiendsmith_duel()
    exit(0 if success else 1)
