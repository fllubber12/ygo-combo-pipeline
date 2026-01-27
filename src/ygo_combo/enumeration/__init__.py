"""
Combo enumeration submodule.

Provides message parsing and response building for ygopro-core interaction.
"""

from .parsers import (
    # Binary readers
    read_u8, read_u16, read_u32, read_i32, read_u64,
    # Message parsers
    parse_idle,
    parse_select_card,
    parse_select_chain,
    parse_select_place,
    parse_select_unselect_card,
    parse_select_option,
    parse_select_tribute,
    parse_select_sum,
    # Helpers
    find_valid_tribute_combinations,
)

from .responses import (
    # Constants
    IDLE_RESPONSE_SUMMON,
    IDLE_RESPONSE_SPSUMMON,
    IDLE_RESPONSE_REPOSITION,
    IDLE_RESPONSE_MSET,
    IDLE_RESPONSE_SSET,
    IDLE_RESPONSE_ACTIVATE,
    IDLE_RESPONSE_TO_BATTLE,
    IDLE_RESPONSE_TO_END,
    # Response builders
    build_activate_response,
    build_summon_response,
    build_spsummon_response,
    build_mset_response,
    build_sset_response,
    build_reposition_response,
    build_pass_response,
    build_to_battle_response,
    build_select_card_response,
    build_cancel_select_card_response,
    build_decline_chain_response,
    build_chain_response,
    build_select_place_response,
    build_select_position_response,
    build_yesno_response,
    build_select_option_response,
    build_select_unselect_finish_response,
    build_select_unselect_card_response,
    build_select_tribute_response,
)

__all__ = [
    # Parsers
    'read_u8', 'read_u16', 'read_u32', 'read_i32', 'read_u64',
    'parse_idle', 'parse_select_card', 'parse_select_chain',
    'parse_select_place', 'parse_select_unselect_card',
    'parse_select_option', 'parse_select_tribute', 'parse_select_sum',
    'find_valid_tribute_combinations',
    # Response constants
    'IDLE_RESPONSE_SUMMON', 'IDLE_RESPONSE_SPSUMMON', 'IDLE_RESPONSE_REPOSITION',
    'IDLE_RESPONSE_MSET', 'IDLE_RESPONSE_SSET', 'IDLE_RESPONSE_ACTIVATE',
    'IDLE_RESPONSE_TO_BATTLE', 'IDLE_RESPONSE_TO_END',
    # Response builders
    'build_activate_response', 'build_summon_response', 'build_spsummon_response',
    'build_mset_response', 'build_sset_response', 'build_reposition_response',
    'build_pass_response', 'build_to_battle_response', 'build_select_card_response',
    'build_cancel_select_card_response', 'build_decline_chain_response',
    'build_chain_response', 'build_select_place_response',
    'build_select_position_response', 'build_yesno_response',
    'build_select_option_response', 'build_select_unselect_finish_response',
    'build_select_unselect_card_response', 'build_select_tribute_response',
]
