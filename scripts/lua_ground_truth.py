#!/usr/bin/env python3
"""
Lua Ground Truth Verification

Loads official YGOPro card scripts and compares their behavior
to our Python implementations.

This creates a minimal YGOPro API environment sufficient to:
1. Load card scripts
2. Execute initial_effect() to register effects
3. Call condition/cost/target functions with chk==0 to test if effects can activate
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import argparse
import json
import os
import re
import sys

from lupa import LuaRuntime

LUA_DIR_ENV = "YGOPRO_SCRIPT_DIR"

# Passcode to CID mapping (from db.ygoprodeck.com)
PASSCODE_TO_CID = {
    "60764609": "20196",   # Fiendsmith Engraver
    "98567237": "20240",   # Fiendsmith's Tract
    "2463794": "20225",    # Fiendsmith's Requiem
    "82135803": "20215",   # Fiendsmith's Desirae
    "46640168": "20214",   # Fiendsmith's Lacrima
    "49867899": "20238",   # Fiendsmith's Sequence
    "32991300": "20521",   # Fiendsmith's Agnumday
    "11464648": "20774",   # Fiendsmith's Rextremende
    "35552985": "20241",   # Fiendsmith's Sanct
    "99989863": "20251",   # Fiendsmith in Paradise
    "26434972": "20816",   # Fiendsmith Kyrie
    "28803166": "20490",   # Lacrima the Crimson Tears
}

CID_TO_PASSCODE = {v: k for k, v in PASSCODE_TO_CID.items()}

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

ATTRIBUTE_BITS = {
    "EARTH": 0x01,
    "WATER": 0x02,
    "FIRE": 0x04,
    "WIND": 0x08,
    "LIGHT": 0x10,
    "DARK": 0x20,
    "DIVINE": 0x40,
}

RACE_BITS = {
    "WARRIOR": 0x1,
    "SPELLCASTER": 0x2,
    "FAIRY": 0x4,
    "FIEND": 0x8,
    "ZOMBIE": 0x10,
    "MACHINE": 0x20,
    "AQUA": 0x40,
    "PYRO": 0x80,
    "ROCK": 0x100,
    "WINDBEAST": 0x200,
    "PLANT": 0x400,
    "INSECT": 0x800,
    "THUNDER": 0x1000,
    "DRAGON": 0x2000,
    "BEAST": 0x4000,
    "BEASTWARRIOR": 0x8000,
    "DINOSAUR": 0x10000,
    "FISH": 0x20000,
    "SEASERPENT": 0x40000,
    "REPTILE": 0x80000,
    "PSYCHIC": 0x100000,
    "DIVINE": 0x200000,
    "CREATORGOD": 0x400000,
    "WYRM": 0x800000,
    "CYBERSE": 0x1000000,
    "ILLUSION": 0x2000000,
}

TYPE_BITS = {
    "MONSTER": 0x1,
    "SPELL": 0x2,
    "TRAP": 0x4,
    "EFFECT": 0x20,
    "FUSION": 0x40,
    "RITUAL": 0x80,
    "SYNCHRO": 0x2000,
    "XYZ": 0x800000,
    "LINK": 0x4000000,
    "EQUIP": 0x40000,
}


@dataclass
class CardState:
    """Represents a card's state for Lua queries."""
    code: int  # passcode
    cid: str
    name: str
    location: int  # bitmask
    position: int = 0x1  # POS_FACEUP_ATTACK
    race: int = 0
    attribute: int = 0
    level: int = 0
    rank: int = 0
    link: int = 0
    card_type: int = 0x1  # TYPE_MONSTER
    setcode: int = 0
    controller: int = 0
    owner: int = 0
    equip_target: Optional['CardState'] = None
    equipped_cards: list = field(default_factory=list)
    materials: list = field(default_factory=list)
    counters: dict = field(default_factory=dict)


@dataclass
class GameState:
    """Game state that can be queried by Lua scripts."""
    turn_player: int = 0
    phase: int = 0x04  # PHASE_MAIN1

    # Cards by location (player 0)
    hand: list = field(default_factory=list)
    deck: list = field(default_factory=list)
    gy: list = field(default_factory=list)
    banished: list = field(default_factory=list)
    extra: list = field(default_factory=list)
    mzone: list = field(default_factory=lambda: [None] * 5)
    szone: list = field(default_factory=lambda: [None] * 5)
    emz: list = field(default_factory=lambda: [None] * 2)

    # OPT tracking - maps "code,counter" to count used
    count_limits: dict = field(default_factory=dict)

    # Chain state
    chain_count: int = 0

    def get_cards_at_location(self, location: int, controller: int = 0) -> list:
        """Get all cards at a location bitmask."""
        cards = []
        if location & 0x02:  # LOCATION_HAND
            cards.extend(self.hand)
        if location & 0x04:  # LOCATION_MZONE
            cards.extend([c for c in self.mzone if c is not None])
            cards.extend([c for c in self.emz if c is not None])
        if location & 0x08:  # LOCATION_SZONE
            cards.extend([c for c in self.szone if c is not None])
        if location & 0x10:  # LOCATION_GRAVE
            cards.extend(self.gy)
        if location & 0x20:  # LOCATION_REMOVED
            cards.extend(self.banished)
        if location & 0x01:  # LOCATION_DECK
            cards.extend(self.deck)
        if location & 0x40:  # LOCATION_EXTRA
            cards.extend(self.extra)
        return cards

    def count_empty_zones(self, location: int, controller: int = 0) -> int:
        """Count empty zones at location."""
        if location & 0x04:  # LOCATION_MZONE
            return sum(1 for c in self.mzone if c is None) + sum(1 for c in self.emz if c is None)
        if location & 0x08:  # LOCATION_SZONE
            return sum(1 for c in self.szone if c is None)
        return 0


# Global game state accessible from Lua
_game_state: GameState = GameState()
_registered_effects: list = []
_effect_handler_card: Optional[CardState] = None
_lua_runtime: Optional[LuaRuntime] = None


def _resolve_lua_dir() -> Optional[Path]:
    path = os.environ.get(LUA_DIR_ENV)
    if not path:
        return None
    resolved = Path(path).expanduser()
    if not resolved.exists():
        return None
    return resolved


def create_lua_runtime() -> LuaRuntime:
    """Create a Lua runtime with comprehensive YGOPro API stubs."""
    lua = LuaRuntime(unpack_returned_tuples=True)
    global _lua_runtime
    _lua_runtime = lua

    # Inject the comprehensive API
    lua.execute(LUA_API_CODE)

    # Bind Python functions to Lua
    lua.globals()["_py_get_matching_cards"] = _py_get_matching_cards
    lua.globals()["_py_get_location_count"] = _py_get_location_count
    lua.globals()["_py_check_count_limit"] = _py_check_count_limit
    lua.globals()["_py_register_effect"] = _py_register_effect
    lua.globals()["_py_get_handler_card"] = _py_get_handler_card
    lua.globals()["_py_is_existing_target"] = _py_is_existing_target
    lua.globals()["_py_fusion_materials_ok"] = _py_fusion_materials_ok

    return lua


def _py_get_matching_cards(filter_func, tp: int, loc1: int, loc2: int, exclude_card) -> list:
    """Python callback to get cards matching a Lua filter function."""
    global _game_state

    cards = []
    # Get cards from player's locations
    if loc1 > 0:
        cards.extend(_game_state.get_cards_at_location(loc1, tp))
    # Get cards from opponent's locations
    if loc2 > 0:
        cards.extend(_game_state.get_cards_at_location(loc2, 1 - tp))

    # Apply filter function
    matching = []
    for card in cards:
        if exclude_card is not None:
            if getattr(card, "_lua_card", None) is exclude_card:
                continue
            if getattr(exclude_card, "cid", None) and card.cid == getattr(exclude_card, "cid", None):
                continue
        try:
            # Create Lua card object for filter
            if filter_func(card._lua_card):
                matching.append(card)
        except Exception:
            # Filter returned false or errored
            pass

    if _lua_runtime:
        lua_table = _lua_runtime.table()
        idx = 1
        for card in matching:
            lua_table[idx] = card
            idx += 1
        return lua_table
    return matching


def _py_get_location_count(tp: int, location: int) -> int:
    """Get count of empty zones at location."""
    global _game_state
    return _game_state.count_empty_zones(location, tp)


def _py_check_count_limit(code: int, counter: int) -> bool:
    """Check if OPT is available."""
    global _game_state
    key = f"{code},{counter}"
    return _game_state.count_limits.get(key, 0) < 1


def _py_register_effect(effect_data):
    """Register an effect from Lua."""
    global _registered_effects
    # Convert Lua table to Python dict
    if hasattr(effect_data, 'items'):
        # It's a Lua table - convert to dict
        py_dict = {}
        for k, v in effect_data.items():
            # Convert Lua values to Python
            if k == "effect_obj":
                py_dict[k] = v
            elif hasattr(v, 'items'):
                py_dict[k] = dict(v.items())
            else:
                py_dict[k] = v
        _registered_effects.append(py_dict)
    else:
        _registered_effects.append(dict(effect_data) if effect_data else {})


def _py_get_handler_card():
    """Get the current effect handler card."""
    global _effect_handler_card
    return _effect_handler_card


def _py_is_existing_target(filter_func, tp: int, loc1: int, loc2: int, count: int, exclude_card) -> bool:
    """Check if valid targets exist."""
    cards = _py_get_matching_cards(filter_func, tp, loc1, loc2, exclude_card)
    try:
        return len(cards) >= count
    except Exception:
        return sum(1 for _ in cards.items()) >= count


def _py_fusion_materials_ok(effect_obj, tp: int) -> bool:
    """Check fusion material availability for scripted effects."""
    global _game_state
    try:
        handler = effect_obj["_handler"]
        handler_code = int(getattr(handler, "code", 0))
    except Exception:
        return True

    # Tract (98567237) requires Engraver + 2 other LIGHT Fiends in hand/field.
    if handler_code == 98567237:
        candidates = []
        candidates.extend(_game_state.hand)
        candidates.extend([c for c in _game_state.mzone if c is not None])
        candidates.extend([c for c in _game_state.emz if c is not None])
        engraver = [c for c in candidates if c.cid == "20196"]
        light_fiends = [
            c for c in candidates
            if (c.attribute & ATTRIBUTE_BITS["LIGHT"]) and (c.race & RACE_BITS["FIEND"])
        ]
        other_light_fiends = [c for c in light_fiends if c.cid != "20196"]
        return bool(engraver) and len(other_light_fiends) >= 2

    return True


# Comprehensive Lua API code
LUA_API_CODE = """
-- ============================================================
-- YGOPro API Stubs for Ground Truth Verification
-- ============================================================

if not bit32 then
    bit32 = {}
    function bit32.band(a, b)
        return a & b
    end
end

Group = {}
Group.__index = Group
function Group.new(cards)
    local g = setmetatable({}, Group)
    g.cards = cards or {}
    return g
end
function Group:__len()
    return #self.cards
end
function Group:Match(filter_func, ...)
    local out = {}
    for _, c in ipairs(self.cards) do
        if filter_func(c, ...) then
            table.insert(out, c)
        end
    end
    return Group.new(out)
end
function Group:GetSum(func, ...)
    local sum = 0
    for _, c in ipairs(self.cards) do
        sum = sum + func(c, ...)
    end
    return sum
end
function Group:FilterCount(func, ...)
    local count = 0
    for _, c in ipairs(self.cards) do
        if func(c, ...) then
            count = count + 1
        end
    end
    return count
end
function Group:Iter()
    return ipairs(self.cards)
end

-- ============================================================
-- CONSTANTS
-- ============================================================

-- Locations (bitmask)
LOCATION_DECK    = 0x01
LOCATION_HAND    = 0x02
LOCATION_MZONE   = 0x04
LOCATION_SZONE   = 0x08
LOCATION_GRAVE   = 0x10
LOCATION_REMOVED = 0x20
LOCATION_EXTRA   = 0x40
LOCATION_OVERLAY = 0x80
LOCATION_ONFIELD = 0x0C  -- MZONE | SZONE
LOCATION_FZONE   = 0x100
LOCATION_STZONE  = 0x108  -- SZONE | FZONE

-- Positions
POS_FACEUP_ATTACK    = 0x1
POS_FACEDOWN_ATTACK  = 0x2
POS_FACEUP_DEFENSE   = 0x4
POS_FACEDOWN_DEFENSE = 0x8
POS_FACEUP           = 0x5
POS_FACEDOWN         = 0xA
POS_ATTACK           = 0x3
POS_DEFENSE          = 0xC

-- Attributes
ATTRIBUTE_EARTH  = 0x01
ATTRIBUTE_WATER  = 0x02
ATTRIBUTE_FIRE   = 0x04
ATTRIBUTE_WIND   = 0x08
ATTRIBUTE_LIGHT  = 0x10
ATTRIBUTE_DARK   = 0x20
ATTRIBUTE_DIVINE = 0x40

-- Races
RACE_WARRIOR     = 0x1
RACE_SPELLCASTER = 0x2
RACE_FAIRY       = 0x4
RACE_FIEND       = 0x8
RACE_ZOMBIE      = 0x10
RACE_MACHINE     = 0x20
RACE_AQUA        = 0x40
RACE_PYRO        = 0x80
RACE_ROCK        = 0x100
RACE_WINDBEAST   = 0x200
RACE_PLANT       = 0x400
RACE_INSECT      = 0x800
RACE_THUNDER     = 0x1000
RACE_DRAGON      = 0x2000
RACE_BEAST       = 0x4000
RACE_BEASTWARRIOR = 0x8000
RACE_DINOSAUR    = 0x10000
RACE_FISH        = 0x20000
RACE_SEASERPENT  = 0x40000
RACE_REPTILE     = 0x80000
RACE_PSYCHIC     = 0x100000
RACE_DIVINE      = 0x200000
RACE_CREATORGOD  = 0x400000
RACE_WYRM        = 0x800000
RACE_CYBERSE     = 0x1000000
RACE_ILLUSION    = 0x2000000

-- Types
TYPE_MONSTER     = 0x1
TYPE_SPELL       = 0x2
TYPE_TRAP        = 0x4
TYPE_NORMAL      = 0x10
TYPE_EFFECT      = 0x20
TYPE_FUSION      = 0x40
TYPE_RITUAL      = 0x80
TYPE_TRAPMONSTER = 0x100
TYPE_SPIRIT      = 0x200
TYPE_UNION       = 0x400
TYPE_GEMINI      = 0x800
TYPE_TUNER       = 0x1000
TYPE_SYNCHRO     = 0x2000
TYPE_TOKEN       = 0x4000
TYPE_QUICKPLAY   = 0x10000
TYPE_CONTINUOUS  = 0x20000
TYPE_EQUIP       = 0x40000
TYPE_FIELD       = 0x80000
TYPE_COUNTER     = 0x100000
TYPE_FLIP        = 0x200000
TYPE_TOON        = 0x400000
TYPE_XYZ         = 0x800000
TYPE_PENDULUM    = 0x1000000
TYPE_SPSUMMON    = 0x2000000
TYPE_LINK        = 0x4000000
TYPES_TOKEN      = TYPE_MONSTER + TYPE_TOKEN + TYPE_EFFECT

-- Effect types
EFFECT_TYPE_SINGLE     = 0x0001
EFFECT_TYPE_FIELD      = 0x0002
EFFECT_TYPE_EQUIP      = 0x0004
EFFECT_TYPE_ACTIONS    = 0x0008
EFFECT_TYPE_ACTIVATE   = 0x0010
EFFECT_TYPE_FLIP       = 0x0020
EFFECT_TYPE_IGNITION   = 0x0040
EFFECT_TYPE_TRIGGER_O  = 0x0080
EFFECT_TYPE_QUICK_O    = 0x0100
EFFECT_TYPE_TRIGGER_F  = 0x0200
EFFECT_TYPE_QUICK_F    = 0x0400
EFFECT_TYPE_CONTINUOUS = 0x0800
EFFECT_TYPE_GRANT      = 0x1000
EFFECT_TYPE_TARGET     = 0x2000
EFFECT_TYPE_XMATERIAL  = 0x4000

-- Effect flags
EFFECT_FLAG_INITIAL           = 0x0001
EFFECT_FLAG_FUNC_VALUE        = 0x0002
EFFECT_FLAG_COUNT_LIMIT       = 0x0004
EFFECT_FLAG_FIELD_ONLY        = 0x0008
EFFECT_FLAG_CARD_TARGET       = 0x0010
EFFECT_FLAG_IGNORE_RANGE      = 0x0020
EFFECT_FLAG_ABSOLUTE_TARGET   = 0x0040
EFFECT_FLAG_IGNORE_IMMUNE     = 0x0080
EFFECT_FLAG_SET_AVAILABLE     = 0x0100
EFFECT_FLAG_CANNOT_NEGATE     = 0x0200
EFFECT_FLAG_CANNOT_DISABLE    = 0x0400
EFFECT_FLAG_PLAYER_TARGET     = 0x0800
EFFECT_FLAG_BOTH_SIDE         = 0x1000
EFFECT_FLAG_COPY_INHERIT      = 0x2000
EFFECT_FLAG_DAMAGE_STEP       = 0x4000
EFFECT_FLAG_DAMAGE_CAL        = 0x8000
EFFECT_FLAG_DELAY             = 0x10000
EFFECT_FLAG_SINGLE_RANGE      = 0x20000
EFFECT_FLAG_UNCOPYABLE        = 0x40000
EFFECT_FLAG_OATH              = 0x80000
EFFECT_FLAG_SPSUM_PARAM       = 0x100000
EFFECT_FLAG_REPEAT            = 0x200000
EFFECT_FLAG_NO_TURN_RESET     = 0x400000
EFFECT_FLAG_EVENT_PLAYER      = 0x800000
EFFECT_FLAG_OWNER_RELATE      = 0x1000000
EFFECT_FLAG_CLIENT_HINT       = 0x2000000
EFFECT_FLAG_CONTINUOUS_TARGET = 0x4000000
EFFECT_FLAG_LIMIT_ZONE        = 0x8000000
EFFECT_FLAG2_CHECK_SIMULTANEOUS = 0x10000000

-- Categories
CATEGORY_DESTROY       = 0x1
CATEGORY_RELEASE       = 0x2
CATEGORY_REMOVE        = 0x4
CATEGORY_TOHAND        = 0x8
CATEGORY_TODECK        = 0x10
CATEGORY_TOGRAVE       = 0x20
CATEGORY_DECKDES       = 0x40
CATEGORY_HANDES        = 0x80
CATEGORY_SUMMON        = 0x100
CATEGORY_SPECIAL_SUMMON = 0x200
CATEGORY_TOKEN         = 0x400
CATEGORY_FLIP          = 0x800
CATEGORY_POSITION      = 0x1000
CATEGORY_CONTROL       = 0x2000
CATEGORY_DISABLE       = 0x4000
CATEGORY_DRAW          = 0x8000
CATEGORY_SEARCH        = 0x10000
CATEGORY_EQUIP         = 0x20000
CATEGORY_DAMAGE        = 0x40000
CATEGORY_RECOVER       = 0x80000
CATEGORY_ATKCHANGE     = 0x100000
CATEGORY_DEFCHANGE     = 0x200000
CATEGORY_COUNTER       = 0x400000
CATEGORY_COIN          = 0x800000
CATEGORY_DICE          = 0x1000000
CATEGORY_LEAVE_GRAVE   = 0x2000000
CATEGORY_LVCHANGE      = 0x4000000
CATEGORY_NEGATE        = 0x8000000
CATEGORY_ANNOUNCE      = 0x10000000
CATEGORY_FUSION_SUMMON = 0x20000000
CATEGORY_TOEXTRA       = 0x40000000

-- Events
EVENT_STARTUP          = 1000
EVENT_FLIP             = 1001
EVENT_FREE_CHAIN       = 1002
EVENT_DESTROY          = 1010
EVENT_REMOVE           = 1011
EVENT_TO_HAND          = 1012
EVENT_TO_DECK          = 1013
EVENT_TO_GRAVE         = 1014
EVENT_LEAVE_FIELD      = 1015
EVENT_CHANGE_POS       = 1016
EVENT_RELEASE          = 1017
EVENT_DISCARD          = 1018
EVENT_LEAVE_FIELD_P    = 1019
EVENT_CHAIN_SOLVING    = 1020
EVENT_CHAIN_ACTIVATING = 1021
EVENT_CHAIN_SOLVED     = 1022
EVENT_CHAIN_END        = 1023
EVENT_CHAINING         = 1024
EVENT_BECOME_TARGET    = 1025
EVENT_SUMMON           = 1030
EVENT_FLIP_SUMMON      = 1031
EVENT_SPSUMMON         = 1032
EVENT_SPSUMMON_SUCCESS = 1033
EVENT_SUMMON_SUCCESS   = 1034
EVENT_FLIP_SUMMON_SUCCESS = 1035
EVENT_MSET             = 1036
EVENT_SSET             = 1037
EVENT_BE_MATERIAL      = 1038
EVENT_ADJUST           = 1100

-- Reasons
REASON_DESTROY    = 0x1
REASON_RELEASE    = 0x2
REASON_TEMPORARY  = 0x4
REASON_EFFECT     = 0x8
REASON_SUMMON     = 0x10
REASON_BATTLE     = 0x20
REASON_COST       = 0x40
REASON_RULE       = 0x80
REASON_SPSUMMON   = 0x100
REASON_DISCARD    = 0x200
REASON_MATERIAL   = 0x400
REASON_RETURN     = 0x800
REASON_FUSION     = 0x1000
REASON_SYNCHRO    = 0x2000
REASON_RITUAL     = 0x4000
REASON_XYZ        = 0x8000
REASON_REPLACE    = 0x10000
REASON_DRAW       = 0x20000
REASON_REDIRECT   = 0x40000
REASON_REVEAL     = 0x80000
REASON_LINK       = 0x100000
REASON_LOST_TARGET = 0x200000

-- Hints
HINT_SELECTMSG     = 1
HINTMSG_FACEUP     = 500
HINTMSG_TOGRAVE    = 507
HINTMSG_ATOHAND    = 511
HINTMSG_TODECK     = 512
HINTMSG_SPSUMMON   = 519
HINTMSG_EQUIP      = 522
HINTMSG_REMOVE     = 531
HINTMSG_DISCARD    = 533
HINTMSG_DESTROY    = 535
HINTMSG_TARGET     = 536

-- Resets
RESET_SELF_TURN    = 0x10000000
RESET_OPPO_TURN    = 0x20000000
RESET_PHASE        = 0x40000000
RESET_CHAIN        = 0x80000000
RESET_EVENT        = 0x1000000
RESET_CARD         = 0x2000000
RESET_CODE         = 0x4000000
RESET_COPY         = 0x8000000
RESET_DISABLE      = 0x10000
RESET_TURN_SET     = 0x100000
RESET_TOGRAVE      = 0x200000
RESET_REMOVE       = 0x400000
RESET_TOHAND       = 0x800000
RESET_TODECK       = 0x1000
RESET_LEAVE        = 0x2000
RESET_TOFIELD      = 0x4000
RESET_CONTROL      = 0x8000
RESET_OVERLAY      = 0x10
RESET_MSCHANGE     = 0x20
RESET_STANDARD     = RESET_TOFIELD+RESET_LEAVE+RESET_TODECK+RESET_TOHAND+RESET_REMOVE+RESET_TOGRAVE+RESET_TURN_SET

RESETS_STANDARD    = RESET_STANDARD

-- Timing
TIMING_DRAW_PHASE     = 0x1
TIMING_STANDBY_PHASE  = 0x2
TIMING_MAIN_END       = 0x4
TIMING_BATTLE_START   = 0x8
TIMING_BATTLE_END     = 0x10
TIMING_END_PHASE      = 0x20
TIMING_SUMMON         = 0x40
TIMING_SPSUMMON       = 0x80
TIMING_FLIPSUMMON     = 0x100
TIMING_MSET           = 0x200
TIMING_SSET           = 0x400
TIMING_POS_CHANGE     = 0x800
TIMING_ATTACK         = 0x1000
TIMING_DAMAGE_STEP    = 0x2000
TIMING_DAMAGE_CAL     = 0x4000
TIMING_CHAIN_END      = 0x8000
TIMING_DRAW           = 0x10000
TIMING_EQUIP          = 0x20000
TIMING_BATTLE_PHASE   = 0x40000
TIMING_TOGRAVE        = 0x80000
TIMING_TOHAND         = 0x100000
TIMING_TODECK         = 0x200000
TIMING_REMOVE         = 0x400000
TIMING_DAMAGE         = 0x800000
TIMING_RECOVER        = 0x1000000
TIMING_DESTROY        = 0x2000000
TIMING_RELEASE        = 0x4000000

TIMINGS_CHECK_MONSTER = TIMING_SUMMON+TIMING_SPSUMMON+TIMING_FLIPSUMMON+TIMING_MSET
TIMINGS_CHECK_MONSTER_E = TIMING_SUMMON+TIMING_SPSUMMON+TIMING_MSET

-- Setcodes (archetypes)
SET_FIENDSMITH = 0x1eb

-- Phases
PHASE_DRAW       = 0x01
PHASE_STANDBY    = 0x02
PHASE_MAIN1      = 0x04
PHASE_BATTLE     = 0x08
PHASE_DAMAGE     = 0x10
PHASE_DAMAGE_CAL = 0x20
PHASE_MAIN2      = 0x40
PHASE_END        = 0x80

-- Misc
SEQ_DECKSHUFFLE = 2
PLAYER_NONE = 2

-- ============================================================
-- CARD OBJECT
-- ============================================================

Card = {}
Card.__index = Card

function Card:new(data)
    local c = setmetatable({}, Card)
    c.code = data.code or 0
    c.cid = data.cid or ""
    c.name = data.name or ""
    c.location = data.location or 0
    c.position = data.position or POS_FACEUP_ATTACK
    c.race = data.race or 0
    c.attribute = data.attribute or 0
    c.level = data.level or 0
    c.rank = data.rank or 0
    c.link = data.link or 0
    c.card_type = data.card_type or TYPE_MONSTER
    c.setcode = data.setcode or 0
    c.controller = data.controller or 0
    c.owner = data.owner or 0
    c.equip_target = data.equip_target
    c.equipped_cards = data.equipped_cards or {}
    c.materials = data.materials or {}
    c.counters = data.counters or {}
    c._effect_handler = nil
    return c
end

function Card:IsLocation(loc)
    return bit32.band(self.location, loc) > 0
end

function Card:IsRace(race)
    return bit32.band(self.race, race) > 0
end

function Card:IsAttribute(attr)
    return bit32.band(self.attribute, attr) > 0
end

function Card:IsCode(code)
    return self.code == code
end

function Card:IsSetCard(setcode)
    return bit32.band(self.setcode, setcode) > 0
end

function Card:IsType(t)
    return bit32.band(self.card_type, t) > 0
end

function Card:IsMonster()
    return self:IsType(TYPE_MONSTER)
end

function Card:IsMonsterCard()
    return self:IsMonster()
end

function Card:IsSpell()
    return self:IsType(TYPE_SPELL)
end

function Card:IsTrap()
    return self:IsType(TYPE_TRAP)
end

function Card:IsSpellTrap()
    return self:IsSpell() or self:IsTrap()
end

function Card:IsFaceup()
    return bit32.band(self.position, POS_FACEUP) > 0
end

function Card:IsFacedown()
    return bit32.band(self.position, POS_FACEDOWN) > 0
end

function Card:IsControler(tp)
    return self.controller == tp
end

function Card:GetControler()
    return self.controller
end

function Card:GetOwner()
    return self.owner
end

function Card:IsOnField()
    return self:IsLocation(LOCATION_ONFIELD)
end

function Card:IsLinkMonster()
    return self:IsType(TYPE_LINK)
end

function Card:GetLink()
    return self.link or 0
end

function Card:IsLevelAbove(lv)
    return self.level >= lv
end

function Card:GetEquipGroup()
    return Group.new(self.equipped_cards or {})
end

function Card:GetEquipTarget()
    return self.equip_target
end

function Card:IsEquipCard()
    return self.equip_target ~= nil
end

function Card:IsEquipSpell()
    return self:IsType(TYPE_EQUIP) or self.equip_target ~= nil
end

-- Ability checks (simplified - always return true for condition checking)
function Card:IsAbleToHand()
    return true
end

function Card:IsAbleToGrave()
    return true
end

function Card:IsAbleToGraveAsCost()
    return true
end

function Card:IsAbleToDeck()
    return true
end

function Card:IsAbleToDeckOrExtraAsCost()
    return true
end

function Card:IsAbleToRemove()
    return true
end

function Card:IsAbleToRemoveAsCost()
    return true
end

function Card:IsCanBeSpecialSummoned(e, sumtype, tp, nocheck, nolimit)
    return true
end

function Card:IsCanBeEffectTarget(e)
    return true
end

function Card:IsCanBeDisabledByEffect()
    return true
end

function Card:IsDiscardable()
    return self:IsLocation(LOCATION_HAND)
end

function Card:IsRelateToEffect(e)
    return true
end

function Card:IsSSetable()
    return true
end

function Card:IsSequence(seq)
    return true
end

function Card:IsPreviousLocation(loc)
    return false
end

function Card:IsPreviousControler(tp)
    return false
end

function Card:IsPreviousSetCard(setcode)
    return false
end

function Card:IsPreviousPosition(pos)
    return false
end

function Card:IsStatus(status)
    return false
end

function Card:IsReason(reason)
    return false
end

function Card:IsNegatableMonster()
    return true
end

function Card.IsNegatable(c)
    return true
end

function Card:IsReleasableByEffect()
    return true
end

function Card:IsAbleToChangeControler()
    return true
end

function Card:IsForbidden()
    return false
end

function Card:IsImmuneToEffect(e)
    return false
end

function Card:CheckUniqueOnField(tp)
    return true
end

function Card:GetMaterial()
    return self.materials or {}
end

function Card:GetAttribute()
    return self.attribute
end

function Card:Clone()
    return Card:new({
        code = self.code,
        cid = self.cid,
        name = self.name,
        location = self.location,
        position = self.position,
        race = self.race,
        attribute = self.attribute,
        level = self.level,
        rank = self.rank,
        link = self.link,
        card_type = self.card_type,
        setcode = self.setcode,
        controller = self.controller,
        owner = self.owner
    })
end

-- Effect registration
function Card:RegisterEffect(e)
    e._handler = self
    _py_register_effect({
        effect_obj = e,
        handler_code = self.code,
        effect_type = e._type,
        effect_range = e._range,
        effect_code = e._code,
        count_limit = e._count_limit,
        count_limit_id = e._count_limit_id,
        description = e._description,
        category = e._category,
        property = e._property,
        has_condition = e._condition_func ~= nil,
        has_cost = e._cost_func ~= nil,
        has_target = e._target_func ~= nil,
        has_operation = e._operation_func ~= nil,
        condition_func = e._condition_func,
        cost_func = e._cost_func,
        target_func = e._target_func
    })
end

function Card:EnableReviveLimit()
    self._revive_limit = true
end

function Card:SetSPSummonOnce(code)
    self._spsummon_once = code
end

function Card:SetUniqueOnField(unique, location, value)
    self._unique = {unique, location, value}
end

function Card:NegateEffects()
    self._effects_negated = true
end

function Card:RegisterFlagEffect(code, reset, property, count)
    self._flag_effects = self._flag_effects or {}
    self._flag_effects[code] = count
end

function Card:AddMustBeFusionSummoned()
    self._must_be_fusion = true
end

-- ============================================================
-- EFFECT OBJECT
-- ============================================================

Effect = {}
Effect.__index = Effect

function Effect.CreateEffect(c)
    local e = setmetatable({}, Effect)
    e._handler = c
    e._type = 0
    e._range = 0
    e._code = 0
    e._count_limit = nil
    e._count_limit_id = nil
    e._description = 0
    e._category = 0
    e._property = 0
    e._condition_func = nil
    e._cost_func = nil
    e._target_func = nil
    e._operation_func = nil
    e._value = nil
    e._reset = 0
    e._target_range = nil
    e._hint_timing = nil
    e._label = nil
    e._label_object = nil
    return e
end

function Effect:GetHandler()
    return self._handler
end

function Effect:GetHandlerPlayer()
    return self._handler and self._handler.controller or 0
end

function Effect:SetType(t)
    self._type = t
end

function Effect:SetRange(range)
    self._range = range
end

function Effect:SetCode(code)
    self._code = code
end

function Effect:SetCountLimit(count, id)
    self._count_limit = count
    if type(id) == "table" then
        self._count_limit_id = id
    else
        self._count_limit_id = {id, 0}
    end
end

function Effect:SetDescription(desc)
    self._description = desc
end

function Effect:SetCategory(cat)
    self._category = cat
end

function Effect:SetProperty(prop)
    self._property = prop
end

function Effect:SetCondition(func)
    self._condition_func = func
end

function Effect:SetCost(func)
    self._cost_func = func
end

function Effect:SetTarget(func)
    self._target_func = func
end

function Effect:SetOperation(func)
    self._operation_func = func
end

function Effect:SetValue(val)
    self._value = val
end

function Effect:SetReset(reset)
    self._reset = reset
end

function Effect:SetTargetRange(r1, r2)
    self._target_range = {r1, r2}
end

function Effect:SetHintTiming(t1, t2)
    self._hint_timing = {t1, t2 or t1}
end

function Effect:SetLabel(label)
    self._label = label
end

function Effect:GetLabel()
    return self._label or 0
end

function Effect:SetLabelObject(obj)
    self._label_object = obj
end

function Effect:GetLabelObject()
    return self._label_object
end

function Effect:IsActivated()
    return bit32.band(self._type, EFFECT_TYPE_ACTIONS) > 0
end

function Effect:Clone()
    local e = setmetatable({}, Effect)
    e._handler = self._handler
    e._type = self._type
    e._range = self._range
    e._code = self._code
    e._count_limit = self._count_limit
    e._count_limit_id = self._count_limit_id
    e._description = self._description
    e._category = self._category
    e._property = self._property
    e._condition_func = self._condition_func
    e._cost_func = self._cost_func
    e._target_func = self._target_func
    e._operation_func = self._operation_func
    e._value = self._value
    e._reset = self._reset
    e._target_range = self._target_range
    e._hint_timing = self._hint_timing
    e._label = self._label
    e._label_object = self._label_object
    return e
end

-- ============================================================
-- DUEL OBJECT
-- ============================================================

Duel = {}

function Duel.GetMatchingGroup(filter_func, tp, loc1, loc2, ex, ...)
    -- Call Python to get matching cards
    local cards = _py_get_matching_cards(filter_func, tp, loc1, loc2, ex)
    local group = {}
    if cards then
        for i=1, #cards do
            local c = cards[i]
            if c and c._lua_card then
                table.insert(group, c._lua_card)
            end
        end
    end
    return Group.new(group)
end

function Duel.IsExistingMatchingCard(filter_func, tp, loc1, loc2, count, ex, ...)
    local group = Duel.GetMatchingGroup(filter_func, tp, loc1, loc2, ex, ...)
    return #group >= count
end

function Duel.IsExistingTarget(filter_func, tp, loc1, loc2, count, ex, ...)
    return Duel.IsExistingMatchingCard(filter_func, tp, loc1, loc2, count, ex, ...)
end

function Duel.GetLocationCount(tp, location)
    return _py_get_location_count(tp, location)
end

function Duel.GetMZoneCount(tp)
    return Duel.GetLocationCount(tp, LOCATION_MZONE)
end

function Duel.CheckCountLimit(tp, code, counter)
    return _py_check_count_limit(code, counter or 0)
end

function Duel.GetChainInfo(chain_count, info)
    return 0, 0, 0  -- Simplified
end

function Duel.IsTurnPlayer(tp)
    return tp == 0  -- Assume player 0 is turn player
end

function Duel.HasFlagEffect(tp, code)
    return false
end

function Duel.IsPlayerCanDraw(tp)
    return true
end

function Duel.IsPlayerCanSpecialSummonMonster(tp, code, ...)
    return true
end

-- Operation stubs (only called during resolution, not condition checking)
function Duel.SetOperationInfo(chain, category, targets, count, tp, loc) end
function Duel.SetPossibleOperationInfo(chain, category, targets, count, tp, loc) end
function Duel.SetTargetCard(targets) end
function Duel.SetTargetPlayer(tp) end
function Duel.SetTargetParam(param) end
function Duel.Hint(hint_type, tp, hint_value) end
function Duel.HintSelection(group) end
function Duel.SelectMatchingCard(tp, filter, p, loc1, loc2, min, max, ex, ...) return {} end
function Duel.SelectTarget(tp, filter, p, loc1, loc2, min, max, ex, ...) return {} end
function Duel.SelectEffect(tp, ...) return nil end
function Duel.GetFirstTarget() return nil end
function Duel.GetTargetCards(e) return {} end
function Duel.SendtoHand(cards, tp, reason) end
function Duel.SendtoGrave(cards, reason) end
function Duel.SendtoDeck(cards, tp, seq, reason) end
function Duel.ConfirmCards(tp, cards) end
function Duel.SpecialSummon(c, sumtype, tp, ctrl, nocheck, nolimit, pos) return 1 end
function Duel.Destroy(cards, reason, dest) return 0 end
function Duel.Remove(cards, pos, reason) return 0 end
function Duel.Equip(tp, equip_card, target) return true end
function Duel.ShuffleHand(tp) end
function Duel.DiscardHand(tp, filter, min, max, reason, ex, ...) return {} end
function Duel.SSet(tp, cards) end
function Duel.RegisterEffect(e, tp) end
function Duel.RegisterFlagEffect(tp, code, reset, property, count) end

-- ============================================================
-- AUX LIBRARY
-- ============================================================

aux = {}

function aux.Stringid(code, idx)
    return code * 16 + idx
end

function aux.FilterBoolFunction(filter, ...)
    local args = {...}
    return function(c)
        return filter(c, table.unpack(args))
    end
end

function aux.FilterBoolFunctionEx(filter, ...)
    return aux.FilterBoolFunction(filter, ...)
end

function aux.SelectUnselectGroup(group, e, tp, min, max, check_func, sel_flag, tp2, hint, ...)
    -- Simplified: check if group has enough valid cards
    if sel_flag == 0 then
        -- Check mode: return if valid selection is possible
        return #group >= min
    else
        -- Select mode: return first valid cards
        local result = {}
        for i = 1, math.min(min, #group) do
            table.insert(result, group[i])
        end
        return result
    end
end

function aux.NecroValleyFilter(filter)
    return filter
end

function aux.FALSE()
    return false
end

function aux.TRUE()
    return true
end

function aux.RegisterClientHint(c, e, tp, reset, code, val)
end

-- ============================================================
-- FUSION LIBRARY
-- ============================================================

Fusion = {}

function Fusion.AddProcMix(c, sub, ...)
    -- Register fusion summoning procedure
    c._fusion_materials = {...}
end

function Fusion.AddProcMixN(c, sub, ...)
    -- Register fusion summoning procedure with N materials
    c._fusion_materials = {...}
end

function Fusion.AddContactProc(c, func, mat_func, sum_con, sum_op, desc, set_op)
    -- Contact fusion
    c._contact_fusion = true
end

function Fusion.CreateSummonEff(c, desc, summon_con, filter, from_extra)
    -- Create fusion summon effect
    return Effect.CreateEffect(c)
end

function Fusion.SummonEffTG(...)
    -- Return a target function closure used by SetTarget
    return function(e, tp, eg, ep, ev, re, r, rp, chk)
        if chk == 0 then return _py_fusion_materials_ok(e, tp) end
    end
end

function Fusion.SummonEffOP(e, tp, eg, ep, ev, re, r, rp)
    -- Fusion summon operation
end

function Fusion.ShuffleMaterial(mat_filter)
    -- Material shuffled back to deck
    return mat_filter
end

function Fusion.IsMonsterFilter(filter)
    return filter
end

function Fusion.OnFieldMat(c)
    -- Materials must be on field
    return true
end

-- ============================================================
-- LINK LIBRARY
-- ============================================================

Link = {}

function Link.AddProcedure(c, filter, min, max, ...)
    -- Register link summoning procedure
    c._link_materials = {filter = filter, min = min, max = max}
end

-- ============================================================
-- COST FUNCTIONS
-- ============================================================

Cost = {}

function Cost.SelfDiscard(e, tp, eg, ep, ev, re, r, rp, chk)
    local c = e:GetHandler()
    if chk == 0 then
        return c:IsDiscardable()
    end
    -- Actual discard would happen here
end

function Cost.SelfBanish(e, tp, eg, ep, ev, re, r, rp, chk)
    local c = e:GetHandler()
    if chk == 0 then
        return c:IsLocation(LOCATION_GRAVE) and c:IsAbleToRemove()
    end
    -- Actual banish would happen here
end

function Cost.SelfTribute(e, tp, eg, ep, ev, re, r, rp, chk)
    local c = e:GetHandler()
    if chk == 0 then
        return c:IsOnField() and c:IsReleasableByEffect()
    end
    -- Actual tribute would happen here
end

-- ============================================================
-- GLOBAL FUNCTIONS
-- ============================================================

function GetID()
    return {}, _current_card_code or 0
end

-- Helper to load a card script
function LoadCardScript(code)
    _current_card_code = code
    _registered_effects = {}
end

-- Set game state for condition checking
_game_state = {}

function SetGameState(state)
    _game_state = state
end

-- Track registered effects
_registered_effects = {}
"""


def load_card_script(lua, passcode: str) -> bool:
    """Load a card's Lua script into the runtime."""
    # Find the Lua file by passcode
    lua_files = list(LUA_DIR.glob(f"c{passcode}.lua")) + list(LUA_DIR.glob(f"c{passcode}_*.lua"))

    if not lua_files:
        print(f"No Lua file found for passcode {passcode}")
        return False

    lua_path = lua_files[0]
    script = lua_path.read_text()

    # Set current card code
    lua.execute(f"LoadCardScript({passcode})")

    try:
        lua.execute(script)
        return True
    except Exception as e:
        print(f"Error loading {lua_path}: {e}")
        return False


def get_registered_effects(lua) -> list:
    """Get effects registered by the loaded script."""
    global _registered_effects
    return _registered_effects.copy()


def check_effect_can_activate(lua, effect_idx: int, game_state: GameState) -> dict:
    """
    Check if a specific effect can activate in the given game state.

    Returns dict with:
    - can_activate: bool
    - reason: str describing why/why not
    """
    global _game_state, _registered_effects
    _game_state = game_state

    if effect_idx >= len(_registered_effects):
        return {"can_activate": False, "reason": "Effect index out of range"}

    effect = _registered_effects[effect_idx]

    # Check basic conditions
    result = {
        "can_activate": True,
        "reason": "",
        "effect": effect
    }

    # Check count limit (OPT)
    if effect.get("count_limit") and effect.get("count_limit_id"):
        code = effect["count_limit_id"][0] if isinstance(effect["count_limit_id"], list) else effect["count_limit_id"]
        counter = effect["count_limit_id"][1] if isinstance(effect["count_limit_id"], list) and len(effect["count_limit_id"]) > 1 else 0
        key = f"{code},{counter}"
        if game_state.count_limits.get(key, 0) >= 1:
            result["can_activate"] = False
            result["reason"] = f"OPT already used: {key}"
            return result

    return result


def create_card_for_lua(lua, card_state: CardState):
    """Create a Lua Card object from a CardState."""
    lua_card = lua.eval(f"""
        Card:new({{
            code = {card_state.code},
            cid = "{card_state.cid}",
            name = "{card_state.name}",
            location = {card_state.location},
            position = {card_state.position},
            race = {card_state.race},
            attribute = {card_state.attribute},
            level = {card_state.level},
            rank = {card_state.rank},
            link = {card_state.link},
            card_type = {card_state.card_type},
            setcode = {card_state.setcode},
            controller = {card_state.controller},
            owner = {card_state.owner}
        }})
    """)
    card_state._lua_card = lua_card
    return lua_card


def load_and_register_card(lua, passcode: str) -> bool:
    """Load a card script and execute initial_effect to register its effects."""
    global _registered_effects
    _registered_effects = []

    # Find the Lua file by passcode
    lua_dir = _resolve_lua_dir()
    if not lua_dir:
        print(f"Lua script dir not set. Set {LUA_DIR_ENV} to enable ground-truth checks.")
        return False
    lua_files = list(lua_dir.glob(f"c{passcode}.lua")) + list(lua_dir.glob(f"c{passcode}_*.lua"))

    if not lua_files:
        print(f"No Lua file found for passcode {passcode}")
        return False

    lua_path = lua_files[0]
    script = lua_path.read_text()

    # Wrap the script to make s and id accessible and call initial_effect
    # The original script uses: local s,id=GetID()
    # We need to capture 's' and call s.initial_effect with a card object
    wrapped_script = f"""
do
    _current_card_code = {passcode}

    -- Execute the card script (defines s.initial_effect)
    {script}

    -- Create handler card and call initial_effect
    local handler = Card:new({{
        code = {passcode},
        location = LOCATION_DECK,
        race = 0,
        attribute = 0,
        setcode = 0
    }})
    s.initial_effect(handler)
end
"""

    try:
        lua.execute(wrapped_script)
        return True
    except Exception as e:
        print(f"Error loading {lua_path}: {e}")
        return False


def _effect_key_to_index(effect_key: str) -> Optional[int]:
    match = re.match(r"e(\d+)$", str(effect_key).strip())
    if not match:
        return None
    idx = int(match.group(1)) - 1
    return idx if idx >= 0 else None


def _parse_attribute(value: str | None) -> int:
    if not value:
        return 0
    return ATTRIBUTE_BITS.get(str(value).upper(), 0)


def _parse_race(value: str | None) -> int:
    if not value:
        return 0
    return RACE_BITS.get(str(value).upper(), 0)


def _parse_type(entry: dict) -> int:
    raw = entry.get("type") or entry.get("card_type")
    type_bits = 0
    if raw:
        type_bits |= TYPE_BITS.get(str(raw).upper(), 0)
    if type_bits == 0:
        type_bits = TYPE_BITS["MONSTER"]
    if entry.get("is_link"):
        type_bits |= TYPE_BITS["LINK"]
    if entry.get("is_equip"):
        type_bits |= TYPE_BITS["EQUIP"]
        type_bits |= TYPE_BITS["SPELL"]
    return type_bits


def _card_state_from_entry(entry: dict, location: int) -> CardState:
    cid = str(entry.get("cid", ""))
    passcode = CID_TO_PASSCODE.get(cid, cid if cid.isdigit() else "0")
    code = int(passcode) if str(passcode).isdigit() else 0
    name = entry.get("name", cid)
    attribute = _parse_attribute(entry.get("attribute"))
    race = _parse_race(entry.get("race"))
    level = int(entry.get("level", 0) or 0)
    link = int(entry.get("link", 0) or entry.get("link_rating", 0) or 0)
    card_type = _parse_type(entry)
    setcode = int(entry.get("setcode", 0) or 0)
    if not setcode and cid in CID_TO_PASSCODE:
        setcode = 0x1EB
    return CardState(
        code=code,
        cid=cid,
        name=name,
        location=location,
        race=race,
        attribute=attribute,
        level=level,
        link=link,
        card_type=card_type,
        setcode=setcode,
    )


def _build_lua_state(lua, state_data: dict) -> GameState:
    gs = GameState()

    def add_cards(entries, location, zone_list=None):
        cards = []
        for entry in entries:
            card_state = _card_state_from_entry(entry, location)
            create_card_for_lua(lua, card_state)
            cards.append(card_state)
        if zone_list is not None:
            for idx, card_state in enumerate(cards):
                if idx >= len(zone_list):
                    break
                zone_list[idx] = card_state
        return cards

    gs.hand = add_cards(state_data.get("hand", []), 0x02)
    gs.deck = add_cards(state_data.get("deck", []), 0x01)
    gs.gy = add_cards(state_data.get("gy", []), 0x10)
    gs.banished = add_cards(state_data.get("banished", []), 0x20)
    gs.extra = add_cards(state_data.get("extra", []), 0x40)

    field = state_data.get("field", {})
    if isinstance(field, list):
        field = {"mz": field}

    add_cards(field.get("mz", []), 0x04, gs.mzone)
    add_cards(field.get("emz", []), 0x04, gs.emz)
    add_cards(field.get("stz", []), 0x08, gs.szone)
    add_cards(field.get("fz", []), 0x08, gs.szone)

    # Equip cards: attach to host and add to SZONE for Lua equip checks.
    mz_entries = field.get("mz", [])
    for idx, entry in enumerate(mz_entries):
        if idx >= len(gs.mzone):
            break
        host = gs.mzone[idx]
        if not host:
            continue
        for equip_entry in entry.get("equipped", []) or []:
            equip_entry = dict(equip_entry)
            equip_entry.setdefault("is_equip", True)
            equip_state = _card_state_from_entry(equip_entry, 0x08)
            create_card_for_lua(lua, equip_state)
            equip_state.equip_target = host
            host.equipped_cards.append(equip_state._lua_card)
            if getattr(host, "_lua_card", None) is not None:
                if _lua_runtime:
                    lua_table = _lua_runtime.table()
                    for idx, eq in enumerate(host.equipped_cards, start=1):
                        lua_table[idx] = eq
                    host._lua_card.equipped_cards = lua_table
                else:
                    host._lua_card.equipped_cards = host.equipped_cards
            gs.szone.append(equip_state)

    return gs


def _build_python_snapshot(state_data: dict) -> dict:
    zones = {
        "hand": [],
        "deck": [],
        "gy": [],
        "banished": [],
        "extra": [],
        "field_zones": {
            "mz": [None, None, None, None, None],
            "emz": [None, None],
            "stz": [None, None, None, None, None],
            "fz": [None],
        },
    }

    def to_card(entry: dict) -> dict:
        card = {"cid": str(entry.get("cid", "")), "name": entry.get("name", "")}
        metadata = {}
        if entry.get("attribute"):
            metadata["attribute"] = entry["attribute"]
        if entry.get("race"):
            metadata["race"] = entry["race"]
        if entry.get("summon_type"):
            metadata["summon_type"] = entry["summon_type"]
        if entry.get("link") or entry.get("link_rating"):
            metadata["link_rating"] = int(entry.get("link") or entry.get("link_rating") or 0)
            metadata.setdefault("summon_type", "link")
        if metadata:
            card["metadata"] = metadata
        if entry.get("equipped"):
            card["equipped"] = [to_card(eq) for eq in entry.get("equipped", [])]
        return card

    for key in ("hand", "deck", "gy", "banished", "extra"):
        zones[key] = [to_card(entry) for entry in state_data.get(key, [])]

    field = state_data.get("field", {})
    if isinstance(field, list):
        field = {"mz": field}

    for idx, entry in enumerate(field.get("mz", [])):
        if idx >= len(zones["field_zones"]["mz"]):
            break
        zones["field_zones"]["mz"][idx] = to_card(entry)
    for idx, entry in enumerate(field.get("emz", [])):
        if idx >= len(zones["field_zones"]["emz"]):
            break
        zones["field_zones"]["emz"][idx] = to_card(entry)
    for idx, entry in enumerate(field.get("stz", [])):
        if idx >= len(zones["field_zones"]["stz"]):
            break
        zones["field_zones"]["stz"][idx] = to_card(entry)
    for idx, entry in enumerate(field.get("fz", [])):
        if idx >= len(zones["field_zones"]["fz"]):
            break
        zones["field_zones"]["fz"][idx] = to_card(entry)

    return zones


def run_lua_hook(
    lua,
    cid: str,
    effect_key: str,
    hook_name: str,
    state: GameState,
    tp: int = 0,
) -> Optional[bool]:
    effect_idx = _effect_key_to_index(effect_key)
    if effect_idx is None:
        return None
    passcode = CID_TO_PASSCODE.get(str(cid))
    if not passcode:
        return None
    if not load_and_register_card(lua, passcode):
        return None
    if effect_idx >= len(_registered_effects):
        return None
    effect = _registered_effects[effect_idx]
    func = effect.get(f"{hook_name}_func")
    if func is None:
        return None

    # Bind handler to current card instance if possible.
    handler = None
    for card in state.get_cards_at_location(0x7F, tp):
        if card.cid == str(cid):
            handler = card
            break
    effect_obj = effect.get("effect_obj")
    if handler and effect_obj is not None:
        try:
            effect_obj["_handler"] = handler._lua_card
        except Exception:
            pass

    try:
        if hook_name == "condition":
            return bool(func(effect_obj, tp, None, tp, 0, None, 0, 1 - tp))
        if hook_name in {"cost", "target"}:
            return bool(func(effect_obj, tp, None, tp, 0, None, 0, 1 - tp, 0))
    except Exception:
        return False
    return None


def python_can_activate(case: dict) -> bool:
    from sim.state import GameState as PyGameState
    from sim.effects.registry import enumerate_effect_actions

    state_data = case.get("state", {})
    snapshot = {
        "zones": _build_python_snapshot(state_data),
        "phase": state_data.get("phase", "Main Phase 1"),
        "events": state_data.get("events", []),
        "opt_used": state_data.get("opt_used", {}),
        "pending_triggers": state_data.get("pending_triggers", []),
        "last_moved_to_gy": state_data.get("last_moved_to_gy", []),
    }
    state = PyGameState.from_snapshot(snapshot)
    cid = str(case.get("cid", ""))
    python_effect_id = case.get("python_effect_id")
    for action in enumerate_effect_actions(state):
        if action.cid != cid:
            continue
        if python_effect_id and action.effect_id != python_effect_id:
            continue
        return True
    return False


def verify_cases(cases_path: Path, verify_hooks: bool, verify_activation: bool, ci: bool) -> int:
    lua_dir = _resolve_lua_dir()
    if not lua_dir:
        print(f"{LUA_DIR_ENV} not set; skipping Lua ground-truth verification.")
        return 0

    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    lua = create_lua_runtime()
    mismatches = 0

    for case in cases:
        name = case.get("name", "unnamed")
        cid = str(case.get("cid", ""))
        effect_key = case.get("effect", "")
        tp = int(case.get("tp", 0))

        state = _build_lua_state(lua, case.get("state", {}))
        global _game_state
        _game_state = state

        lua_cond = run_lua_hook(lua, cid, effect_key, "condition", state, tp=tp)
        lua_cost = run_lua_hook(lua, cid, effect_key, "cost", state, tp=tp)
        lua_targ = run_lua_hook(lua, cid, effect_key, "target", state, tp=tp)

        if verify_hooks:
            print(f"\nCASE: {name}")
            print(f"  lua.condition: {lua_cond}")
            print(f"  lua.cost: {lua_cost}")
            print(f"  lua.target: {lua_targ}")

        lua_can = all(
            val is not False for val in [lua_cond, lua_cost, lua_targ] if val is not None
        )
        py_can = python_can_activate(case)

        if verify_activation:
            status = "OK" if lua_can == py_can else "MISMATCH"
            print(f"  lua_can={lua_can} py_can={py_can} => {status}")
            if status != "OK":
                mismatches += 1

    if ci and mismatches:
        return 1
    return 0


def test_engraver_conditions():
    """Test Engraver effect conditions with the Lua ground truth."""
    global _registered_effects, _game_state

    print("=" * 60)
    print("ENGRAVER LUA GROUND TRUTH TEST")
    print("=" * 60)

    # Create Lua runtime
    lua = create_lua_runtime()
    print("✓ Lua runtime created")

    # Load Engraver script (passcode 60764609)
    if not load_and_register_card(lua, "60764609"):
        print("✗ Failed to load Engraver script")
        return False
    print("✓ Engraver script loaded and effects registered")

    # Check registered effects
    print(f"\nRegistered effects: {len(_registered_effects)}")
    for i, eff in enumerate(_registered_effects):
        eff_type = eff.get('effect_type', 0)
        eff_range = eff.get('effect_range', 0)

        type_name = "IGNITION" if eff_type & 0x40 else "TRIGGER_O" if eff_type & 0x80 else "QUICK_O" if eff_type & 0x100 else f"0x{eff_type:x}"
        range_name = []
        if eff_range & 0x02: range_name.append("HAND")
        if eff_range & 0x04: range_name.append("MZONE")
        if eff_range & 0x10: range_name.append("GRAVE")

        print(f"  e{i+1}: type={type_name}, range={'+'.join(range_name) or '0x' + hex(eff_range)}")
        print(f"       has_cost={eff.get('has_cost')}, has_target={eff.get('has_target')}")

    # Now let's verify these match our verified_effects.json
    print("\n" + "=" * 60)
    print("COMPARISON WITH verified_effects.json")
    print("=" * 60)

    import json
    verified_path = Path("config/verified_effects.json")
    if verified_path.exists():
        verified = json.loads(verified_path.read_text())
        engraver = verified.get("20196", {})
        print(f"\nverified_effects.json for Engraver (CID 20196):")
        for eff in engraver.get("effects", []):
            print(f"  {eff['id']}: location={eff.get('location')}, cost={eff.get('cost', 'none')[:30]}...")

    # Verify effect locations match
    print("\n" + "=" * 60)
    print("LOCATION VERIFICATION")
    print("=" * 60)

    expected = [
        {"id": "e1", "location": "hand", "lua_range": 0x02},
        {"id": "e2", "location": "field", "lua_range": 0x04},
        {"id": "e3", "location": "gy", "lua_range": 0x10},
    ]

    all_match = True
    for i, exp in enumerate(expected):
        if i < len(_registered_effects):
            actual_range = _registered_effects[i].get('effect_range', 0)
            match = actual_range == exp['lua_range']
            status = "✓" if match else "✗"
            print(f"  {exp['id']}: expected {exp['location']} (0x{exp['lua_range']:02x}), got 0x{actual_range:02x} {status}")
            if not match:
                all_match = False
        else:
            print(f"  {exp['id']}: MISSING from Lua registration")
            all_match = False

    return all_match


def test_all_fiendsmith_cards():
    """Test all Fiendsmith cards we have Lua scripts for."""
    global _registered_effects

    print("=" * 70)
    print("FIENDSMITH CARD LUA GROUND TRUTH VERIFICATION")
    print("=" * 70)

    # Cards to test (passcode -> expected effects)
    # Note: Trigger effects (EVENT_TO_GRAVE etc) often have range=0x0
    # because they use SetCode(EVENT_*) instead of SetRange
    cards_to_test = [
        ("60764609", "Fiendsmith Engraver", [
            ("e1", "HAND", 0x02, "IGNITION"),
            ("e2", "MZONE", 0x04, "IGNITION"),
            ("e3", "GRAVE", 0x10, "IGNITION"),
        ]),
        ("98567237", "Fiendsmith's Tract", [
            ("e1", "activate", None, "ACTIVATE"),  # Spell activation
            ("e2", "GRAVE", 0x10, "IGNITION"),
        ]),
        ("2463794", "Fiendsmith's Requiem", [
            ("e1", "MZONE", 0x04, "QUICK_O"),  # Tribute to SS
            ("e2", "MZONE+GRAVE", 0x14, "IGNITION"),  # Equip from field or GY
        ]),
        ("82135803", "Fiendsmith's Desirae", [
            ("e1", "MZONE", 0x04, "QUICK_O"),  # Negate
            ("e2", "trigger", 0x00, "TRIGGER_O"),  # GY trigger (uses EVENT_TO_GRAVE)
        ]),
        ("46640168", "Fiendsmith's Lacrima", [
            ("e1", "MZONE", 0x04, "FIELD"),  # ATK reduction (continuous)
            ("e2", "trigger", 0x00, "TRIGGER_O"),  # On summon (EVENT_SPSUMMON_SUCCESS)
            ("e3", "trigger", 0x00, "TRIGGER_O"),  # GY trigger (EVENT_TO_GRAVE)
        ]),
        ("49867899", "Fiendsmith's Sequence", [
            ("e1", "MZONE", 0x04, "IGNITION"),  # GY Fusion
            ("e2", "MZONE+GRAVE", 0x14, "IGNITION"),  # Equip
        ]),
    ]

    lua = create_lua_runtime()
    results = []

    for passcode, name, expected_effects in cards_to_test:
        print(f"\n{'─' * 70}")
        print(f"Testing: {name} (passcode: {passcode})")
        print("─" * 70)

        _registered_effects = []

        if not load_and_register_card(lua, passcode):
            print(f"  ✗ Failed to load script")
            results.append((name, False, "Script load failed"))
            continue

        print(f"  ✓ Loaded, {len(_registered_effects)} effects registered")

        # Display effect details
        all_match = True
        for i, eff in enumerate(_registered_effects):
            eff_type = eff.get('effect_type', 0)
            eff_range = eff.get('effect_range', 0)

            # Decode type
            if eff_type & 0x40:
                type_name = "IGNITION"
            elif eff_type & 0x80:
                type_name = "TRIGGER_O"
            elif eff_type & 0x100:
                type_name = "QUICK_O"
            elif eff_type & 0x10:
                type_name = "ACTIVATE"
            elif eff_type & 0x01:
                type_name = "SINGLE"
            elif eff_type & 0x02:
                type_name = "FIELD"
            else:
                type_name = f"0x{eff_type:x}"

            # Decode range
            range_parts = []
            if eff_range & 0x02: range_parts.append("HAND")
            if eff_range & 0x04: range_parts.append("MZONE")
            if eff_range & 0x08: range_parts.append("SZONE")
            if eff_range & 0x10: range_parts.append("GRAVE")
            if eff_range & 0x20: range_parts.append("REMOVED")
            range_name = "+".join(range_parts) if range_parts else f"0x{eff_range:x}"

            # Check if we have expected for this effect
            if i < len(expected_effects):
                exp_id, exp_range, exp_code, exp_type = expected_effects[i]
                if exp_code is not None:
                    match = eff_range == exp_code
                    status = "✓" if match else "✗"
                    if not match:
                        all_match = False
                else:
                    status = "~"  # Can't verify exactly (e.g., spell activation, trigger)
            else:
                status = "?"
                exp_id = f"e{i}"

            print(f"    {exp_id}: type={type_name:12} range={range_name:15} {status}")

        results.append((name, all_match, f"{len(_registered_effects)} effects"))

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nPassed: {passed}/{len(results)}")
    for name, ok, details in results:
        status = "✓" if ok else "✗"
        print(f"  {status} {name}: {details}")

    return all(ok for _, ok, _ in results)


def compare_lua_vs_python():
    """
    Compare Lua effect locations against actual Python enumerate behavior.

    This is the key test: if Python enumerates from the wrong location,
    this comparison will catch it.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    from sim.state import GameState as PyGameState, CardInstance as PyCardState, FieldZones
    from sim.effects.registry import enumerate_effect_actions

    print("=" * 70)
    print("LUA vs PYTHON EFFECT LOCATION COMPARISON")
    print("=" * 70)

    lua = create_lua_runtime()

    # Test Engraver specifically
    print("\n" + "─" * 70)
    print("Testing: Fiendsmith Engraver (CID 20196)")
    print("─" * 70)

    # Load Lua and get expected locations
    global _registered_effects
    _registered_effects = []
    load_and_register_card(lua, "60764609")

    lua_effects = []
    for i, eff in enumerate(_registered_effects):
        eff_range = eff.get('effect_range', 0)
        locations = []
        if eff_range & 0x02: locations.append("HAND")
        if eff_range & 0x04: locations.append("FIELD")
        if eff_range & 0x10: locations.append("GY")
        if eff_range & 0x20: locations.append("BANISHED")
        lua_effects.append({
            "id": f"e{i+1}",
            "range": eff_range,
            "locations": locations
        })

    print(f"\nLua registered {len(lua_effects)} effects:")
    for eff in lua_effects:
        print(f"  {eff['id']}: {'+'.join(eff['locations']) or 'NONE'} (0x{eff['range']:02x})")

    # Now test Python - create states with Engraver in different locations
    print("\nPython enumerate_actions() behavior:")

    # Helper to create empty field zones
    def empty_field():
        return FieldZones(
            mz=[None, None, None, None, None],
            stz=[None, None, None, None, None],
            fz=[None],
            emz=[None, None]
        )

    # Test e1: Should enumerate from HAND
    print("\n  Testing e1 (search from hand):")
    state_hand = PyGameState(
        hand=[
            PyCardState(cid="20196", name="Fiendsmith Engraver",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 6}),
        ],
        deck=[
            PyCardState(cid="20240", name="Fiendsmith's Tract", metadata={}),
        ],
        gy=[],
        banished=[],
        extra=[],
        field=empty_field(),
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_hand = [a for a in enumerate_effect_actions(state_hand)
                   if a.cid == "20196" and "search" in a.effect_id.lower()]
    e1_from_hand = len(actions_hand) > 0
    print(f"    Engraver in HAND → enumerates search: {e1_from_hand}")

    # Test e3: Should enumerate from GY (but our bug makes it enumerate from HAND)
    print("\n  Testing e3 (GY revive):")

    # First test: Engraver in GY (correct location per Lua)
    state_gy = PyGameState(
        hand=[],
        deck=[],
        gy=[
            PyCardState(cid="20196", name="Fiendsmith Engraver",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 6}),
            PyCardState(cid="8092", name="Fabled Lurrie",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 1}),
        ],
        banished=[],
        extra=[],
        field=empty_field(),
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_gy = [a for a in enumerate_effect_actions(state_gy)
                 if a.cid == "20196" and "gy_shuffle" in a.effect_id.lower()]
    e3_from_gy = len(actions_gy) > 0
    print(f"    Engraver in GY → enumerates revive: {e3_from_gy}")

    # Second test: Engraver in HAND (wrong location - should NOT enumerate e3)
    state_hand_wrong = PyGameState(
        hand=[
            PyCardState(cid="20196", name="Fiendsmith Engraver",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 6}),
            PyCardState(cid="8092", name="Fabled Lurrie",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 1}),
        ],
        deck=[],
        gy=[],
        banished=[],
        extra=[],
        field=empty_field(),
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_hand_wrong = [a for a in enumerate_effect_actions(state_hand_wrong)
                         if a.cid == "20196" and "gy_shuffle" in a.effect_id.lower()]
    e3_from_hand_wrongly = len(actions_hand_wrong) > 0
    print(f"    Engraver in HAND → enumerates revive: {e3_from_hand_wrongly} (SHOULD BE False!)")

    # Comparison
    print("\n" + "=" * 70)
    print("COMPARISON RESULTS")
    print("=" * 70)

    results = []

    # e1: Lua says HAND, Python should enumerate from HAND
    e1_lua = "HAND" in lua_effects[0]['locations']
    e1_py = e1_from_hand
    e1_match = e1_lua == e1_py
    results.append(("e1", "HAND", e1_lua, e1_py, e1_match))

    # e3: Lua says GY, Python should ONLY enumerate from GY
    e3_lua_loc = "GY" in lua_effects[2]['locations'] if len(lua_effects) > 2 else False
    e3_py_correct = e3_from_gy and not e3_from_hand_wrongly
    e3_match = e3_lua_loc and e3_py_correct
    results.append(("e3", "GY", e3_lua_loc, e3_py_correct, e3_match))

    print(f"\n{'Effect':<8} {'Lua Location':<15} {'Python Correct?':<18} {'Match?'}")
    print("─" * 55)
    for eff_id, lua_loc, lua_ok, py_ok, match in results:
        status = "✓" if match else "✗ MISMATCH"
        print(f"{eff_id:<8} {lua_loc:<15} {str(py_ok):<18} {status}")

    if e3_from_hand_wrongly:
        print("\n" + "!" * 70)
        print("BUG DETECTED: e3 enumerates from HAND but Lua says it should be GY!")
        print("!" * 70)
        return False

    all_match = all(m for _, _, _, _, m in results)
    if all_match:
        print("\n✓ All effects enumerate from correct locations")

    return all_match


def full_comparison_report():
    """
    Generate a comprehensive comparison report for ALL cards.

    Compares:
    - Lua effect locations
    - verified_effects.json documented locations
    - Python enumerate behavior
    """
    import sys
    import json
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    from sim.state import GameState as PyGameState, CardInstance as PyCardState, FieldZones
    from sim.effects.registry import enumerate_effect_actions, EFFECT_REGISTRY

    print("=" * 70)
    print("FULL GROUND TRUTH COMPARISON REPORT")
    print("=" * 70)

    lua = create_lua_runtime()

    # Load verified_effects.json
    verified_path = Path("config/verified_effects.json")
    verified = json.loads(verified_path.read_text()) if verified_path.exists() else {}

    # All passcodes we have Lua for
    all_passcodes = {
        "60764609": ("20196", "Fiendsmith Engraver"),
        "98567237": ("20240", "Fiendsmith's Tract"),
        "2463794": ("20225", "Fiendsmith's Requiem"),
        "82135803": ("20215", "Fiendsmith's Desirae"),
        "46640168": ("20214", "Fiendsmith's Lacrima"),
        "49867899": ("20238", "Fiendsmith's Sequence"),
        "32991300": ("20521", "Fiendsmith's Agnumday"),
        "11464648": ("20774", "Fiendsmith's Rextremende"),
        "35552985": ("20241", "Fiendsmith's Sanct"),
        "99989863": ("20251", "Fiendsmith in Paradise"),
        "26434972": ("20816", "Fiendsmith Kyrie"),
        "28803166": ("20490", "Lacrima the Crimson Tears"),
    }

    # Location mapping
    LUA_TO_NAME = {0x02: "hand", 0x04: "field", 0x10: "gy", 0x20: "banished", 0x14: "field/gy"}

    global _registered_effects
    total_effects = 0
    matching = 0
    mismatches = []

    for passcode, (cid, name) in all_passcodes.items():
        _registered_effects = []

        if not load_and_register_card(lua, passcode):
            print(f"\nCID {cid} ({name}): SCRIPT LOAD FAILED")
            continue

        print(f"\nCID {cid} ({name}):")

        # Get verified_effects.json entry
        json_entry = verified.get(cid, {})
        json_effects = json_entry.get("effects", [])

        for i, lua_eff in enumerate(_registered_effects):
            total_effects += 1
            lua_range = lua_eff.get('effect_range', 0)

            # Determine Lua location name
            lua_loc = LUA_TO_NAME.get(lua_range, f"0x{lua_range:x}")
            if lua_range == 0:
                lua_loc = "trigger"  # Trigger effects use EVENT_*, not SetRange

            # Get JSON location
            json_loc = "?"
            if i < len(json_effects):
                json_loc = json_effects[i].get("location", "?")

            # Normalize for comparison
            lua_norm = lua_loc.lower().replace("/", "_")
            json_norm = json_loc.lower().replace("/", "_").replace("field", "mzone")

            # For triggers, they can activate from anywhere when the event occurs
            # Common trigger events: on-summon (field), to-GY (gy), etc.
            if lua_loc == "trigger":
                # Trigger effects are OK if JSON indicates the card's context
                # On-summon triggers technically activate from field
                # GY triggers technically activate from GY
                match = json_loc in ["gy", "trigger", "trap", "spell", "field"]
            elif lua_loc == "field/gy":
                # Field/GY effects can activate from either
                match = json_loc in ["field/gy", "field_gy", "field", "gy"]
            elif lua_norm == json_norm or (lua_loc == "field" and json_loc in ["field", "mzone"]):
                match = True
            else:
                match = False

            status = "✓" if match else "✗"
            if not match:
                mismatches.append((cid, name, f"e{i+1}", lua_loc, json_loc))
            else:
                matching += 1

            print(f"  e{i+1}: Lua={lua_loc:<12} JSON={json_loc:<12} {status}")

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"\nTotal effects: {total_effects}")
    print(f"Matching: {matching}")
    print(f"Mismatches: {len(mismatches)}")

    if mismatches:
        print("\nMISMATCHES:")
        for cid, name, eff_id, lua, json in mismatches:
            print(f"  {cid} ({name}) {eff_id}: Lua={lua}, JSON={json}")

    return len(mismatches) == 0


def verify_conditions():
    """
    Verify CONDITIONS and COSTS for 5 core Fiendsmith effects.

    Creates test game states and verifies Python enumerate behavior matches
    the expected Lua conditions documented in verified_effects.json.

    Test Cases:
    1. Engraver e3: Needs OTHER LIGHT Fiend in GY (not itself)
    2. Tract e2: Needs Tract in GY + LIGHT Fiends for fusion materials
    3. Requiem e2: Needs non-Link LIGHT Fiend on field to target
    4. Lacrima CT e1: Needs Fiendsmith card in deck to send (trigger on summon)
    5. Desirae e1: Needs equipped cards with Link Rating > 0
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    from sim.state import GameState as PyGameState, CardInstance as PyCardState, FieldZones
    from sim.effects.registry import enumerate_effect_actions

    print("=" * 70)
    print("CONDITION & COST VERIFICATION")
    print("=" * 70)

    def empty_field():
        return FieldZones(
            mz=[None, None, None, None, None],
            stz=[None, None, None, None, None],
            fz=[None],
            emz=[None, None]
        )

    results = []

    # ================================================================
    # TEST 1: Engraver e3 - needs OTHER LIGHT Fiend in GY
    # ================================================================
    print("\n" + "-" * 70)
    print("TEST 1: Engraver e3 (GY revive)")
    print("  Condition: Engraver in GY + OTHER LIGHT Fiend in GY")
    print("-" * 70)

    # Case 1a: Engraver in GY WITH another LIGHT Fiend -> SHOULD enumerate
    state_1a = PyGameState(
        hand=[],
        deck=[],
        gy=[
            PyCardState(cid="20196", name="Fiendsmith Engraver",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 6}),
            PyCardState(cid="8092", name="Fabled Lurrie",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 1}),
        ],
        banished=[],
        extra=[],
        field=empty_field(),
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_1a = [a for a in enumerate_effect_actions(state_1a)
                  if a.cid == "20196" and "gy_shuffle" in a.effect_id.lower()]
    case_1a_pass = len(actions_1a) > 0
    print(f"  Case 1a: Engraver+Lurrie in GY -> enumerates: {case_1a_pass} (expected: True)")
    results.append(("Engraver e3 - with other LIGHT Fiend", case_1a_pass, True))

    # Case 1b: Engraver in GY ALONE (no other LIGHT Fiend) -> should NOT enumerate
    state_1b = PyGameState(
        hand=[],
        deck=[],
        gy=[
            PyCardState(cid="20196", name="Fiendsmith Engraver",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 6}),
        ],
        banished=[],
        extra=[],
        field=empty_field(),
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_1b = [a for a in enumerate_effect_actions(state_1b)
                  if a.cid == "20196" and "gy_shuffle" in a.effect_id.lower()]
    case_1b_pass = len(actions_1b) == 0
    print(f"  Case 1b: Engraver ALONE in GY -> enumerates: {len(actions_1b) > 0} (expected: False)")
    results.append(("Engraver e3 - alone in GY", case_1b_pass, True))

    # Case 1c: Two Engravers in GY (can use one as cost for other)
    state_1c = PyGameState(
        hand=[],
        deck=[],
        gy=[
            PyCardState(cid="20196", name="Fiendsmith Engraver",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 6}),
            PyCardState(cid="20196", name="Fiendsmith Engraver",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 6}),
        ],
        banished=[],
        extra=[],
        field=empty_field(),
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_1c = [a for a in enumerate_effect_actions(state_1c)
                  if a.cid == "20196" and "gy_shuffle" in a.effect_id.lower()]
    case_1c_pass = len(actions_1c) > 0
    print(f"  Case 1c: Two Engravers in GY -> enumerates: {case_1c_pass} (expected: True)")
    results.append(("Engraver e3 - two copies in GY", case_1c_pass, True))

    # ================================================================
    # TEST 2: Tract e2 - needs Tract in GY + fusion materials
    # ================================================================
    print("\n" + "-" * 70)
    print("TEST 2: Tract e2 (GY banish fusion)")
    print("  Condition: Tract in GY + valid fusion materials on field/hand")
    print("-" * 70)

    # Case 2a: Tract in GY with enough LIGHT Fiends in hand -> SHOULD enumerate
    field_2a = empty_field()
    state_2a = PyGameState(
        hand=[
            PyCardState(cid="20196", name="Fiendsmith Engraver",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 6}),
            PyCardState(cid="8092", name="Fabled Lurrie",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 1}),
        ],
        deck=[],
        gy=[
            PyCardState(cid="20240", name="Fiendsmith's Tract", metadata={}),
        ],
        banished=[],
        extra=[
            PyCardState(cid="20214", name="Fiendsmith's Lacrima",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 8}),
        ],
        field=field_2a,
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_2a = [a for a in enumerate_effect_actions(state_2a)
                  if a.cid == "20240" and "gy_banish_fuse" in a.effect_id.lower()]
    case_2a_pass = len(actions_2a) > 0
    print(f"  Case 2a: Tract in GY + 2 LIGHT Fiends in hand -> enumerates: {case_2a_pass} (expected: True)")
    results.append(("Tract e2 - with valid materials", case_2a_pass, True))

    # Case 2b: Tract in GY with only 1 material -> should NOT enumerate (need 2 for Lacrima)
    state_2b = PyGameState(
        hand=[
            PyCardState(cid="20196", name="Fiendsmith Engraver",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 6}),
        ],
        deck=[],
        gy=[
            PyCardState(cid="20240", name="Fiendsmith's Tract", metadata={}),
        ],
        banished=[],
        extra=[
            PyCardState(cid="20214", name="Fiendsmith's Lacrima",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 8}),
        ],
        field=empty_field(),
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_2b = [a for a in enumerate_effect_actions(state_2b)
                  if a.cid == "20240" and "gy_banish_fuse" in a.effect_id.lower()]
    case_2b_pass = len(actions_2b) == 0
    print(f"  Case 2b: Tract in GY + only 1 material -> enumerates: {len(actions_2b) > 0} (expected: False)")
    results.append(("Tract e2 - insufficient materials", case_2b_pass, True))

    # ================================================================
    # TEST 3: Requiem e2 - needs non-Link LIGHT Fiend on field
    # ================================================================
    print("\n" + "-" * 70)
    print("TEST 3: Requiem e2 (equip to LIGHT Fiend)")
    print("  Condition: Requiem in GY/field + non-Link LIGHT Fiend on field")
    print("-" * 70)

    # Case 3a: Requiem in GY with Lacrima (Fusion) on field -> SHOULD enumerate
    field_3a = empty_field()
    field_3a.mz[0] = PyCardState(cid="20214", name="Fiendsmith's Lacrima",
                                  metadata={"attribute": "LIGHT", "race": "FIEND",
                                           "summon_type": "fusion"})
    state_3a = PyGameState(
        hand=[],
        deck=[],
        gy=[
            PyCardState(cid="20225", name="Fiendsmith's Requiem",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "link_rating": 2}),
        ],
        banished=[],
        extra=[],
        field=field_3a,
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_3a = [a for a in enumerate_effect_actions(state_3a)
                  if a.cid == "20225" and "equip" in a.effect_id.lower()]
    case_3a_pass = len(actions_3a) > 0
    print(f"  Case 3a: Requiem in GY + Lacrima (Fusion) on field -> enumerates: {case_3a_pass} (expected: True)")
    results.append(("Requiem e2 - with valid target", case_3a_pass, True))

    # Case 3b: Requiem in GY with Sequence (Link) on field -> should NOT enumerate
    field_3b = empty_field()
    field_3b.emz[0] = PyCardState(cid="20238", name="Fiendsmith's Sequence",
                                   metadata={"attribute": "LIGHT", "race": "FIEND",
                                            "summon_type": "link", "link_rating": 2})
    state_3b = PyGameState(
        hand=[],
        deck=[],
        gy=[
            PyCardState(cid="20225", name="Fiendsmith's Requiem",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "link_rating": 2}),
        ],
        banished=[],
        extra=[],
        field=field_3b,
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_3b = [a for a in enumerate_effect_actions(state_3b)
                  if a.cid == "20225" and "equip" in a.effect_id.lower()]
    case_3b_pass = len(actions_3b) == 0
    print(f"  Case 3b: Requiem in GY + Sequence (Link) on field -> enumerates: {len(actions_3b) > 0} (expected: False)")
    results.append(("Requiem e2 - Link monster (invalid target)", case_3b_pass, True))

    # Case 3c: Requiem in GY but no monsters on field
    state_3c = PyGameState(
        hand=[],
        deck=[],
        gy=[
            PyCardState(cid="20225", name="Fiendsmith's Requiem",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "link_rating": 2}),
        ],
        banished=[],
        extra=[],
        field=empty_field(),
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_3c = [a for a in enumerate_effect_actions(state_3c)
                  if a.cid == "20225" and "equip" in a.effect_id.lower()]
    case_3c_pass = len(actions_3c) == 0
    print(f"  Case 3c: Requiem in GY + empty field -> enumerates: {len(actions_3c) > 0} (expected: False)")
    results.append(("Requiem e2 - no targets on field", case_3c_pass, True))

    # ================================================================
    # TEST 4: Lacrima CT e1 - trigger on summon, needs Fiendsmith in deck
    # ================================================================
    print("\n" + "-" * 70)
    print("TEST 4: Lacrima CT e1 (send Fiendsmith from deck)")
    print("  Condition: Lacrima CT on field (just summoned) + Fiendsmith in deck")
    print("-" * 70)

    # Case 4a: Lacrima CT on field with pending summon trigger + Fiendsmith in deck
    field_4a = empty_field()
    field_4a.mz[0] = PyCardState(cid="20490", name="Lacrima the Crimson Tears",
                                  metadata={"attribute": "LIGHT", "race": "FIEND", "level": 4})
    state_4a = PyGameState(
        hand=[],
        deck=[
            PyCardState(cid="20240", name="Fiendsmith's Tract", metadata={}),
        ],
        gy=[],
        banished=[],
        extra=[],
        field=field_4a,
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=["SUMMON:20490"]
    )
    actions_4a = [a for a in enumerate_effect_actions(state_4a)
                  if a.cid == "20490" and "send_fiendsmith" in a.effect_id.lower()]
    case_4a_pass = len(actions_4a) > 0
    print(f"  Case 4a: Lacrima CT summoned + Fiendsmith in deck -> enumerates: {case_4a_pass} (expected: True)")
    results.append(("Lacrima CT e1 - with trigger and target", case_4a_pass, True))

    # Case 4b: Lacrima CT on field but NO pending trigger (not just summoned)
    field_4b = empty_field()
    field_4b.mz[0] = PyCardState(cid="20490", name="Lacrima the Crimson Tears",
                                  metadata={"attribute": "LIGHT", "race": "FIEND", "level": 4})
    state_4b = PyGameState(
        hand=[],
        deck=[
            PyCardState(cid="20240", name="Fiendsmith's Tract", metadata={}),
        ],
        gy=[],
        banished=[],
        extra=[],
        field=field_4b,
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]  # No summon trigger
    )
    actions_4b = [a for a in enumerate_effect_actions(state_4b)
                  if a.cid == "20490" and "send_fiendsmith" in a.effect_id.lower()]
    case_4b_pass = len(actions_4b) == 0
    print(f"  Case 4b: Lacrima CT on field (no trigger) -> enumerates: {len(actions_4b) > 0} (expected: False)")
    results.append(("Lacrima CT e1 - no summon trigger", case_4b_pass, True))

    # Case 4c: Lacrima CT summoned but no Fiendsmith in deck
    field_4c = empty_field()
    field_4c.mz[0] = PyCardState(cid="20490", name="Lacrima the Crimson Tears",
                                  metadata={"attribute": "LIGHT", "race": "FIEND", "level": 4})
    state_4c = PyGameState(
        hand=[],
        deck=[
            PyCardState(cid="8092", name="Fabled Lurrie",
                       metadata={"attribute": "LIGHT", "race": "FIEND", "level": 1}),
        ],
        gy=[],
        banished=[],
        extra=[],
        field=field_4c,
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=["SUMMON:20490"]
    )
    actions_4c = [a for a in enumerate_effect_actions(state_4c)
                  if a.cid == "20490" and "send_fiendsmith" in a.effect_id.lower()]
    case_4c_pass = len(actions_4c) == 0
    print(f"  Case 4c: Lacrima CT summoned + no Fiendsmith in deck -> enumerates: {len(actions_4c) > 0} (expected: False)")
    results.append(("Lacrima CT e1 - no valid target in deck", case_4c_pass, True))

    # ================================================================
    # TEST 5: Desirae e1 - needs equipped Link monsters with rating > 0
    # ================================================================
    print("\n" + "-" * 70)
    print("TEST 5: Desirae e1 (negate effect)")
    print("  Condition: Desirae on field + equipped Link monsters with total rating > 0")
    print("-" * 70)

    # Case 5a: Desirae on field with Requiem equipped (Link-2) -> SHOULD enumerate
    field_5a = empty_field()
    desirae_5a = PyCardState(cid="20215", name="Fiendsmith's Desirae",
                              metadata={"attribute": "LIGHT", "race": "FIEND",
                                       "summon_type": "fusion"})
    desirae_5a.equipped = [
        PyCardState(cid="20225", name="Fiendsmith's Requiem",
                   metadata={"attribute": "LIGHT", "race": "FIEND", "link_rating": 2,
                            "summon_type": "link"})
    ]
    field_5a.mz[0] = desirae_5a
    state_5a = PyGameState(
        hand=[],
        deck=[],
        gy=[],
        banished=[],
        extra=[],
        field=field_5a,
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_5a = [a for a in enumerate_effect_actions(state_5a)
                  if a.cid == "20215" and "negate" in a.effect_id.lower()]
    case_5a_pass = len(actions_5a) > 0
    print(f"  Case 5a: Desirae + Requiem (Link-2) equipped -> enumerates: {case_5a_pass} (expected: True)")
    results.append(("Desirae e1 - with equipped Link", case_5a_pass, True))

    # Case 5b: Desirae on field with NO equipped cards -> should NOT enumerate
    field_5b = empty_field()
    desirae_5b = PyCardState(cid="20215", name="Fiendsmith's Desirae",
                              metadata={"attribute": "LIGHT", "race": "FIEND",
                                       "summon_type": "fusion"})
    field_5b.mz[0] = desirae_5b
    state_5b = PyGameState(
        hand=[],
        deck=[],
        gy=[],
        banished=[],
        extra=[],
        field=field_5b,
        turn_number=1,
        phase="Main Phase 1",
        opt_used={},
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_5b = [a for a in enumerate_effect_actions(state_5b)
                  if a.cid == "20215" and "negate" in a.effect_id.lower()]
    case_5b_pass = len(actions_5b) == 0
    print(f"  Case 5b: Desirae with no equipped cards -> enumerates: {len(actions_5b) > 0} (expected: False)")
    results.append(("Desirae e1 - no equipped cards", case_5b_pass, True))

    # Case 5c: Desirae with negates already used = equipped Link rating
    field_5c = empty_field()
    desirae_5c = PyCardState(cid="20215", name="Fiendsmith's Desirae",
                              metadata={"attribute": "LIGHT", "race": "FIEND",
                                       "summon_type": "fusion"})
    desirae_5c.equipped = [
        PyCardState(cid="20225", name="Fiendsmith's Requiem",
                   metadata={"attribute": "LIGHT", "race": "FIEND", "link_rating": 2,
                            "summon_type": "link"})
    ]
    field_5c.mz[0] = desirae_5c
    state_5c = PyGameState(
        hand=[],
        deck=[],
        gy=[],
        banished=[],
        extra=[],
        field=field_5c,
        turn_number=1,
        phase="Main Phase 1",
        opt_used={"20215:negates_used": 2},  # Already used 2 negates
        normal_summon_set_used=False,
        restrictions=[],
        events=[],
        last_moved_to_gy=[],
        pending_triggers=[]
    )
    actions_5c = [a for a in enumerate_effect_actions(state_5c)
                  if a.cid == "20215" and "negate" in a.effect_id.lower()]
    case_5c_pass = len(actions_5c) == 0
    print(f"  Case 5c: Desirae with 2 negates used (max) -> enumerates: {len(actions_5c) > 0} (expected: False)")
    results.append(("Desirae e1 - negates exhausted", case_5c_pass, True))

    # ================================================================
    # SUMMARY
    # ================================================================
    print("\n" + "=" * 70)
    print("CONDITION VERIFICATION SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, actual, expected in results if actual == expected)
    total = len(results)

    print(f"\nPassed: {passed}/{total}")
    print()

    for name, actual, expected in results:
        status = "PASS" if actual == expected else "FAIL"
        symbol = "✓" if status == "PASS" else "✗"
        print(f"  {symbol} {name}: {status}")

    mismatches = [(name, actual, expected) for name, actual, expected in results if actual != expected]
    if mismatches:
        print("\nMISMATCHES:")
        for name, actual, expected in mismatches:
            print(f"  {name}: got {actual}, expected {expected}")
        return False

    print("\n✓ All condition checks passed!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lua ground-truth verification")
    parser.add_argument("--all", action="store_true", help="Run all Fiendsmith card tests")
    parser.add_argument("--compare", action="store_true", help="Compare Lua vs Python effect locations")
    parser.add_argument("--report", action="store_true", help="Print full comparison report")
    parser.add_argument("--conditions", action="store_true", help="Verify conditions and costs")
    parser.add_argument(
        "--cases",
        default=str(Path("config") / "lua_ground_truth_cases.json"),
        help="Path to ground-truth case definitions",
    )
    parser.add_argument("--verify-hooks", action="store_true", help="Verify condition/cost/target hooks")
    parser.add_argument(
        "--verify-activation",
        action="store_true",
        help="Verify combined activation (cond && cost && target)",
    )
    parser.add_argument("--ci", action="store_true", help="Exit nonzero on mismatch")
    args = parser.parse_args()

    if args.verify_hooks or args.verify_activation:
        exit_code = verify_cases(Path(args.cases), args.verify_hooks, args.verify_activation, args.ci)
        raise SystemExit(exit_code)
    if args.all:
        test_all_fiendsmith_cards()
    elif args.compare:
        compare_lua_vs_python()
    elif args.report:
        full_comparison_report()
    elif args.conditions:
        verify_conditions()
    else:
        test_engraver_conditions()
