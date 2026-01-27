"""
Engine layer: ygopro-core interface.

This module provides:
- CFFI bindings to ygopro-core (bindings.py)
- Engine context and callbacks (interface.py)
- State representation classes (state.py)
- Path configuration (paths.py)
"""

from .bindings import (
    # Library access
    ffi, load_library, get_lib,
    # Location constants
    LOCATION_DECK, LOCATION_HAND, LOCATION_EXTRA, LOCATION_MZONE,
    LOCATION_GRAVE, LOCATION_SZONE, LOCATION_REMOVED, LOCATION_OVERLAY,
    LOCATION_ONFIELD,
    # Position constants
    POS_FACEUP_ATTACK, POS_FACEDOWN_ATTACK, POS_FACEUP_DEFENSE,
    POS_FACEDOWN_DEFENSE, POS_FACEUP, POS_FACEDOWN,
    # Query flags
    QUERY_CODE, QUERY_POSITION, QUERY_EQUIP_CARD, QUERY_ATTACK,
    QUERY_DEFENSE, QUERY_END,
    # Message constants (selection)
    MSG_SELECT_BATTLECMD, MSG_IDLE, MSG_SELECT_CARD, MSG_SELECT_CHAIN,
    MSG_SELECT_PLACE, MSG_SELECT_POSITION, MSG_SELECT_TRIBUTE,
    MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO, MSG_SELECT_OPTION,
    MSG_SELECT_COUNTER, MSG_SELECT_UNSELECT_CARD, MSG_SELECT_SUM,
    MSG_SORT_CARD, MSG_SELECT_DISFIELD,
    # Message constants (core)
    MSG_RETRY, MSG_HINT, MSG_WAITING, MSG_START, MSG_WIN,
    MSG_UPDATE_DATA, MSG_UPDATE_CARD,
    # Message constants (deck/hand)
    MSG_CONFIRM_DECKTOP, MSG_CONFIRM_CARDS, MSG_SHUFFLE_DECK, MSG_SHUFFLE_HAND,
    MSG_REFRESH_DECK, MSG_SWAP_GRAVE_DECK, MSG_SHUFFLE_SET_CARD, MSG_REVERSE_DECK,
    MSG_DECK_TOP, MSG_SHUFFLE_EXTRA,
    # Message constants (turn/phase)
    MSG_NEW_TURN, MSG_NEW_PHASE, MSG_CONFIRM_EXTRATOP,
    # Message constants (movement)
    MSG_MOVE, MSG_POS_CHANGE, MSG_SET, MSG_SWAP, MSG_FIELD_DISABLED,
    # Message constants (summoning)
    MSG_SUMMONING, MSG_SUMMONED, MSG_SPSUMMONING, MSG_SPSUMMONED,
    MSG_FLIPSUMMONING, MSG_FLIPSUMMONED,
    # Message constants (chain)
    MSG_CHAINING, MSG_CHAINED, MSG_CHAIN_SOLVING, MSG_CHAIN_SOLVED,
    MSG_CHAIN_END, MSG_CHAIN_NEGATED, MSG_CHAIN_DISABLED,
    # Message constants (selection feedback)
    MSG_CARD_SELECTED, MSG_RANDOM_SELECTED, MSG_BECOME_TARGET,
    # Message constants (LP/damage)
    MSG_DRAW, MSG_DAMAGE, MSG_RECOVER, MSG_EQUIP, MSG_LPUPDATE, MSG_UNEQUIP,
    MSG_CARD_TARGET, MSG_CANCEL_TARGET, MSG_PAY_LPCOST,
    MSG_ADD_COUNTER, MSG_REMOVE_COUNTER,
    # Message constants (battle)
    MSG_ATTACK, MSG_BATTLE, MSG_ATTACK_DISABLED,
    MSG_DAMAGE_STEP_START, MSG_DAMAGE_STEP_END,
    # Message constants (effects)
    MSG_MISSED_EFFECT, MSG_BE_CHAIN_TARGET, MSG_CREATE_RELATION, MSG_RELEASE_RELATION,
    # Message constants (random)
    MSG_TOSS_COIN, MSG_TOSS_DICE, MSG_ROCK_PAPER_SCISSORS, MSG_HAND_RES,
    # Message constants (announcements)
    MSG_ANNOUNCE_RACE, MSG_ANNOUNCE_ATTRIB, MSG_ANNOUNCE_CARD, MSG_ANNOUNCE_NUMBER,
    # Message constants (hints/UI)
    MSG_CARD_HINT, MSG_TAG_SWAP, MSG_RELOAD_FIELD, MSG_AI_NAME,
    MSG_SHOW_HINT, MSG_PLAYER_HINT, MSG_MATCH_KILL, MSG_CUSTOM_MSG, MSG_REMOVE_CARDS,
)

from .interface import (
    init_card_database, load_library as load_library_interface,
    preload_utility_scripts,
    py_card_reader, py_card_reader_done, py_script_reader, py_log_handler,
    get_card_name, set_lib,
)

from .state import (
    BoardSignature, IntermediateState, ActionSpec,
    evaluate_board_quality, BOSS_MONSTERS, INTERACTION_PIECES,
)

from .paths import (
    get_scripts_path, get_library_path,
    CDB_PATH, LOCKED_LIBRARY_PATH,
)

__all__ = [
    # Bindings
    'ffi', 'load_library', 'get_lib',
    # Location constants
    'LOCATION_DECK', 'LOCATION_HAND', 'LOCATION_EXTRA', 'LOCATION_MZONE',
    'LOCATION_GRAVE', 'LOCATION_SZONE', 'LOCATION_REMOVED', 'LOCATION_OVERLAY',
    'LOCATION_ONFIELD',
    # Position constants
    'POS_FACEUP_ATTACK', 'POS_FACEDOWN_ATTACK', 'POS_FACEUP_DEFENSE',
    'POS_FACEDOWN_DEFENSE', 'POS_FACEUP', 'POS_FACEDOWN',
    # Query flags
    'QUERY_CODE', 'QUERY_POSITION', 'QUERY_ATTACK', 'QUERY_DEFENSE', 'QUERY_END',
    # Interface
    'init_card_database', 'preload_utility_scripts',
    'py_card_reader', 'py_card_reader_done', 'py_script_reader', 'py_log_handler',
    'get_card_name', 'set_lib',
    # State
    'BoardSignature', 'IntermediateState', 'ActionSpec',
    'evaluate_board_quality', 'BOSS_MONSTERS', 'INTERACTION_PIECES',
    # Paths
    'get_scripts_path', 'get_library_path', 'CDB_PATH', 'LOCKED_LIBRARY_PATH',
]
