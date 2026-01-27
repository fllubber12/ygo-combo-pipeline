#!/usr/bin/env python3
"""
Execute a Fiendsmith combo sequence through the CFFI engine.

Optimal Combo Line:
1. Engraver e1: Discard from hand → Search Tract
2. Tract e1: Activate → Search Lacrima CT + discard
3. Normal Summon Lacrima CT (Level 4, no tribute)
4. (Lacrima CT trigger → Send Fiendsmith from deck to GY)
5. Link Summon Requiem using Lacrima CT
6. Requiem e1: Tribute self → SS Lacrima CT from deck
7. Link Summon Sequence using Lacrima CT
8. Tract e2 (GY): Banish → Fusion Summon Desirae
"""

import io
import sqlite3
import struct
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parents[2] / "src" / "ygo_combo"))

from engine.bindings import (
    ffi, load_library,
    LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA, LOCATION_GRAVE,
    LOCATION_MZONE, LOCATION_SZONE,
    POS_FACEDOWN_DEFENSE, POS_FACEUP_ATTACK,
    TYPE_LINK,
    # Message types
    MSG_RETRY, MSG_HINT, MSG_START, MSG_IDLE, MSG_SELECT_CARD,
    MSG_SELECT_CHAIN, MSG_SELECT_PLACE, MSG_SELECT_POSITION,
    MSG_SELECT_TRIBUTE, MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO,
    MSG_SELECT_OPTION, MSG_SELECT_UNSELECT_CARD,
    MSG_SHUFFLE_DECK, MSG_SHUFFLE_HAND, MSG_NEW_TURN, MSG_NEW_PHASE,
    MSG_MOVE, MSG_SUMMONING, MSG_SUMMONED, MSG_SPSUMMONING, MSG_SPSUMMONED,
    MSG_CHAINING, MSG_CHAINED, MSG_CHAIN_SOLVING, MSG_CHAIN_SOLVED, MSG_CHAIN_END,
    MSG_DRAW, MSG_CONFIRM_CARDS, MSG_UPDATE_DATA, MSG_UPDATE_CARD,
)
from engine.paths import CDB_PATH, get_scripts_path


# Script path
SCRIPT_PATH = get_scripts_path()

# MSG_IDLE alias for backward compatibility
MSG_SELECT_IDLECMD = MSG_IDLE

# Fiendsmith card IDs
# Main Deck Monsters
ENGRAVER = 60764609      # Level 6 LIGHT Fiend - discard to search Fiendsmith S/T
LACRIMA_CT = 28803166    # Level 4 LIGHT Fiend - "Lacrima the Crimson Tears" - NS/SS trigger sends Fiendsmith to GY

# Spells/Traps
TRACT = 98567237         # Spell - search LIGHT Fiend + discard
KYRIE = 26434972         # Trap
SANCT = 35552985         # Continuous Trap

# Extra Deck
REQUIEM = 2463794        # Link-1 - tribute to SS LIGHT Fiend from deck
SEQUENCE = 49867899      # Link-2
AGNUMDAY = 32991300      # Link-3
LACRIMA_FUSION = 46640168  # Fusion - Level 6
DESIRAE = 82135803       # Fusion - Level 9
REXTREMENDE = 11464648   # Fusion - Level 9

# Filler for opponent deck (any card)
FILLER = LACRIMA_CT

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
    if log_type == 0:
        print(f"[OCG ERROR] {msg}")


def read_u8(buf):
    return struct.unpack("<B", buf.read(1))[0]

def read_u16(buf):
    return struct.unpack("<H", buf.read(2))[0]

def read_u32(buf):
    return struct.unpack("<I", buf.read(4))[0]

def read_u64(buf):
    return struct.unpack("<Q", buf.read(8))[0]

def read_i32(buf):
    return struct.unpack("<i", buf.read(4))[0]


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


class ComboExecutor:
    def __init__(self, lib, duel):
        self.lib = lib
        self.duel = duel
        self.action_log = []
        self.current_state = None
        self.step_count = 0
        self.verbose = True

    def log(self, msg):
        if self.verbose:
            print(msg)

    def send_response_int(self, value):
        """Send an integer response."""
        response_bytes = struct.pack("<I", value)
        self.lib.OCG_DuelSetResponse(self.duel, response_bytes, len(response_bytes))

    def send_response_bytes(self, data):
        """Send a byte buffer response."""
        self.lib.OCG_DuelSetResponse(self.duel, data, len(data))

    def send_card_selection(self, indices):
        """Send card selection response (type=0 format)."""
        # Format: type(i32) + count(u32) + indices(u32...)
        data = struct.pack("<iI", 0, len(indices))
        for idx in indices:
            data += struct.pack("<I", idx)
        self.send_response_bytes(data)

    def get_messages(self):
        """Get all pending messages."""
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
        """Parse MSG_SELECT_IDLECMD (MSG_IDLE)."""
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

    def parse_select_card(self, data):
        """Parse MSG_SELECT_CARD."""
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
            cards.append({
                "code": code, "name": get_card_name(code),
                "controller": con, "location": location_name(loc),
                "sequence": seq, "position": pos
            })

        return {"player": player, "cancelable": bool(cancelable),
                "min": min_cards, "max": max_cards, "cards": cards}

    def parse_select_chain(self, data):
        """Parse MSG_SELECT_CHAIN."""
        buf = io.BytesIO(data)
        player = read_u8(buf)
        count = read_u8(buf)
        specount = read_u8(buf)
        forced = read_u8(buf)
        hint0 = read_u32(buf)
        hint1 = read_u32(buf)

        chains = []
        for _ in range(count):
            flag = read_u8(buf)
            code = read_u32(buf)
            loc = read_u32(buf)
            desc = read_u64(buf)
            client_mode = read_u8(buf)
            chains.append({
                "code": code, "name": get_card_name(code),
                "desc": desc, "flag": flag
            })

        return {"player": player, "count": count, "forced": bool(forced), "chains": chains}

    def parse_select_tribute(self, data):
        """Parse MSG_SELECT_TRIBUTE."""
        buf = io.BytesIO(data)
        player = read_u8(buf)
        cancelable = read_u8(buf)
        min_tributes = read_u32(buf)
        max_tributes = read_u32(buf)
        count = read_u32(buf)

        cards = []
        for _ in range(count):
            code = read_u32(buf)
            con = read_u8(buf)
            loc = read_u8(buf)
            seq = read_u32(buf)
            release_param = read_u8(buf)
            cards.append({
                "code": code, "name": get_card_name(code),
                "controller": con, "location": location_name(loc),
                "sequence": seq, "release_param": release_param
            })

        return {"player": player, "cancelable": bool(cancelable),
                "min": min_tributes, "max": max_tributes, "cards": cards}

    def parse_select_position(self, data):
        """Parse MSG_SELECT_POSITION."""
        buf = io.BytesIO(data)
        player = read_u8(buf)
        code = read_u32(buf)
        positions = read_u8(buf)
        return {"player": player, "code": code, "name": get_card_name(code), "positions": positions}

    def parse_select_place(self, data):
        """Parse MSG_SELECT_PLACE."""
        buf = io.BytesIO(data)
        player = read_u8(buf)
        count = read_u8(buf)
        flag = read_u32(buf)
        return {"player": player, "count": count, "flag": flag}

    def parse_move(self, data):
        """Parse MSG_MOVE."""
        buf = io.BytesIO(data)
        code = read_u32(buf)
        prev_loc = read_u32(buf)
        curr_loc = read_u32(buf)
        reason = read_u32(buf)

        prev_con = prev_loc & 0xFF
        prev_location = (prev_loc >> 8) & 0xFF
        prev_seq = (prev_loc >> 16) & 0xFFFF

        curr_con = curr_loc & 0xFF
        curr_location = (curr_loc >> 8) & 0xFF
        curr_seq = (curr_loc >> 16) & 0xFFFF

        return {
            "code": code, "name": get_card_name(code),
            "from": {"controller": prev_con, "location": location_name(prev_location), "seq": prev_seq},
            "to": {"controller": curr_con, "location": location_name(curr_location), "seq": curr_seq},
        }

    def handle_message(self, msg, auto_select_fn=None):
        """Handle a single message, returning response if needed."""
        msg_type = msg["type"]
        data = msg["data"]

        if msg_type == MSG_SELECT_IDLECMD:
            return ("IDLE", self.parse_idle(data))

        elif msg_type == MSG_SELECT_CARD:
            parsed = self.parse_select_card(data)
            self.log(f"  SELECT_CARD: Choose {parsed['min']}-{parsed['max']} from {len(parsed['cards'])} cards:")
            for i, c in enumerate(parsed['cards']):
                self.log(f"    [{i}] {c['name']} ({c['location']})")

            if auto_select_fn:
                selection = auto_select_fn(parsed)
            else:
                selection = list(range(parsed['min']))  # Default: select first N

            self.log(f"  -> Selecting indices: {selection}")
            self.send_card_selection(selection)
            return ("SELECT_CARD", parsed)

        elif msg_type == MSG_SELECT_UNSELECT_CARD:
            # Material selection for Link/Synchro summons
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
                select_cards.append({
                    "code": code, "name": get_card_name(code),
                    "controller": con, "location": location_name(loc),
                    "sequence": seq, "position": pos
                })

            unselect_count = read_u32(buf)
            unselect_cards = []
            for _ in range(unselect_count):
                code = read_u32(buf)
                con = read_u8(buf)
                loc = read_u8(buf)
                seq = read_u32(buf)
                pos = read_u32(buf)
                unselect_cards.append({
                    "code": code, "name": get_card_name(code),
                    "controller": con, "location": location_name(loc),
                    "sequence": seq, "position": pos
                })

            self.log(f"  SELECT_UNSELECT_CARD: Select materials (min={min_cards}, max={max_cards})")
            self.log(f"    Selectable ({select_count}): {[c['name'] for c in select_cards]}")
            self.log(f"    Unselectable ({unselect_count}): {[c['name'] for c in unselect_cards]}")

            # If we can finish (have enough materials selected), finish
            if finishable and unselect_count > 0:
                self.log(f"  -> Finishing material selection")
                # Response: -1 to finish
                self.send_response_int(0xFFFFFFFF)
            elif select_count > 0:
                # Select first available card as material
                self.log(f"  -> Selecting first material: {select_cards[0]['name']}")
                # Response format: [1, index] - first int32=1 to select, second int32=index
                response = struct.pack("<ii", 1, 0)  # select, index 0
                self.send_response_bytes(response)
            else:
                # No cards to select, try to finish or cancel
                self.log(f"  -> No materials to select, finishing")
                self.send_response_int(0xFFFFFFFF)

            return ("SELECT_UNSELECT_CARD", {
                "player": player, "finishable": finishable, "cancelable": cancelable,
                "min": min_cards, "max": max_cards,
                "select_cards": select_cards, "unselect_cards": unselect_cards
            })

        elif msg_type == MSG_SELECT_CHAIN:
            parsed = self.parse_select_chain(data)
            if parsed['count'] > 0:
                self.log(f"  SELECT_CHAIN: {parsed['count']} optional chain(s) available")
                for i, c in enumerate(parsed['chains']):
                    self.log(f"    [{i}] {c['name']}")

                # Accept trigger effects from our combo cards
                for i, c in enumerate(parsed['chains']):
                    if any(name in c['name'] for name in ["Lacrima", "Engraver", "Requiem", "Sequence", "Tract"]):
                        self.log(f"  -> Accepting chain: {c['name']} (index {i})")
                        self.send_response_int(i)
                        return ("SELECT_CHAIN", parsed)

            # Decline optional chains by default
            self.log(f"  -> Declining chain")
            self.send_response_int(0xFFFFFFFF)  # -1 as unsigned
            return ("SELECT_CHAIN", parsed)

        elif msg_type == MSG_SELECT_TRIBUTE:
            parsed = self.parse_select_tribute(data)
            self.log(f"  SELECT_TRIBUTE: Choose {parsed['min']}-{parsed['max']} tributes:")
            for i, c in enumerate(parsed['cards']):
                self.log(f"    [{i}] {c['name']} (release_param={c['release_param']})")

            # Select minimum required tributes
            selection = list(range(parsed['min']))
            self.log(f"  -> Selecting tributes: {selection}")
            self.send_card_selection(selection)
            return ("SELECT_TRIBUTE", parsed)

        elif msg_type == MSG_SELECT_POSITION:
            parsed = self.parse_select_position(data)
            self.log(f"  SELECT_POSITION: {parsed['name']}")
            # Default to attack position (0x1)
            self.send_response_int(0x1)
            return ("SELECT_POSITION", parsed)

        elif msg_type == MSG_SELECT_PLACE:
            parsed = self.parse_select_place(data)
            self.log(f"  SELECT_PLACE: Select {parsed['count']} zone(s), flag=0x{parsed['flag']:08x}")
            # Flag bits: 0-4=MZONE(our), 8-12=SZONE(our), 16-20=MZONE(opp), 24-28=SZONE(opp)
            flag = parsed['flag']
            # Find first available S/T zone (bits 8-12)
            player = 0
            location = 0x08  # LOCATION_SZONE
            sequence = 0
            for i in range(5):
                if not (flag & (1 << (8 + i))):  # S/T zone available if bit is 0
                    sequence = i
                    break
            else:
                # Try monster zone if no S/T zone (bits 0-4)
                location = 0x04  # LOCATION_MZONE
                for i in range(5):
                    if not (flag & (1 << i)):
                        sequence = i
                        break
            self.log(f"  -> Selecting zone: player={player}, loc=0x{location:02x}, seq={sequence}")
            # Response format: 3 bytes (player, location, sequence)
            response = struct.pack("<BBB", player, location, sequence)
            self.send_response_bytes(response)
            return ("SELECT_PLACE", parsed)

        elif msg_type == MSG_SELECT_YESNO:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            desc = read_u64(buf)
            self.log(f"  SELECT_YESNO: desc={desc}")
            self.send_response_int(1)  # Yes
            return ("SELECT_YESNO", {"player": player, "desc": desc})

        elif msg_type == MSG_SELECT_EFFECTYN:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            # Skip location info
            self.log(f"  SELECT_EFFECTYN: Activate effect?")
            self.send_response_int(1)  # Yes
            return ("SELECT_EFFECTYN", {"player": player})

        elif msg_type == MSG_SELECT_OPTION:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            count = read_u8(buf)
            options = []
            for _ in range(count):
                opt = read_u64(buf)
                options.append(opt)
            self.log(f"  SELECT_OPTION: Choose from {count} options (player={player})")
            for i, opt in enumerate(options):
                self.log(f"    [{i}] Option {opt}")
            # Default to second option (Special Summon for aux.ToHandOrElse)
            # Option 0 is usually "Add to hand", Option 1 is "Special Summon"
            choice = 1 if count > 1 else 0
            self.log(f"  -> Selecting option {choice}")
            self.send_response_int(choice)
            return ("SELECT_OPTION", {"player": player, "options": options})

        elif msg_type == MSG_MOVE:
            parsed = self.parse_move(data)
            self.log(f"  MOVE: {parsed['name']}: {parsed['from']['location']} -> {parsed['to']['location']}")
            self.action_log.append(parsed)
            return ("MOVE", parsed)

        elif msg_type == MSG_CHAINING:
            buf = io.BytesIO(data)
            code = read_u32(buf)
            self.log(f"  CHAINING: {get_card_name(code)}")
            return ("CHAINING", {"code": code, "name": get_card_name(code)})

        elif msg_type == MSG_CHAIN_SOLVED:
            self.log(f"  CHAIN_SOLVED")
            return ("CHAIN_SOLVED", None)

        elif msg_type == MSG_CHAIN_END:
            self.log(f"  CHAIN_END")
            return ("CHAIN_END", None)

        elif msg_type == MSG_SHUFFLE_DECK:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            self.log(f"  SHUFFLE_DECK: Player {player}")
            return ("SHUFFLE_DECK", {"player": player})

        elif msg_type == MSG_SHUFFLE_HAND:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            self.log(f"  SHUFFLE_HAND: Player {player}")
            return ("SHUFFLE_HAND", {"player": player})

        elif msg_type == MSG_SPSUMMONING:
            buf = io.BytesIO(data)
            code = read_u32(buf)
            self.log(f"  SPSUMMONING: {get_card_name(code)}")
            return ("SPSUMMONING", {"code": code, "name": get_card_name(code)})

        elif msg_type == MSG_SPSUMMONED:
            self.log(f"  SPSUMMONED")
            return ("SPSUMMONED", None)

        elif msg_type == MSG_SUMMONING:
            buf = io.BytesIO(data)
            code = read_u32(buf)
            self.log(f"  SUMMONING: {get_card_name(code)}")
            return ("SUMMONING", {"code": code, "name": get_card_name(code)})

        elif msg_type == MSG_SUMMONED:
            self.log(f"  SUMMONED")
            return ("SUMMONED", None)

        elif msg_type == MSG_CONFIRM_CARDS:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            count = read_u32(buf)
            cards = []
            for _ in range(count):
                code = read_u32(buf)
                cards.append(get_card_name(code))
            self.log(f"  CONFIRM_CARDS: {cards}")
            return ("CONFIRM_CARDS", {"player": player, "cards": cards})

        elif msg_type == MSG_HINT:
            return ("HINT", None)

        elif msg_type == MSG_NEW_PHASE:
            buf = io.BytesIO(data)
            phase = read_u16(buf)
            phase_names = {0x01: "Draw", 0x02: "Standby", 0x04: "Main1",
                           0x08: "Battle", 0x10: "Main2", 0x20: "End"}
            self.log(f"  NEW_PHASE: {phase_names.get(phase, phase)}")
            return ("NEW_PHASE", {"phase": phase})

        elif msg_type == MSG_NEW_TURN:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            self.log(f"  NEW_TURN: Player {player}")
            return ("NEW_TURN", {"player": player})

        elif msg_type == MSG_DRAW:
            buf = io.BytesIO(data)
            player = read_u8(buf)
            count = read_u32(buf)
            self.log(f"  DRAW: Player {player} drew {count}")
            return ("DRAW", {"player": player, "count": count})

        elif msg_type == MSG_RETRY:
            self.log(f"  RETRY: Invalid response!")
            return ("RETRY", None)

        else:
            return (f"MSG_{msg_type}", None)

    def process_until_idle(self, auto_select_fn=None):
        """Process messages until we get back to IDLE state."""
        max_iterations = 100
        for _ in range(max_iterations):
            status = self.lib.OCG_DuelProcess(self.duel)
            messages = self.get_messages()

            for msg in messages:
                result = self.handle_message(msg, auto_select_fn)
                if result[0] == "IDLE":
                    self.current_state = result[1]
                    return result[1]
                elif result[0] == "RETRY":
                    return None  # Error

            if status == 0:  # Duel ended
                return None

        return None

    def print_legal_actions(self, state=None):
        """Print current legal actions."""
        if state is None:
            state = self.current_state
        if state is None:
            print("  (no state available)")
            return

        if state['activatable']:
            print(f"  Activatable ({len(state['activatable'])}):")
            for i, a in enumerate(state['activatable']):
                print(f"    [{i}] {a['name']} ({location_name(a['location'])})")

        if state['spsummon']:
            print(f"  Special Summonable ({len(state['spsummon'])}):")
            for i, s in enumerate(state['spsummon']):
                print(f"    [{i}] {s['name']} ({location_name(s['location'])})")

        if state['summonable']:
            print(f"  Normal Summonable ({len(state['summonable'])}):")
            for i, s in enumerate(state['summonable']):
                print(f"    [{i}] {s['name']} ({location_name(s['location'])})")

        if state['sset']:
            print(f"  Spell/Trap Settable ({len(state['sset'])}):")
            for i, s in enumerate(state['sset']):
                print(f"    [{i}] {s['name']}")

    def activate_effect(self, card_name=None, index=None, auto_select_fn=None):
        """Activate an effect. Returns new IDLE state or None on error."""
        if self.current_state is None:
            return None

        # Find the effect to activate
        if index is not None:
            effect_idx = index
        elif card_name:
            effect_idx = None
            for i, a in enumerate(self.current_state['activatable']):
                if card_name.lower() in a['name'].lower():
                    effect_idx = i
                    break
            if effect_idx is None:
                self.log(f"  ERROR: No activatable effect for '{card_name}'")
                return None
        else:
            effect_idx = 0

        # Response format: (index << 16) | 5
        response = (effect_idx << 16) | 5
        self.log(f"  Sending activation response: {effect_idx} (type 5)")
        self.send_response_int(response)

        return self.process_until_idle(auto_select_fn)

    def special_summon(self, card_name=None, index=None, auto_select_fn=None):
        """Special summon a card. Returns new IDLE state or None on error."""
        if self.current_state is None:
            return None

        if index is not None:
            ss_idx = index
        elif card_name:
            ss_idx = None
            for i, s in enumerate(self.current_state['spsummon']):
                if card_name.lower() in s['name'].lower():
                    ss_idx = i
                    break
            if ss_idx is None:
                self.log(f"  ERROR: Cannot special summon '{card_name}'")
                return None
        else:
            ss_idx = 0

        # Response format: (index << 16) | type
        # Type mapping (validation in playerop.cpp):
        #   0=summon, 1=spsummon, 2=repos, 3=mset, 4=sset, 5=activate
        response = (ss_idx << 16) | 1  # Type 1 for spsummon
        self.log(f"  Sending special summon response: idx={ss_idx}, raw={response} (type 1)")
        self.send_response_int(response)

        return self.process_until_idle(auto_select_fn)

    def normal_summon(self, card_name=None, index=None, auto_select_fn=None):
        """Normal summon a card. Returns new IDLE state or None on error."""
        if self.current_state is None:
            return None

        if index is not None:
            ns_idx = index
        elif card_name:
            ns_idx = None
            for i, s in enumerate(self.current_state['summonable']):
                if card_name.lower() in s['name'].lower():
                    ns_idx = i
                    break
            if ns_idx is None:
                self.log(f"  ERROR: Cannot normal summon '{card_name}'")
                return None
        else:
            ns_idx = 0

        # Response format: (index << 16) | 0
        response = (ns_idx << 16) | 0
        self.log(f"  Sending normal summon response: {ns_idx} (type 0)")
        self.send_response_int(response)

        return self.process_until_idle(auto_select_fn)

    def end_phase(self, auto_select_fn=None):
        """Go to end phase."""
        if self.current_state is None:
            return None

        # Response format: type 7 = to end phase
        response = 7
        self.log(f"  Sending end phase response (type 7)")
        self.send_response_int(response)

        return self.process_until_idle(auto_select_fn)

    def get_zone_count(self, player, location):
        """Query number of cards in a location."""
        return self.lib.OCG_DuelQueryCount(self.duel, player, location)

    def print_game_state(self):
        """Print current game state."""
        hand = self.get_zone_count(0, LOCATION_HAND)
        field = self.get_zone_count(0, LOCATION_MZONE)
        gy = self.get_zone_count(0, LOCATION_GRAVE)
        extra = self.get_zone_count(0, LOCATION_EXTRA)
        deck = self.get_zone_count(0, LOCATION_DECK)

        print(f"\n  === GAME STATE ===")
        print(f"  Hand: {hand} | Field: {field} | GY: {gy} | Extra: {extra} | Deck: {deck}")


def create_duel():
    """Create a duel with Fiendsmith deck."""
    global _lib

    _lib = load_library()

    options = ffi.new("OCG_DuelOptions*")
    options.seed[0] = 42
    options.seed[1] = 1337
    options.seed[2] = 9999
    options.seed[3] = 12345
    options.flags = (5 << 16)

    options.team1.startingLP = 8000
    options.team1.startingDrawCount = 0  # We'll set up hand manually
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
        raise RuntimeError(f"Failed to create duel: {result}")

    duel = duel_ptr[0]
    preload_utility_scripts(_lib, duel)

    # Set up optimal starting hand:
    # - 1x Engraver (to start the combo with discard -> search Tract)
    # - 3x Lacrima CT (backup copies, or could be discarded by Tract)
    hand_cards = [ENGRAVER, LACRIMA_CT, LACRIMA_CT, LACRIMA_CT]

    for i, code in enumerate(hand_cards):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_HAND
        card_info.seq = i
        card_info.pos = POS_FACEUP_ATTACK
        _lib.OCG_DuelNewCard(duel, card_info)

    # Deck: Fiendsmith cards for searching
    # - 3x Tract (searchable by Engraver)
    # - 3x Lacrima CT (searchable by Tract - LIGHT Fiend that triggers on summon)
    # - 3x Engraver (searchable by Tract - LIGHT Fiend)
    # - 2x Kyrie (trap)
    # - Padding with generic LIGHT Fiends for 40 card minimum
    deck_cards = [
        TRACT, TRACT, TRACT,           # Fiendsmith Spell
        LACRIMA_CT, LACRIMA_CT, LACRIMA_CT,  # Main deck Fiendsmith (Level 4)
        ENGRAVER, ENGRAVER, ENGRAVER,  # Main deck Fiendsmith (Level 6)
        KYRIE, KYRIE,                  # Fiendsmith Trap
    ]
    # Pad to 40 cards with copies of Lacrima CT (or could use any card)
    while len(deck_cards) < 40:
        deck_cards.append(LACRIMA_CT)

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

    # Extra deck - Link and Fusion monsters
    extra_cards = [
        REQUIEM, REQUIEM,           # Link-1 (tribute to SS LIGHT Fiend)
        SEQUENCE, SEQUENCE,         # Link-2
        AGNUMDAY,                   # Link-3
        LACRIMA_FUSION,             # Fusion Level 6
        DESIRAE,                    # Fusion Level 9
        REXTREMENDE,                # Fusion Level 9
    ]
    for i, code in enumerate(extra_cards):
        card_info = ffi.new("OCG_NewCardInfo*")
        card_info.team = 0
        card_info.duelist = 0
        card_info.code = code
        card_info.con = 0
        card_info.loc = LOCATION_EXTRA
        card_info.seq = i
        card_info.pos = POS_FACEDOWN_DEFENSE
        _lib.OCG_DuelNewCard(duel, card_info)

    # Opponent deck
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

    return _lib, duel


def run_combo():
    """Execute the Fiendsmith combo."""
    print("\n" + "=" * 70)
    print("FIENDSMITH COMBO EXECUTION")
    print("=" * 70)

    if not init_card_database():
        print("ERROR: Card database not found!")
        return False

    lib, duel = create_duel()
    executor = ComboExecutor(lib, duel)

    print("\n[SETUP]")
    print("  Starting hand: 1x Engraver, 3x Lacrima CT")
    print("  Deck contains: 3x Tract, 3x Lacrima CT, 3x Engraver, 2x Kyrie")
    print("  Extra deck: 2x Requiem, 2x Sequence, Agnumday, Lacrima Fusion, Desirae, Rextremende")

    # Start duel
    lib.OCG_StartDuel(duel)

    # Process to first IDLE
    print("\n[STARTING DUEL]")
    state = executor.process_until_idle()
    if state is None:
        print("ERROR: Failed to reach initial IDLE")
        return False

    executor.print_game_state()
    print("\n[AVAILABLE ACTIONS]")
    executor.print_legal_actions()

    # STEP 1: Activate Engraver's discard effect
    print("\n" + "-" * 50)
    print("[STEP 1] Activate Engraver - Discard to search Tract")
    print("-" * 50)

    def select_tract(select_data):
        """Select Tract from search options."""
        for i, c in enumerate(select_data['cards']):
            if "Tract" in c['name']:
                return [i]
        return [0]

    state = executor.activate_effect("Engraver", auto_select_fn=select_tract)
    if state is None:
        print("ERROR: Failed after Engraver activation")
        lib.OCG_DestroyDuel(duel)
        return False

    executor.print_game_state()
    print("\n[AVAILABLE ACTIONS]")
    executor.print_legal_actions()

    # STEP 2: Activate Tract - search Lacrima CT (LIGHT Fiend) + discard
    print("\n" + "-" * 50)
    print("[STEP 2] Activate Tract - Search Lacrima CT + discard")
    print("-" * 50)

    def select_lacrima_ct(select_data):
        """Select Lacrima CT from search options."""
        for i, c in enumerate(select_data['cards']):
            if "Lacrima" in c['name'] and "Fusion" not in c['name']:
                return [i]
        # Fallback to first LIGHT Fiend
        return [0]

    # Check if Tract is activatable
    tract_available = any("Tract" in a['name'] for a in state['activatable'])
    if tract_available:
        state = executor.activate_effect("Tract", auto_select_fn=select_lacrima_ct)
        if state is None:
            print("ERROR: Failed after Tract activation")
            lib.OCG_DestroyDuel(duel)
            return False

        executor.print_game_state()
        print("\n[AVAILABLE ACTIONS]")
        executor.print_legal_actions()
    else:
        print("  Tract not yet activatable (may need to be set first)")
        # Set Tract instead
        if state['sset']:
            for i, s in enumerate(state['sset']):
                if "Tract" in s['name']:
                    print(f"  Setting Tract instead...")
                    response = (i << 16) | 4  # type 4 = sset
                    executor.send_response_int(response)
                    state = executor.process_until_idle()
                    break

    # STEP 3: Normal Summon Lacrima CT (Level 4 - no tribute needed)
    print("\n" + "-" * 50)
    print("[STEP 3] Normal Summon Lacrima CT")
    print("-" * 50)

    if state and state['summonable']:
        # Look for Lacrima CT (Level 4, no tribute needed)
        summoned = False
        for i, s in enumerate(state['summonable']):
            print(f"  Can summon: {s['name']}")
            if "Lacrima" in s['name']:
                state = executor.normal_summon("Lacrima")
                summoned = True
                print(f"  -> Normal Summoned Lacrima CT!")
                break

        if not summoned:
            # Fallback: summon first available
            print("  Lacrima CT not available, summoning first option...")
            state = executor.normal_summon(index=0)
            summoned = True

        if summoned and state:
            executor.print_game_state()
            print("\n[AVAILABLE ACTIONS]")
            executor.print_legal_actions()
    else:
        print("  No monsters to normal summon")

    # Note: After Normal Summon, Lacrima CT's trigger effect may activate automatically
    # (handled via MSG_SELECT_CHAIN - we decline chains by default, but the mandatory
    # trigger processing happens during process_until_idle)

    # STEP 4: Link Summon Requiem using Lacrima CT
    print("\n" + "-" * 50)
    print("[STEP 4] Link Summon Requiem using Lacrima CT")
    print("-" * 50)

    requiem_available = False
    if state and state['spsummon']:
        for i, s in enumerate(state['spsummon']):
            if "Requiem" in s['name']:
                print(f"  Requiem available for Link Summon!")
                state = executor.special_summon("Requiem")
                requiem_available = True
                break

    if requiem_available and state:
        executor.print_game_state()
        print("\n[AVAILABLE ACTIONS]")
        executor.print_legal_actions()

        # STEP 5: Activate Requiem's effect - tribute to SS LIGHT Fiend from deck
        print("\n" + "-" * 50)
        print("[STEP 5] Activate Requiem - Tribute to SS Lacrima CT from deck")
        print("-" * 50)

        def select_lacrima_from_deck(select_data):
            """Select Lacrima CT from deck for Requiem's SS effect."""
            for i, c in enumerate(select_data['cards']):
                if "Lacrima" in c['name'] and "Deck" in str(c.get('location', '')):
                    return [i]
            # First LIGHT Fiend
            return [0]

        requiem_effect_available = False
        if state['activatable']:
            for i, a in enumerate(state['activatable']):
                if "Requiem" in a['name']:
                    print(f"  Activating Requiem's effect...")
                    state = executor.activate_effect("Requiem", auto_select_fn=select_lacrima_from_deck)
                    requiem_effect_available = True
                    break

        if requiem_effect_available and state:
            executor.print_game_state()
            print("\n[AVAILABLE ACTIONS]")
            executor.print_legal_actions()

            # STEP 5b: Activate Engraver GY effect to SS itself (need 2 materials for Sequence)
            print("\n" + "-" * 50)
            print("[STEP 5b] Activate Engraver GY - SS itself (need 2nd material for Sequence)")
            print("-" * 50)

            engraver_gy_available = False
            if state['activatable']:
                for i, a in enumerate(state['activatable']):
                    if "Engraver" in a['name'] and a['location'] == LOCATION_GRAVE:
                        print(f"  Activating Engraver's GY effect...")
                        state = executor.activate_effect(index=i)
                        engraver_gy_available = True
                        break

            if engraver_gy_available and state:
                executor.print_game_state()
                print("\n[AVAILABLE ACTIONS]")
                executor.print_legal_actions()

            # STEP 6: Link Summon Sequence using Lacrima CT + Engraver
            print("\n" + "-" * 50)
            print("[STEP 6] Link Summon Sequence (2 materials: Lacrima CT + Engraver)")
            print("-" * 50)

            sequence_available = False
            if state['spsummon']:
                for i, s in enumerate(state['spsummon']):
                    if "Sequence" in s['name']:
                        print(f"  Sequence available for Link Summon!")
                        state = executor.special_summon("Sequence")
                        sequence_available = True
                        break

            if sequence_available and state:
                executor.print_game_state()
                print("\n[AVAILABLE ACTIONS]")
                executor.print_legal_actions()

                # STEP 7: Continue toward Desirae
                # Sequence can be used to Link Summon Agnumday (Link-3) or as Fusion material
                print("\n" + "-" * 50)
                print("[STEP 7] Continue combo toward Desirae")
                print("-" * 50)

                # Check if we can activate GY effects or continue combo
                # Look for Tract's GY effect (Fusion Summon Fiendsmith Fusion)
                print("  Checking available effects...")
                if state['activatable']:
                    for i, a in enumerate(state['activatable']):
                        print(f"  Available effect: {a['name']} ({location_name(a['location'])})")

                tract_gy_effect = False
                if state['activatable']:
                    for i, a in enumerate(state['activatable']):
                        if "Tract" in a['name'] and a['location'] == LOCATION_GRAVE:
                            print(f"\n  Found Tract GY effect - can Fusion Summon!")
                            print(f"  Materials needed: Lacrima Fusion = 2 LIGHT Fiends")
                            print(f"  Hand should have: 2x Lacrima CT")
                            # Activate Tract GY for Fusion Summon
                            state = executor.activate_effect(index=i)
                            tract_gy_effect = True
                            break

                if tract_gy_effect and state:
                    executor.print_game_state()
                    print("\n[AVAILABLE ACTIONS]")
                    executor.print_legal_actions()

                    # Check for successful Fusion Summon
                    fusion_summoned = any(
                        ("Lacrima" in move['name'] or "Desirae" in move['name'])
                        and move.get('to', {}).get('location') == 'MZone'
                        for move in executor.action_log
                    )
                    if fusion_summoned:
                        print("\n  *** FUSION MONSTER SUCCESSFULLY SUMMONED! ***")

                        # Check for Lacrima Fusion trigger effect
                        print("\n  Checking for Lacrima Fusion trigger...")
                        if state and state['activatable']:
                            for i, a in enumerate(state['activatable']):
                                if "Lacrima" in a['name']:
                                    print(f"    Found: {a['name']} - can recover LIGHT Fiend from GY!")
                else:
                    # Check for other combo extensions
                    print("  Checking for other combo options...")
                    if state and state['spsummon']:
                        print(f"  Special summon options: {[s['name'] for s in state['spsummon']]}")
                    if state and state['activatable']:
                        print(f"  Effect options: {[a['name'] for a in state['activatable']]}")
            else:
                print("  Sequence not available for Link Summon")
        else:
            print("  Requiem effect not available")
    else:
        print("  Requiem not available for Link Summon")
        print("  (Need a LIGHT Fiend on field)")

    # Final state
    print("\n" + "=" * 70)
    print("COMBO SEQUENCE COMPLETE")
    print("=" * 70)
    executor.print_game_state()

    print(f"\nTotal card movements logged: {len(executor.action_log)}")
    print("\nMove log:")
    for move in executor.action_log:
        print(f"  {move['name']}: {move['from']['location']} -> {move['to']['location']}")

    lib.OCG_DestroyDuel(duel)
    return True


if __name__ == "__main__":
    success = run_combo()
    exit(0 if success else 1)
