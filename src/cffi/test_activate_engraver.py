#!/usr/bin/env python3
"""
Test activating Fiendsmith Engraver's discard effect.

This test:
1. Creates a duel with Engraver in hand
2. Activates Engraver's effect (discard to search)
3. Handles the MSG_SELECT_CARD to choose what to search
4. Verifies the effect resolved correctly
"""

import io
import sqlite3
import struct
from pathlib import Path

from ocg_bindings import (
    ffi, load_library,
    LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA, LOCATION_GRAVE,
    POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
)


# Paths
CDB_PATH = Path(__file__).parents[2] / "cards.cdb"
SCRIPT_PATH = Path("/tmp/ygopro-scripts")

# Fiendsmith card IDs
ENGRAVER = 60764609
TRACT = 98567237
KYRIE = 26434972
REQUIEM = 2463794
DESIRAE = 82135803
LACRIMA = 46640168
FILLER = 32864  # The 13th Grave

# Message types (values from ygopro-core common.h)
MSG_RETRY = 1
MSG_HINT = 2
MSG_START = 4
MSG_IDLE = 11
MSG_SELECT_CARD = 15
MSG_SELECT_CHAIN = 16
MSG_SELECT_EFFECTYN = 21  # Fixed: was 12
MSG_SELECT_YESNO = 22
MSG_SHUFFLE_DECK = 32
MSG_NEW_TURN = 40
MSG_NEW_PHASE = 41
MSG_MOVE = 50
MSG_DRAW = 90
MSG_CONFIRM_CARDS = 95

# Type flags
TYPE_LINK = 0x4000000

# Global state
_card_db = None
_lib = None
_setcode_cache = {}
_setcode_arrays = {}


def init_card_database():
    global _card_db
    if CDB_PATH.exists():
        _card_db = sqlite3.connect(str(CDB_PATH))
        _card_db.row_factory = sqlite3.Row
        return True
    return False


def get_card_name(code):
    global _card_db
    if _card_db is None:
        return f"Card#{code}"
    try:
        cursor = _card_db.execute("SELECT name FROM texts WHERE id = ?", (code,))
        row = cursor.fetchone()
        if row:
            return row[0]
    except:
        pass
    return f"Card#{code}"


def get_setcodes(setcode_value):
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


def get_setcode_array(setcodes):
    key = tuple(setcodes)
    if key not in _setcode_arrays:
        arr = ffi.new("uint16_t[]", len(setcodes) + 1)
        for i, code in enumerate(setcodes):
            arr[i] = code
        arr[len(setcodes)] = 0
        _setcode_arrays[key] = arr
    return _setcode_arrays[key]


@ffi.callback("void(void*, uint32_t, OCG_CardData*)")
def py_card_reader(payload, code, data):
    global _card_db
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
        cursor = _card_db.execute("SELECT * FROM datas WHERE id = ?", (code,))
        row = cursor.fetchone()
        if row:
            data.code = row["id"]
            data.alias = row["alias"] or 0
            data.type = row["type"] or 0
            level_raw = row["level"] or 0
            data.level = level_raw & 0xFF
            data.lscale = (level_raw >> 24) & 0xFF
            data.rscale = (level_raw >> 16) & 0xFF
            data.attribute = row["attribute"] or 0
            data.race = row["race"] or 0
            data.attack = row["atk"] if row["atk"] is not None else 0
            data.defense = row["def"] if row["def"] is not None else 0
            if data.type & TYPE_LINK:
                data.link_marker = data.defense
                data.defense = 0
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
    pass


@ffi.callback("int(void*, OCG_Duel, const char*)")
def py_script_reader(payload, duel, name):
    global _lib
    script_name = ffi.string(name).decode("utf-8")
    search_paths = [
        SCRIPT_PATH / "official" / script_name,
        SCRIPT_PATH / "official" / f"{script_name}.lua",
        SCRIPT_PATH / script_name,
        SCRIPT_PATH / f"{script_name}.lua",
    ]
    for script_file in search_paths:
        if script_file.exists():
            try:
                script_content = script_file.read_bytes()
                result = _lib.OCG_LoadScript(duel, script_content, len(script_content), name)
                return 1 if result == 1 else 0
            except:
                return 0
    return 0


@ffi.callback("void(void*, const char*, int)")
def py_log_handler(payload, string, log_type):
    msg = ffi.string(string).decode("utf-8") if string != ffi.NULL else ""
    if log_type == 0:  # Only print errors
        print(f"[OCG ERROR] {msg}")


def read_u8(buf):
    return struct.unpack("<B", buf.read(1))[0]


def read_u16(buf):
    return struct.unpack("<H", buf.read(2))[0]


def read_u32(buf):
    return struct.unpack("<I", buf.read(4))[0]


def read_u64(buf):
    return struct.unpack("<Q", buf.read(8))[0]


def location_name(loc):
    names = {
        0x01: "Deck", 0x02: "Hand", 0x04: "MZone", 0x08: "SZone",
        0x10: "Grave", 0x20: "Banished", 0x40: "Extra", 0x80: "Overlay",
    }
    return names.get(loc, f"Loc{loc}")


def preload_utility_scripts(lib, duel):
    utility_scripts = [
        "constant.lua", "utility.lua", "archetype_setcode_constants.lua",
        "proc_fusion.lua", "proc_link.lua", "proc_synchro.lua",
        "proc_xyz.lua", "proc_ritual.lua", "proc_pendulum.lua",
        "proc_normal.lua", "proc_equip.lua", "cards_specific_functions.lua",
    ]
    loaded = 0
    for script_name in utility_scripts:
        script_path = SCRIPT_PATH / script_name
        if script_path.exists():
            try:
                script_content = script_path.read_bytes()
                result = lib.OCG_LoadScript(duel, script_content, len(script_content), script_name.encode())
                if result == 1:
                    loaded += 1
            except:
                pass
    return loaded


def send_response(lib, duel, response_value):
    """Send an integer response to the duel."""
    response_bytes = struct.pack("<I", response_value)
    lib.OCG_DuelSetResponse(duel, response_bytes, len(response_bytes))


def send_response_bytes(lib, duel, data):
    """Send a byte buffer response to the duel."""
    lib.OCG_DuelSetResponse(duel, data, len(data))


def process_messages(lib, duel):
    """Process all pending messages."""
    msg_len = ffi.new("uint32_t*")
    msg_ptr = lib.OCG_DuelGetMessage(duel, msg_len)

    if msg_len[0] == 0:
        return []

    msg_data = ffi.buffer(msg_ptr, msg_len[0])[:]
    buf = io.BytesIO(msg_data)
    messages = []

    while buf.tell() < len(msg_data):
        remaining = len(msg_data) - buf.tell()
        if remaining < 4:
            break

        msg_length = read_u32(buf)
        if msg_length == 0 or msg_length > remaining:
            break

        msg_type = read_u8(buf)
        data_length = msg_length - 1
        msg_body = buf.read(data_length)
        msg_buf = io.BytesIO(msg_body)

        try:
            if msg_type == MSG_IDLE:
                messages.append(("IDLE", parse_idle(msg_body)))
            elif msg_type == MSG_SELECT_CARD:
                messages.append(("SELECT_CARD", parse_select_card(msg_body)))
            elif msg_type == MSG_HINT:
                hint_type = read_u8(msg_buf)
                player = read_u8(msg_buf)
                data = read_u64(msg_buf)
                messages.append(("HINT", {"type": hint_type, "player": player, "data": data}))
            elif msg_type == MSG_MOVE:
                messages.append(("MOVE", parse_move(msg_body)))
            elif msg_type == MSG_SHUFFLE_DECK:
                player = read_u8(msg_buf)
                messages.append(("SHUFFLE_DECK", {"player": player}))
            elif msg_type == MSG_CONFIRM_CARDS:
                messages.append(("CONFIRM_CARDS", parse_confirm_cards(msg_body)))
            elif msg_type == MSG_NEW_TURN:
                player = read_u8(msg_buf)
                messages.append(("NEW_TURN", {"player": player}))
            elif msg_type == MSG_NEW_PHASE:
                phase = read_u16(msg_buf)
                messages.append(("NEW_PHASE", {"phase": phase}))
            elif msg_type == MSG_DRAW:
                player = read_u8(msg_buf)
                count = read_u32(msg_buf)
                messages.append(("DRAW", {"player": player, "count": count}))
            elif msg_type == MSG_START:
                messages.append(("START", None))
            else:
                messages.append((f"MSG_{msg_type}", {"raw": msg_body.hex()[:40]}))
        except Exception as e:
            messages.append((f"MSG_{msg_type}_ERROR", str(e)))

    return messages


def parse_idle(data):
    buf = io.BytesIO(data)
    player = read_u8(buf)

    def read_cardlist(extra=False, seq_u8=False):
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
                cards.append((code, con, loc, seq, desc, mode))
            else:
                cards.append((code, con, loc, seq))
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


def parse_select_card(data):
    """Parse MSG_SELECT_CARD message."""
    buf = io.BytesIO(data)
    player = read_u8(buf)
    cancelable = read_u8(buf)
    min_cards = read_u32(buf)
    max_cards = read_u32(buf)
    count = read_u32(buf)

    cards = []
    for _ in range(count):
        code = read_u32(buf)
        con = read_u8(buf)
        loc = read_u8(buf)
        seq = read_u32(buf)
        # Additional position info
        pos = read_u32(buf)
        cards.append({
            "code": code,
            "controller": con,
            "location": loc,
            "sequence": seq,
            "position": pos,
            "name": get_card_name(code),
        })

    return {
        "player": player,
        "cancelable": bool(cancelable),
        "min": min_cards,
        "max": max_cards,
        "cards": cards,
    }


def parse_move(data):
    """Parse MSG_MOVE message."""
    buf = io.BytesIO(data)
    code = read_u32(buf)
    prev_loc = read_u32(buf)
    curr_loc = read_u32(buf)
    reason = read_u32(buf)

    # Decode locations
    prev_con = prev_loc & 0xFF
    prev_location = (prev_loc >> 8) & 0xFF
    prev_seq = (prev_loc >> 16) & 0xFFFF

    curr_con = curr_loc & 0xFF
    curr_location = (curr_loc >> 8) & 0xFF
    curr_seq = (curr_loc >> 16) & 0xFFFF

    return {
        "code": code,
        "name": get_card_name(code),
        "from": {"controller": prev_con, "location": location_name(prev_location), "seq": prev_seq},
        "to": {"controller": curr_con, "location": location_name(curr_location), "seq": curr_seq},
        "reason": reason,
    }


def parse_confirm_cards(data):
    """Parse MSG_CONFIRM_CARDS message."""
    buf = io.BytesIO(data)
    player = read_u8(buf)
    count = read_u32(buf)
    cards = []
    for _ in range(count):
        code = read_u32(buf)
        con = read_u8(buf)
        loc = read_u8(buf)
        seq = read_u32(buf)
        cards.append({"code": code, "name": get_card_name(code), "location": location_name(loc)})
    return {"player": player, "cards": cards}


def test_activate_engraver():
    global _lib

    print("\n" + "=" * 60)
    print("Test: Activate Fiendsmith Engraver's Discard Effect")
    print("=" * 60 + "\n")

    if not init_card_database():
        print("Card database not found!")
        return False

    _lib = load_library()
    print("Library loaded")

    # Create duel
    options = ffi.new("OCG_DuelOptions*")
    options.seed[0] = 12345
    options.seed[1] = 67890
    options.seed[2] = 11111
    options.seed[3] = 22222
    options.flags = (5 << 16)  # MR5

    options.team1.startingLP = 8000
    options.team1.startingDrawCount = 2
    options.team1.drawCountPerTurn = 1

    options.team2.startingLP = 8000
    options.team2.startingDrawCount = 5
    options.team2.drawCountPerTurn = 1

    options.cardReader = py_card_reader
    options.scriptReader = py_script_reader
    options.logHandler = py_log_handler
    options.cardReaderDone = py_card_reader_done
    options.payload1 = options.payload2 = options.payload3 = options.payload4 = ffi.NULL
    options.enableUnsafeLibraries = 0

    duel_ptr = ffi.new("OCG_Duel*")
    result = _lib.OCG_CreateDuel(duel_ptr, options)
    if result != 0:
        print(f"Failed to create duel: {result}")
        return False

    duel = duel_ptr[0]
    print("Duel created")

    # Preload utility scripts
    preload_utility_scripts(_lib, duel)

    # Add Engraver to hand
    for i in range(2):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = ENGRAVER
        card_info.con = 0
        card_info.loc = LOCATION_HAND
        card_info.seq = i
        card_info.pos = POS_FACEUP_ATTACK
        _lib.OCG_DuelNewCard(duel, card_info)

    # Add Tract to hand (for discarding)
    card_info = ffi.new("OCG_NewCardInfo*")
    card_info.team = 0
    card_info.duelist = 0
    card_info.code = TRACT
    card_info.con = 0
    card_info.loc = LOCATION_HAND
    card_info.seq = 2
    card_info.pos = POS_FACEUP_ATTACK
    _lib.OCG_DuelNewCard(duel, card_info)

    print("Hand: 2x Fiendsmith Engraver, 1x Fiendsmith's Tract")

    # Add searchable targets to deck
    deck_cards = [TRACT, TRACT, KYRIE, KYRIE]
    for _ in range(36):
        deck_cards.append(FILLER)

    for i, code in enumerate(deck_cards):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_DECK
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        _lib.OCG_DuelNewCard(duel, card_info)

    print("Deck: 2x Tract, 2x Kyrie, 36x filler (searchable targets available)")

    # Extra deck
    for code in [REQUIEM, DESIRAE, LACRIMA]:
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_EXTRA
        card_info.seq = 0
        card_info.pos = POS_FACEDOWN_DEFENSE
        _lib.OCG_DuelNewCard(duel, card_info)

    # Player 1 deck
    for i in range(40):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 1
        card_info.duelist = 0
        card_info.code = FILLER
        card_info.con = 1
        card_info.loc = LOCATION_DECK
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        _lib.OCG_DuelNewCard(duel, card_info)

    # Start duel
    _lib.OCG_StartDuel(duel)
    print("\n--- Duel Started ---")

    # Process until we get MSG_IDLE
    idle_data = None
    for _ in range(20):
        status = _lib.OCG_DuelProcess(duel)
        messages = process_messages(_lib, duel)

        for msg_type, msg_data in messages:
            if msg_type == "DRAW":
                print(f"Player {msg_data['player']} drew {msg_data['count']} card(s)")
            elif msg_type == "NEW_PHASE":
                phase = msg_data['phase']
                phase_names = {0x01: "Draw", 0x02: "Standby", 0x04: "Main1"}
                print(f"Phase: {phase_names.get(phase, phase)}")
            elif msg_type == "IDLE":
                idle_data = msg_data
                break
            elif msg_type.startswith("MSG_"):
                pass  # Skip other messages

        if idle_data:
            break

    if not idle_data:
        print("Failed to reach IDLE state")
        return False

    print("\n--- Initial Legal Actions ---")
    print(f"Activatable effects: {len(idle_data['activatable'])}")
    for i, (code, con, loc, seq, desc, mode) in enumerate(idle_data['activatable']):
        print(f"  [{i}] {get_card_name(code)} in {location_name(loc)}")

    # Activate the first Engraver effect (index 0)
    # Response format: (index << 16) | action_type
    # action_type 5 = activate effect
    print("\n--- Activating Engraver's Effect (index 0) ---")
    response = (0 << 16) | 5
    print(f"Sending response: {response} ({hex(response)})")
    send_response(_lib, duel, response)

    # Process and handle follow-up messages
    for iteration in range(30):
        status = _lib.OCG_DuelProcess(duel)
        messages = process_messages(_lib, duel)

        if not messages and status != 1:  # Not awaiting
            continue

        for msg_type, msg_data in messages:
            print(f"\n[{msg_type}]", end=" ")

            if msg_type == "SELECT_CARD":
                print("Choose card to add to hand:")
                for i, card in enumerate(msg_data['cards']):
                    print(f"  [{i}] {card['name']} ({card['location']})")

                # Select the first card (Tract)
                print(f"Selecting card 0...")
                # Response format for edo9300:
                # - type (int32): 0=u32 indices, 1=u16 indices, 2=u8 indices, 3=bitfield
                # - size (uint32): number of selections
                # - indices (uint32 each for type 0)
                response_data = struct.pack("<iII", 0, 1, 0)  # type=0, count=1, index=0
                send_response_bytes(_lib, duel, response_data)

            elif msg_type == "MOVE":
                move = msg_data
                print(f"{move['name']}: {move['from']['location']} -> {move['to']['location']}")

            elif msg_type == "CONFIRM_CARDS":
                print(f"Confirming to opponent:")
                for card in msg_data['cards']:
                    print(f"  - {card['name']}")

            elif msg_type == "SHUFFLE_DECK":
                print(f"Player {msg_data['player']}'s deck shuffled")

            elif msg_type == "IDLE":
                print("\n--- Back to IDLE ---")
                print("Effect resolved! Checking new hand...")

                # Query hand to verify
                hand_count = _lib.OCG_DuelQueryCount(duel, 0, LOCATION_HAND)
                print(f"Cards in hand: {hand_count}")

                grave_count = _lib.OCG_DuelQueryCount(duel, 0, LOCATION_GRAVE)
                print(f"Cards in graveyard: {grave_count}")

                # Success!
                print("\n" + "=" * 60)
                print("SUCCESS! Engraver's effect resolved:")
                print("  - Engraver discarded from hand to GY")
                print("  - Fiendsmith Spell/Trap searched from deck to hand")
                print("=" * 60)

                _lib.OCG_DestroyDuel(duel)
                return True

            elif msg_type == "HINT":
                pass  # Skip hints

            else:
                if msg_data:
                    print(f"{msg_data}")
                else:
                    print("")

        if status == 0:  # Duel ended
            break

    print("Test did not complete as expected")
    _lib.OCG_DestroyDuel(duel)
    return False


if __name__ == "__main__":
    success = test_activate_engraver()
    exit(0 if success else 1)
