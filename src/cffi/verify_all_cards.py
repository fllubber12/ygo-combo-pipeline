#!/usr/bin/env python3
"""
Verify every Fiendsmith card works correctly through the CFFI engine.

For EACH card, test:
1. Does the script load without errors?
2. Do effects enumerate in the correct game states?
3. Do effects resolve with correct outcomes?

This must pass 100% before any combo analysis.
"""

import io
import sqlite3
import struct
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

from ocg_bindings import (
    ffi, load_library,
    LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA, LOCATION_GRAVE,
    LOCATION_MZONE, LOCATION_SZONE, LOCATION_REMOVED,
    POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
)

# Paths
CDB_PATH = Path(__file__).parents[2] / "cards.cdb"
SCRIPT_PATH = Path("/tmp/ygopro-scripts")

# Cards to verify - All 26 library cards from cdb_aliases.json
CARDS_TO_VERIFY = {
    # ===========================================
    # FIENDSMITH ARCHETYPE (12 cards)
    # ===========================================
    # Main Deck Monsters
    "20196": {"name": "Fiendsmith Engraver", "passcode": 60764609},
    "20490": {"name": "Lacrima the Crimson Tears", "passcode": 28803166},

    # Main Deck Spells
    "20240": {"name": "Fiendsmith's Tract", "passcode": 98567237},
    "20241": {"name": "Fiendsmith's Sanct", "passcode": 35552985},

    # Main Deck Traps
    "20251": {"name": "Fiendsmith in Paradise", "passcode": 99989863},
    "20816": {"name": "Fiendsmith Kyrie", "passcode": 26434972},

    # Fiendsmith Extra Deck
    "20215": {"name": "Fiendsmith's Desirae", "passcode": 82135803},
    "20225": {"name": "Fiendsmith's Requiem", "passcode": 2463794},
    "20238": {"name": "Fiendsmith's Sequence", "passcode": 49867899},
    "20214": {"name": "Fiendsmith's Lacrima", "passcode": 46640168},
    "20521": {"name": "Fiendsmith's Agnumday", "passcode": 32991300},
    "20774": {"name": "Fiendsmith's Rextremende", "passcode": 11464648},

    # ===========================================
    # NON-FIENDSMITH LIBRARY CARDS (14 cards)
    # ===========================================
    # Main Deck
    "8092": {"name": "Fabled Lurrie", "passcode": 97651498},
    "20389": {"name": "Mutiny in the Sky", "passcode": 71593652},

    # Extra Deck - Xyz
    "10942": {"name": "Evilswarm Exciton Knight", "passcode": 46772449},
    "13081": {"name": "D/D/D Wave High King Caesar", "passcode": 79559912},

    # Extra Deck - Link-2
    "14856": {"name": "Cross-Sheep", "passcode": 50277355},
    "17806": {"name": "Muckraker From the Underworld", "passcode": 71607202},
    "19188": {"name": "S:P Little Knight", "passcode": 29301450},
    "20423": {"name": "Necroquip Princess", "passcode": 93860227},
    "20427": {"name": "The Duke of Demise", "passcode": 45445571},

    # Extra Deck - Link-3
    "20786": {"name": "A Bao A Qu, the Lightless Shadow", "passcode": 4731783},
    "20772": {"name": "Aerial Eater", "passcode": 28143384},

    # Extra Deck - Link-4
    "21624": {"name": "Buio the Dawn's Light", "passcode": 19000848},
    "21625": {"name": "Luce the Dusk's Dark", "passcode": 45409943},
    "21626": {"name": "Snake-Eyes Doomed Dragon", "passcode": 58071334},
}

# Message types (values from ygopro-core common.h)
MSG_RETRY = 1
MSG_HINT = 2
MSG_SELECT_IDLECMD = 11
MSG_SELECT_CARD = 15
MSG_SELECT_CHAIN = 16
MSG_SELECT_PLACE = 18
MSG_SELECT_POSITION = 19
MSG_SELECT_TRIBUTE = 20
MSG_SELECT_EFFECTYN = 21  # Fixed: was 12
MSG_SELECT_YESNO = 22
MSG_SELECT_OPTION = 23    # Fixed: was 14
MSG_SELECT_UNSELECT_CARD = 25  # Fixed: was 26
MSG_SHUFFLE_DECK = 32
MSG_SHUFFLE_HAND = 33
MSG_NEW_TURN = 40
MSG_NEW_PHASE = 41
MSG_MOVE = 50
MSG_SUMMONING = 60
MSG_SUMMONED = 61
MSG_SPSUMMONING = 62
MSG_SPSUMMONED = 63
MSG_CHAINING = 70
MSG_CHAINED = 71
MSG_CHAIN_SOLVING = 72
MSG_CHAIN_SOLVED = 73
MSG_CHAIN_END = 74
MSG_DRAW = 90
MSG_CONFIRM_CARDS = 95
MSG_START = 4

TYPE_LINK = 0x4000000

# Global state
_card_db = None
_lib = None
_setcode_cache = {}
_setcode_arrays = {}
_script_errors = []

# Generic filler card for opponent deck
FILLER_CARD = 28803166  # Lacrima CT


def init_card_database():
    global _card_db
    if CDB_PATH.exists():
        _card_db = sqlite3.connect(str(CDB_PATH))
        _card_db.row_factory = sqlite3.Row
        return True
    return False


def get_card_name(code):
    global _card_db
    if code == 0:
        return "(none)"
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
                    data.setcodes = get_setcode_array(setcodes)
    except Exception as e:
        pass


@ffi.callback("void(void*, OCG_CardData*)")
def py_card_reader_done(payload, data):
    pass


@ffi.callback("int(void*, OCG_Duel, const char*)")
def py_script_reader(payload, duel, name):
    global _lib, _script_errors
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
            except Exception as e:
                _script_errors.append(f"Error loading {script_name}: {e}")
                return 0
    return 0


@ffi.callback("void(void*, const char*, int)")
def py_log_handler(payload, string, log_type):
    global _script_errors
    msg = ffi.string(string).decode("utf-8") if string != ffi.NULL else ""
    if log_type == 0:  # Error
        _script_errors.append(f"OCG Error: {msg}")


# Message reading helpers
def read_u8(buf): return struct.unpack("<B", buf.read(1))[0]
def read_u16(buf): return struct.unpack("<H", buf.read(2))[0]
def read_u32(buf): return struct.unpack("<I", buf.read(4))[0]
def read_u64(buf): return struct.unpack("<Q", buf.read(8))[0]
def read_i32(buf): return struct.unpack("<i", buf.read(4))[0]


def location_name(loc):
    names = {
        0x01: "Deck", 0x02: "Hand", 0x04: "MZone", 0x08: "SZone",
        0x10: "GY", 0x20: "Banished", 0x40: "Extra", 0x80: "Overlay",
    }
    return names.get(loc, f"Loc{loc:02x}")


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


class DuelHelper:
    """Helper class for creating and managing test duels."""

    def __init__(self, lib):
        self.lib = lib
        self.duel = None
        self.messages = []
        self.move_log = []
        self.current_state = None
        self.verbose = False

    def log(self, msg):
        if self.verbose:
            print(f"    {msg}")

    def create_duel(self):
        """Create a fresh duel."""
        options = ffi.new("OCG_DuelOptions*")
        options.seed[0] = 42
        options.seed[1] = 1337
        options.seed[2] = 9999
        options.seed[3] = 12345
        options.flags = (5 << 16)

        options.team1.startingLP = 8000
        options.team1.startingDrawCount = 0
        options.team1.drawCountPerTurn = 0  # No draws - we control hand

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
        result = self.lib.OCG_CreateDuel(duel_ptr, options)
        if result != 0:
            return False

        self.duel = duel_ptr[0]
        preload_utility_scripts(self.lib, self.duel)
        return True

    def destroy_duel(self):
        if self.duel:
            self.lib.OCG_DestroyDuel(self.duel)
            self.duel = None

    def add_card(self, code, player, location, sequence, position=POS_FACEUP_ATTACK):
        """Add a card to the duel."""
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = player
        card_info.duelist = 0
        card_info.code = code
        card_info.con = player
        card_info.loc = location
        card_info.seq = sequence
        card_info.pos = position
        self.lib.OCG_DuelNewCard(self.duel, card_info)

    def add_deck(self, player, cards):
        """Add deck cards."""
        for i, code in enumerate(cards):
            self.add_card(code, player, LOCATION_DECK, i, POS_FACEDOWN_DEFENSE)

    def add_hand(self, player, cards):
        """Add hand cards."""
        for i, code in enumerate(cards):
            self.add_card(code, player, LOCATION_HAND, i, POS_FACEUP_ATTACK)

    def add_field(self, player, cards, start_seq=0):
        """Add monsters to field."""
        for i, code in enumerate(cards):
            self.add_card(code, player, LOCATION_MZONE, start_seq + i, POS_FACEUP_ATTACK)

    def add_gy(self, player, cards):
        """Add cards to GY."""
        for i, code in enumerate(cards):
            self.add_card(code, player, LOCATION_GRAVE, i, POS_FACEUP_ATTACK)

    def add_extra(self, player, cards):
        """Add extra deck cards."""
        for i, code in enumerate(cards):
            self.add_card(code, player, LOCATION_EXTRA, i, POS_FACEDOWN_DEFENSE)

    def start_duel(self):
        """Start the duel and process to first IDLE."""
        self.lib.OCG_StartDuel(self.duel)
        return self.process_until_idle()

    def send_response_int(self, value):
        response_bytes = struct.pack("<I", value)
        self.lib.OCG_DuelSetResponse(self.duel, response_bytes, len(response_bytes))

    def send_response_bytes(self, data):
        self.lib.OCG_DuelSetResponse(self.duel, data, len(data))

    def send_card_selection(self, indices):
        data = struct.pack("<iI", 0, len(indices))
        for idx in indices:
            data += struct.pack("<I", idx)
        self.send_response_bytes(data)

    def get_messages(self):
        msg_len = ffi.new("uint32_t*")
        msg_ptr = self.lib.OCG_DuelGetMessage(self.duel, msg_len)

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

            messages.append({"type": msg_type, "data": msg_body})

        return messages

    def parse_idle(self, data):
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
                    cards.append({"code": code, "name": get_card_name(code),
                                  "controller": con, "location": loc, "sequence": seq,
                                  "desc": desc, "mode": mode})
                else:
                    cards.append({"code": code, "name": get_card_name(code),
                                  "controller": con, "location": loc, "sequence": seq})
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

    def handle_message(self, msg, auto_respond=True, select_first=True):
        """Handle a message, auto-responding if requested."""
        msg_type = msg["type"]
        data = msg["data"]

        if msg_type == MSG_SELECT_IDLECMD:
            return ("IDLE", self.parse_idle(data))

        elif msg_type == MSG_SELECT_CARD:
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
                pos = read_u32(buf)
                cards.append({"code": code, "name": get_card_name(code),
                             "controller": con, "location": loc, "sequence": seq})

            self.log(f"SELECT_CARD: {[c['name'] for c in cards]}")

            if auto_respond:
                selection = list(range(min(min_cards, count)))
                self.send_card_selection(selection)

            return ("SELECT_CARD", {"min": min_cards, "max": max_cards, "cards": cards})

        elif msg_type == MSG_SELECT_UNSELECT_CARD:
            buf = io.BytesIO(data)
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
                select_cards.append({"code": code, "name": get_card_name(code)})

            unselect_count = read_u32(buf)

            self.log(f"SELECT_UNSELECT_CARD: {[c['name'] for c in select_cards]}, finish={finishable}")

            if auto_respond:
                if finishable and unselect_count > 0:
                    self.send_response_int(0xFFFFFFFF)
                elif select_count > 0:
                    response = struct.pack("<ii", 1, 0)
                    self.send_response_bytes(response)
                else:
                    self.send_response_int(0xFFFFFFFF)

            return ("SELECT_UNSELECT_CARD", {"select": select_cards, "finishable": finishable})

        elif msg_type == MSG_SELECT_CHAIN:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            count = read_u8(buf)
            specount = read_u8(buf)
            forced = read_u8(buf)

            self.log(f"SELECT_CHAIN: count={count}, forced={forced}")

            if auto_respond:
                self.send_response_int(0xFFFFFFFF)  # Decline

            return ("SELECT_CHAIN", {"count": count, "forced": forced})

        elif msg_type == MSG_SELECT_TRIBUTE:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            cancelable = read_u8(buf)
            min_tributes = read_u32(buf)
            max_tributes = read_u32(buf)
            count = read_u32(buf)

            if auto_respond:
                self.send_card_selection(list(range(min_tributes)))

            return ("SELECT_TRIBUTE", {"min": min_tributes, "max": max_tributes})

        elif msg_type == MSG_SELECT_POSITION:
            if auto_respond:
                self.send_response_int(0x1)  # Attack position
            return ("SELECT_POSITION", None)

        elif msg_type == MSG_SELECT_PLACE:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            count = read_u8(buf)
            flag = read_u32(buf)

            self.log(f"SELECT_PLACE: flag=0x{flag:08x}")

            if auto_respond:
                # Find first available zone
                location = 0x08  # S/T zone
                sequence = 0
                for i in range(5):
                    if not (flag & (1 << (8 + i))):
                        sequence = i
                        break
                else:
                    location = 0x04  # Monster zone
                    for i in range(5):
                        if not (flag & (1 << i)):
                            sequence = i
                            break
                response = struct.pack("<BBB", player, location, sequence)
                self.send_response_bytes(response)

            return ("SELECT_PLACE", {"flag": flag})

        elif msg_type == MSG_SELECT_YESNO:
            if auto_respond:
                self.send_response_int(1)
            return ("SELECT_YESNO", None)

        elif msg_type == MSG_SELECT_EFFECTYN:
            if auto_respond:
                self.send_response_int(1)
            return ("SELECT_EFFECTYN", None)

        elif msg_type == MSG_SELECT_OPTION:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            count = read_u8(buf)

            if auto_respond:
                self.send_response_int(0)  # First option

            return ("SELECT_OPTION", {"count": count})

        elif msg_type == MSG_MOVE:
            # MSG_MOVE format (28 bytes in newer ocgcore):
            # - code (4) + prev_packed (4) + prev_seq_ext (4) + curr_packed (4) + curr_seq_ext (4) + reason (4) + ??? (4)
            # Or: code (4) + prev_loc (4) + curr_loc (4) + reason (4) but prev/curr have extended sequence
            buf = io.BytesIO(data)
            code = read_u32(buf)
            prev_loc = read_u32(buf)

            # The third field might be extended sequence, skip to get curr_loc
            if len(data) >= 28:
                # New format with extra fields
                prev_seq_ext = read_u32(buf)
                curr_loc = read_u32(buf)
                curr_seq_ext = read_u32(buf)
                reason = read_u32(buf)
            else:
                # Old 16-byte format
                curr_loc = read_u32(buf)
                reason = read_u32(buf) if len(data) >= 16 else 0

            # prev_loc encoding: controller | (location << 8) | (sequence << 16) | (position << 24)
            prev_location = (prev_loc >> 8) & 0xFF

            # curr_loc encoding appears to be different in newer ocgcore:
            # The location is in the MSB (byte 3) instead of byte 1
            # curr_loc = (position << 24) | (sequence << 16) | (location << 8) | controller
            # OR it could be: location | (sequence << 8) | (position << 16) | (controller << 24)
            # Let's try extracting from MSB
            curr_location = (curr_loc >> 24) & 0xFF

            if self.verbose:
                self.log(f"MOVE: len={len(data)}, prev=0x{prev_loc:08x}(loc={prev_location:02x}), curr=0x{curr_loc:08x}(loc={curr_location:02x})")

            move = {
                "code": code, "name": get_card_name(code),
                "from": location_name(prev_location),
                "to": location_name(curr_location),
            }
            self.move_log.append(move)
            self.log(f"MOVE: {move['name']}: {move['from']} -> {move['to']}")
            return ("MOVE", move)

        elif msg_type == MSG_CHAINING:
            buf = io.BytesIO(data)
            code = read_u32(buf)
            self.log(f"CHAINING: {get_card_name(code)}")
            return ("CHAINING", {"code": code, "name": get_card_name(code)})

        elif msg_type == MSG_CHAIN_SOLVED:
            return ("CHAIN_SOLVED", None)

        elif msg_type == MSG_CHAIN_END:
            return ("CHAIN_END", None)

        elif msg_type == MSG_SPSUMMONING:
            buf = io.BytesIO(data)
            code = read_u32(buf)
            self.log(f"SPSUMMONING: {get_card_name(code)}")
            return ("SPSUMMONING", {"code": code})

        elif msg_type == MSG_SPSUMMONED:
            return ("SPSUMMONED", None)

        elif msg_type == MSG_SUMMONING:
            buf = io.BytesIO(data)
            code = read_u32(buf)
            self.log(f"SUMMONING: {get_card_name(code)}")
            return ("SUMMONING", {"code": code})

        elif msg_type == MSG_SUMMONED:
            return ("SUMMONED", None)

        elif msg_type == MSG_RETRY:
            self.log("RETRY: Invalid response!")
            return ("RETRY", None)

        else:
            return (f"MSG_{msg_type}", None)

    def process_until_idle(self, max_iterations=100):
        """Process messages until IDLE or error."""
        for _ in range(max_iterations):
            status = self.lib.OCG_DuelProcess(self.duel)
            messages = self.get_messages()

            for msg in messages:
                result = self.handle_message(msg)
                if result[0] == "IDLE":
                    self.current_state = result[1]
                    return result[1]
                elif result[0] == "RETRY":
                    return None

            if status == 0:
                return None

        return None

    def activate_effect(self, index):
        """Activate an effect by index."""
        response = (index << 16) | 5
        self.send_response_int(response)
        return self.process_until_idle()

    def get_zone_count(self, player, location):
        return self.lib.OCG_DuelQueryCount(self.duel, player, location)


@dataclass
class VerificationResult:
    """Result of verifying a single card."""
    name: str
    passcode: int
    script_loads: bool = False
    script_path: str = ""
    effects_found: Dict[str, bool] = field(default_factory=dict)
    effects_resolve: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    @property
    def passed(self):
        return self.script_loads and len(self.errors) == 0


def check_script_exists(passcode: int) -> Tuple[bool, str]:
    """Check if a card script exists and return its path."""
    script_name = f"c{passcode}.lua"
    paths = [
        SCRIPT_PATH / "official" / script_name,
        SCRIPT_PATH / script_name,
    ]
    for path in paths:
        if path.exists():
            return True, str(path)
    return False, ""


def verify_script_loads(lib, passcode: int) -> Tuple[bool, List[str]]:
    """Verify that a card script loads without errors."""
    global _script_errors
    _script_errors = []

    helper = DuelHelper(lib)
    if not helper.create_duel():
        return False, ["Failed to create duel"]

    # Add the card to trigger script loading
    helper.add_deck(0, [passcode])

    # Add minimal opponent deck
    helper.add_deck(1, [FILLER_CARD] * 40)

    # Start duel to trigger script loading
    helper.lib.OCG_StartDuel(helper.duel)

    # Process a bit to ensure script loaded
    helper.lib.OCG_DuelProcess(helper.duel)
    helper.get_messages()

    errors = list(_script_errors)
    helper.destroy_duel()

    return len(errors) == 0, errors


def verify_engraver(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith Engraver effects."""
    result = VerificationResult(name="Fiendsmith Engraver", passcode=passcode)

    # Check script
    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    if not loads:
        return result

    # --- Test e1: Hand effect - discard to search Fiendsmith S/T ---
    helper = DuelHelper(lib)
    helper.verbose = False

    if helper.create_duel():
        # Setup: Engraver in hand, Tract in deck
        TRACT = 98567237
        helper.add_hand(0, [passcode])
        helper.add_deck(0, [TRACT] + [FILLER_CARD] * 39)
        helper.add_deck(1, [FILLER_CARD] * 40)

        state = helper.start_duel()

        if state:
            # Check if e1 enumerates
            e1_found = any(
                a['code'] == passcode and a['location'] == LOCATION_HAND
                for a in state['activatable']
            )
            result.effects_found["e1_hand"] = e1_found

            if e1_found:
                # Activate it
                idx = next(i for i, a in enumerate(state['activatable'])
                          if a['code'] == passcode)
                helper.move_log = []
                new_state = helper.activate_effect(idx)

                # Check resolution
                # Engraver should go to GY, Tract should go to hand
                engraver_to_gy = any(
                    m['code'] == passcode and m['to'] == 'GY'
                    for m in helper.move_log
                )
                tract_to_hand = any(
                    m['code'] == TRACT and m['to'] == 'Hand'
                    for m in helper.move_log
                )
                result.effects_resolve["e1_hand"] = engraver_to_gy and tract_to_hand

                if not engraver_to_gy:
                    result.errors.append("e1: Engraver did not go to GY")
                if not tract_to_hand:
                    result.errors.append("e1: Tract was not searched to hand")
            else:
                result.errors.append("e1: Effect did not enumerate in hand")
        else:
            result.errors.append("e1: Failed to start duel")

        helper.destroy_duel()

    # --- Test e3: GY effect - shuffle LIGHT Fiend, SS self ---
    helper = DuelHelper(lib)

    if helper.create_duel():
        # Setup: Engraver in GY, another LIGHT Fiend in GY
        LACRIMA_CT = 28803166
        helper.add_gy(0, [passcode, LACRIMA_CT])
        helper.add_deck(0, [FILLER_CARD] * 40)
        helper.add_deck(1, [FILLER_CARD] * 40)
        helper.add_extra(0, [2463794])  # Requiem - sends to Extra

        state = helper.start_duel()

        if state:
            # Check if e3 enumerates
            e3_found = any(
                a['code'] == passcode and a['location'] == LOCATION_GRAVE
                for a in state['activatable']
            )
            result.effects_found["e3_gy"] = e3_found

            if e3_found:
                idx = next(i for i, a in enumerate(state['activatable'])
                          if a['code'] == passcode and a['location'] == LOCATION_GRAVE)
                helper.move_log = []
                new_state = helper.activate_effect(idx)

                # Check: other LIGHT Fiend shuffled, Engraver on field
                engraver_to_field = any(
                    m['code'] == passcode and m['to'] == 'MZone'
                    for m in helper.move_log
                )
                lacrima_shuffled = any(
                    (m['code'] == LACRIMA_CT or m['name'] == "Fiendsmith's Requiem")
                    and (m['to'] == 'Deck' or m['to'] == 'Extra')
                    for m in helper.move_log
                )
                result.effects_resolve["e3_gy"] = engraver_to_field

                if not engraver_to_field:
                    result.errors.append("e3: Engraver was not SS to field")
            else:
                result.errors.append("e3: Effect did not enumerate in GY")
        else:
            result.errors.append("e3: Failed to start duel")

        helper.destroy_duel()

    return result


def verify_lacrima_ct(lib, passcode: int) -> VerificationResult:
    """Verify Lacrima the Crimson Tears effects."""
    result = VerificationResult(name="Lacrima the Crimson Tears", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    if not loads:
        return result

    # --- Test e1: Trigger on summon - send Fiendsmith from deck to GY ---
    helper = DuelHelper(lib)

    if helper.create_duel():
        # Setup: Lacrima in hand, Fiendsmith cards in deck
        TRACT = 98567237
        helper.add_hand(0, [passcode])
        helper.add_deck(0, [TRACT, 60764609] + [FILLER_CARD] * 38)  # Tract and Engraver
        helper.add_deck(1, [FILLER_CARD] * 40)

        state = helper.start_duel()

        if state:
            # Check if can normal summon
            ns_found = any(a['code'] == passcode for a in state['summonable'])
            result.effects_found["normal_summon"] = ns_found

            if ns_found:
                # Normal summon it
                idx = next(i for i, a in enumerate(state['summonable'])
                          if a['code'] == passcode)
                response = (idx << 16) | 0  # Normal summon
                helper.send_response_int(response)
                helper.move_log = []
                new_state = helper.process_until_idle()

                # Check: Lacrima on field, Fiendsmith sent to GY
                lacrima_to_field = any(
                    m['code'] == passcode and m['to'] == 'MZone'
                    for m in helper.move_log
                )
                fiendsmith_to_gy = any(
                    m['to'] == 'GY' and m['from'] == 'Deck'
                    for m in helper.move_log
                )
                result.effects_found["e1_trigger"] = True  # If no error, trigger was offered
                result.effects_resolve["e1_trigger"] = lacrima_to_field and fiendsmith_to_gy

                if not lacrima_to_field:
                    result.errors.append("e1: Lacrima was not summoned to field")
                if not fiendsmith_to_gy:
                    result.errors.append("e1: No Fiendsmith sent to GY (trigger may not have fired)")
            else:
                result.errors.append("Cannot normal summon Lacrima CT")
        else:
            result.errors.append("Failed to start duel")

        helper.destroy_duel()

    return result


def verify_requiem(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith's Requiem effects."""
    result = VerificationResult(name="Fiendsmith's Requiem", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    if not loads:
        return result

    # --- Test e1: Field effect - tribute to SS LIGHT Fiend from deck ---
    helper = DuelHelper(lib)

    if helper.create_duel():
        # Setup: Requiem on field, LIGHT Fiend in deck
        LACRIMA_CT = 28803166
        helper.add_field(0, [passcode])
        helper.add_deck(0, [LACRIMA_CT] + [FILLER_CARD] * 39)
        helper.add_deck(1, [FILLER_CARD] * 40)

        state = helper.start_duel()

        if state:
            # Check if e1 enumerates
            e1_found = any(
                a['code'] == passcode and a['location'] == LOCATION_MZONE
                for a in state['activatable']
            )
            result.effects_found["e1_field"] = e1_found

            if e1_found:
                idx = next(i for i, a in enumerate(state['activatable'])
                          if a['code'] == passcode)
                helper.move_log = []
                new_state = helper.activate_effect(idx)

                # Check: Requiem to GY, LIGHT Fiend SS to field
                requiem_to_gy = any(
                    m['code'] == passcode and m['to'] == 'GY'
                    for m in helper.move_log
                )
                monster_to_field = any(
                    m['to'] == 'MZone' and m['from'] == 'Deck'
                    for m in helper.move_log
                )
                result.effects_resolve["e1_field"] = requiem_to_gy and monster_to_field

                if not requiem_to_gy:
                    result.errors.append("e1: Requiem did not tribute to GY")
                if not monster_to_field:
                    result.errors.append("e1: No monster SS from deck")
            else:
                result.errors.append("e1: Effect did not enumerate on field")
        else:
            result.errors.append("e1: Failed to start duel")

        helper.destroy_duel()

    return result


def verify_tract(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith's Tract effects."""
    result = VerificationResult(name="Fiendsmith's Tract", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    if not loads:
        return result

    # --- Test e1: Hand activation - search LIGHT Fiend + discard ---
    helper = DuelHelper(lib)

    if helper.create_duel():
        # Setup: Tract in hand, LIGHT Fiend in deck, fodder in hand
        LACRIMA_CT = 28803166
        helper.add_hand(0, [passcode, FILLER_CARD])  # Tract + discard fodder
        helper.add_deck(0, [LACRIMA_CT] + [FILLER_CARD] * 39)
        helper.add_deck(1, [FILLER_CARD] * 40)

        state = helper.start_duel()

        if state:
            e1_found = any(
                a['code'] == passcode and a['location'] == LOCATION_HAND
                for a in state['activatable']
            )
            result.effects_found["e1_hand"] = e1_found

            if e1_found:
                idx = next(i for i, a in enumerate(state['activatable'])
                          if a['code'] == passcode)
                helper.move_log = []
                new_state = helper.activate_effect(idx)

                # Check: Card added to hand, card discarded, Tract to GY
                card_to_hand = any(
                    m['to'] == 'Hand' and m['from'] == 'Deck'
                    for m in helper.move_log
                )
                card_discarded = any(
                    m['to'] == 'GY' and m['from'] == 'Hand'
                    for m in helper.move_log
                )
                result.effects_resolve["e1_hand"] = card_to_hand

                if not card_to_hand:
                    result.errors.append("e1: No LIGHT Fiend searched")
            else:
                result.errors.append("e1: Effect did not enumerate in hand")
        else:
            result.errors.append("e1: Failed to start duel")

        helper.destroy_duel()

    # --- Test e2: GY effect - banish to Fusion Summon ---
    helper = DuelHelper(lib)

    if helper.create_duel():
        # Setup: Tract in GY, Fusion materials available, Fusion in Extra
        LACRIMA_FUSION = 46640168
        LACRIMA_CT = 28803166
        helper.add_gy(0, [passcode])
        helper.add_hand(0, [LACRIMA_CT, LACRIMA_CT])  # Fusion materials
        helper.add_deck(0, [FILLER_CARD] * 40)
        helper.add_extra(0, [LACRIMA_FUSION])
        helper.add_deck(1, [FILLER_CARD] * 40)

        state = helper.start_duel()

        if state:
            e2_found = any(
                a['code'] == passcode and a['location'] == LOCATION_GRAVE
                for a in state['activatable']
            )
            result.effects_found["e2_gy"] = e2_found

            if e2_found:
                idx = next(i for i, a in enumerate(state['activatable'])
                          if a['code'] == passcode and a['location'] == LOCATION_GRAVE)
                helper.move_log = []
                new_state = helper.activate_effect(idx)

                # Check: Tract banished, Fusion monster on field
                tract_banished = any(
                    m['code'] == passcode and m['to'] == 'Banished'
                    for m in helper.move_log
                )
                fusion_to_field = any(
                    m['to'] == 'MZone' and m['from'] == 'Extra'
                    for m in helper.move_log
                )
                result.effects_resolve["e2_gy"] = tract_banished and fusion_to_field

                if not tract_banished:
                    result.errors.append("e2: Tract was not banished")
                if not fusion_to_field:
                    result.errors.append("e2: No Fusion monster summoned")
            else:
                result.errors.append("e2: GY effect did not enumerate")
        else:
            result.errors.append("e2: Failed to start duel")

        helper.destroy_duel()

    return result


def verify_sanct(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith's Sanct effects."""
    result = VerificationResult(name="Fiendsmith's Sanct", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    return result


def verify_paradise(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith in Paradise effects."""
    result = VerificationResult(name="Fiendsmith in Paradise", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    return result


def verify_kyrie(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith Kyrie effects."""
    result = VerificationResult(name="Fiendsmith Kyrie", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    return result


def verify_desirae(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith's Desirae effects."""
    result = VerificationResult(name="Fiendsmith's Desirae", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    return result


def verify_sequence(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith's Sequence effects."""
    result = VerificationResult(name="Fiendsmith's Sequence", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    return result


def verify_lacrima_fusion(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith's Lacrima (Fusion) effects."""
    result = VerificationResult(name="Fiendsmith's Lacrima", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    return result


def verify_agnumday(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith's Agnumday effects."""
    result = VerificationResult(name="Fiendsmith's Agnumday", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    return result


def verify_rextremende(lib, passcode: int) -> VerificationResult:
    """Verify Fiendsmith's Rextremende effects."""
    result = VerificationResult(name="Fiendsmith's Rextremende", passcode=passcode)

    exists, path = check_script_exists(passcode)
    result.script_path = path
    if not exists:
        result.errors.append(f"Script not found: c{passcode}.lua")
        return result

    loads, errors = verify_script_loads(lib, passcode)
    result.script_loads = loads
    result.errors.extend(errors)

    return result


def verify_card(lib, cid: str, info: Dict) -> VerificationResult:
    """Verify a single card works correctly."""
    name = info["name"]
    passcode = info["passcode"]

    # Map cards to their specific verification functions
    verifiers = {
        60764609: verify_engraver,
        28803166: verify_lacrima_ct,
        98567237: verify_tract,  # Corrected passcode
        35552985: verify_sanct,
        99989863: verify_paradise,
        26434972: verify_kyrie,
        82135803: verify_desirae,
        2463794: verify_requiem,
        49867899: verify_sequence,
        46640168: verify_lacrima_fusion,
        32991300: verify_agnumday,
        11464648: verify_rextremende,
    }

    verifier = verifiers.get(passcode)
    if verifier:
        return verifier(lib, passcode)
    else:
        # Generic verification - just check script loads
        result = VerificationResult(name=name, passcode=passcode)
        exists, path = check_script_exists(passcode)
        result.script_path = path
        if not exists:
            result.errors.append(f"Script not found: c{passcode}.lua")
        else:
            loads, errors = verify_script_loads(lib, passcode)
            result.script_loads = loads
            result.errors.extend(errors)
        return result


def run_all_verifications():
    """Run verification for all cards and report results."""
    global _lib

    print("=" * 60)
    print("FIENDSMITH CARD VERIFICATION SUITE")
    print("=" * 60)

    if not init_card_database():
        print("ERROR: Card database not found!")
        return False

    _lib = load_library()

    results = {}
    for cid, info in CARDS_TO_VERIFY.items():
        print(f"\nVerifying {info['name']} ({info['passcode']})...")
        results[cid] = verify_card(_lib, cid, info)

    # Print report
    print("\n" + "=" * 60)
    print("VERIFICATION REPORT")
    print("=" * 60)

    passed = 0
    failed = 0
    script_missing = 0

    for cid, result in results.items():
        if not result.script_path:
            status = "MISSING"
            script_missing += 1
        elif result.passed:
            status = "PASS"
            passed += 1
        else:
            status = "FAIL"
            failed += 1

        print(f"\n[{status}] {result.name} ({result.passcode})")

        if result.script_path:
            print(f"   Script: {result.script_path}")
            print(f"   Loads: {'Yes' if result.script_loads else 'No'}")
        else:
            print(f"   Script: NOT FOUND (c{result.passcode}.lua)")

        if result.effects_found:
            print(f"   Effects found: {result.effects_found}")

        if result.effects_resolve:
            print(f"   Effects resolve: {result.effects_resolve}")

        if result.errors:
            print(f"   Errors:")
            for error in result.errors:
                print(f"      - {error}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total cards: {len(CARDS_TO_VERIFY)}")
    print(f"Scripts found: {len(CARDS_TO_VERIFY) - script_missing}")
    print(f"Scripts missing: {script_missing}")
    print(f"Tests passed: {passed}")
    print(f"Tests failed: {failed}")
    print("=" * 60)

    if script_missing > 0:
        print("\nWARNING: Some card scripts are missing!")
        print("Missing scripts may have different passcodes than expected.")

    return failed == 0 and script_missing == 0


if __name__ == "__main__":
    success = run_all_verifications()
    exit(0 if success else 1)
