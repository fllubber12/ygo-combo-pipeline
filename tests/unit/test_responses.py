"""
Unit tests for enumeration/responses.py.

Tests the binary response builders that create messages for ygopro-core engine.
All functions are pure and deterministic, making them ideal for unit testing.
"""

import struct
import pytest
from src.ygo_combo.enumeration.responses import (
    # Constants
    IDLE_RESPONSE_SUMMON,
    IDLE_RESPONSE_SPSUMMON,
    IDLE_RESPONSE_REPOSITION,
    IDLE_RESPONSE_MSET,
    IDLE_RESPONSE_SSET,
    IDLE_RESPONSE_ACTIVATE,
    IDLE_RESPONSE_TO_BATTLE,
    IDLE_RESPONSE_TO_END,
    # Functions
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


class TestIdleResponseConstants:
    """Test that IDLE_RESPONSE_* constants have expected values."""

    def test_idle_response_values(self):
        """Constants should match ygopro-core field_processor.cpp values."""
        assert IDLE_RESPONSE_SUMMON == 0
        assert IDLE_RESPONSE_SPSUMMON == 1
        assert IDLE_RESPONSE_REPOSITION == 2
        assert IDLE_RESPONSE_MSET == 3
        assert IDLE_RESPONSE_SSET == 4
        assert IDLE_RESPONSE_ACTIVATE == 5
        assert IDLE_RESPONSE_TO_BATTLE == 6
        assert IDLE_RESPONSE_TO_END == 7


class TestIdleResponses:
    """Tests for MSG_IDLE response builders.

    Format: u32 with (index << 16) | action_type
    """

    def test_build_activate_response_index_0(self):
        """Activate effect at index 0."""
        value, data = build_activate_response(0)
        assert value == (0 << 16) | IDLE_RESPONSE_ACTIVATE
        assert value == 5  # 0 | 5 = 5
        assert len(data) == 4
        assert struct.unpack("<I", data)[0] == value

    def test_build_activate_response_index_3(self):
        """Activate effect at index 3."""
        value, data = build_activate_response(3)
        expected = (3 << 16) | IDLE_RESPONSE_ACTIVATE
        assert value == expected
        assert value == 0x30005  # 3 << 16 = 0x30000, | 5 = 0x30005
        assert struct.unpack("<I", data)[0] == expected

    def test_build_summon_response(self):
        """Normal summon at index 2."""
        value, data = build_summon_response(2)
        expected = (2 << 16) | IDLE_RESPONSE_SUMMON
        assert value == expected
        assert struct.unpack("<I", data)[0] == expected

    def test_build_spsummon_response(self):
        """Special summon at index 1."""
        value, data = build_spsummon_response(1)
        expected = (1 << 16) | IDLE_RESPONSE_SPSUMMON
        assert value == expected
        assert struct.unpack("<I", data)[0] == expected

    def test_build_mset_response(self):
        """Set monster at index 0."""
        value, data = build_mset_response(0)
        expected = (0 << 16) | IDLE_RESPONSE_MSET
        assert value == expected
        assert struct.unpack("<I", data)[0] == expected

    def test_build_sset_response(self):
        """Set spell/trap at index 4."""
        value, data = build_sset_response(4)
        expected = (4 << 16) | IDLE_RESPONSE_SSET
        assert value == expected
        assert struct.unpack("<I", data)[0] == expected

    def test_build_reposition_response(self):
        """Change position at index 1."""
        value, data = build_reposition_response(1)
        expected = (1 << 16) | IDLE_RESPONSE_REPOSITION
        assert value == expected
        assert struct.unpack("<I", data)[0] == expected

    def test_build_pass_response(self):
        """Pass (end main phase)."""
        value, data = build_pass_response()
        assert value == IDLE_RESPONSE_TO_END
        assert value == 7
        assert len(data) == 4
        assert struct.unpack("<I", data)[0] == IDLE_RESPONSE_TO_END

    def test_build_to_battle_response(self):
        """Go to battle phase."""
        value, data = build_to_battle_response()
        assert value == IDLE_RESPONSE_TO_BATTLE
        assert value == 6
        assert len(data) == 4
        assert struct.unpack("<I", data)[0] == IDLE_RESPONSE_TO_BATTLE


class TestSelectCardResponses:
    """Tests for MSG_SELECT_CARD response builders.

    Format: i32(cancel_flag) + u32(count) + count*u32(indices)
    """

    def test_build_select_card_response_single(self):
        """Select a single card."""
        indices, data = build_select_card_response([3])
        assert indices == [3]
        # 4 bytes cancel_flag + 4 bytes count + 4 bytes per index
        assert len(data) == 4 + 4 + 4

        cancel_flag = struct.unpack_from("<i", data, 0)[0]
        count = struct.unpack_from("<I", data, 4)[0]
        idx0 = struct.unpack_from("<I", data, 8)[0]

        assert cancel_flag == 0  # Not canceling
        assert count == 1
        assert idx0 == 3

    def test_build_select_card_response_multiple(self):
        """Select multiple cards."""
        indices, data = build_select_card_response([0, 2, 5])
        assert indices == [0, 2, 5]
        assert len(data) == 4 + 4 + 4 * 3  # 20 bytes

        cancel_flag = struct.unpack_from("<i", data, 0)[0]
        count = struct.unpack_from("<I", data, 4)[0]
        idx0 = struct.unpack_from("<I", data, 8)[0]
        idx1 = struct.unpack_from("<I", data, 12)[0]
        idx2 = struct.unpack_from("<I", data, 16)[0]

        assert cancel_flag == 0
        assert count == 3
        assert idx0 == 0
        assert idx1 == 2
        assert idx2 == 5

    def test_build_select_card_response_empty(self):
        """Select zero cards (edge case)."""
        indices, data = build_select_card_response([])
        assert indices == []
        assert len(data) == 8  # Just cancel_flag + count

        cancel_flag = struct.unpack_from("<i", data, 0)[0]
        count = struct.unpack_from("<I", data, 4)[0]

        assert cancel_flag == 0
        assert count == 0

    def test_build_cancel_select_card_response(self):
        """Cancel card selection."""
        value, data = build_cancel_select_card_response()
        assert value == -1
        assert len(data) == 4
        assert struct.unpack("<i", data)[0] == -1


class TestChainResponses:
    """Tests for MSG_SELECT_CHAIN response builders.

    Format: i32 (chain index or -1 to decline)
    """

    def test_build_decline_chain_response(self):
        """Decline chain opportunity."""
        value, data = build_decline_chain_response()
        assert value == -1
        assert len(data) == 4
        assert struct.unpack("<i", data)[0] == -1

    def test_build_chain_response_index_0(self):
        """Activate chain at index 0."""
        value, data = build_chain_response(0)
        assert value == 0
        assert len(data) == 4
        assert struct.unpack("<i", data)[0] == 0

    def test_build_chain_response_index_2(self):
        """Activate chain at index 2."""
        value, data = build_chain_response(2)
        assert value == 2
        assert struct.unpack("<i", data)[0] == 2


class TestSelectPlaceResponse:
    """Tests for MSG_SELECT_PLACE response builder.

    Format: u8(player) + u8(location) + u8(sequence)
    """

    def test_build_select_place_response_monster_zone(self):
        """Select monster zone."""
        LOCATION_MZONE = 0x04
        data = build_select_place_response(player=0, location=LOCATION_MZONE, sequence=2)
        assert len(data) == 3

        player, location, sequence = struct.unpack("<BBB", data)
        assert player == 0
        assert location == 0x04
        assert sequence == 2

    def test_build_select_place_response_spell_zone(self):
        """Select spell/trap zone."""
        LOCATION_SZONE = 0x08
        data = build_select_place_response(player=0, location=LOCATION_SZONE, sequence=4)
        assert len(data) == 3

        player, location, sequence = struct.unpack("<BBB", data)
        assert player == 0
        assert location == 0x08
        assert sequence == 4

    def test_build_select_place_response_player_1(self):
        """Select zone for player 1."""
        data = build_select_place_response(player=1, location=0x04, sequence=0)
        player, location, sequence = struct.unpack("<BBB", data)
        assert player == 1

    def test_build_select_place_response_emz(self):
        """Select Extra Monster Zone (sequence 5 or 6)."""
        LOCATION_MZONE = 0x04
        data = build_select_place_response(player=0, location=LOCATION_MZONE, sequence=5)
        _, _, sequence = struct.unpack("<BBB", data)
        assert sequence == 5


class TestSelectPositionResponse:
    """Tests for MSG_SELECT_POSITION response builder.

    Format: u32 (position flags)
    """

    def test_build_select_position_response_attack(self):
        """Select face-up attack position."""
        POS_FACEUP_ATTACK = 0x1
        data = build_select_position_response(POS_FACEUP_ATTACK)
        assert len(data) == 4
        assert struct.unpack("<I", data)[0] == 0x1

    def test_build_select_position_response_defense(self):
        """Select face-up defense position."""
        POS_FACEUP_DEFENSE = 0x2
        data = build_select_position_response(POS_FACEUP_DEFENSE)
        assert struct.unpack("<I", data)[0] == 0x2

    def test_build_select_position_response_facedown_defense(self):
        """Select face-down defense position."""
        POS_FACEDOWN_DEFENSE = 0x8
        data = build_select_position_response(POS_FACEDOWN_DEFENSE)
        assert struct.unpack("<I", data)[0] == 0x8


class TestYesNoResponse:
    """Tests for MSG_SELECT_YESNO / MSG_SELECT_EFFECTYN response builder.

    Format: u32 (1 for yes, 0 for no)
    """

    def test_build_yesno_response_yes(self):
        """Select YES."""
        data = build_yesno_response(True)
        assert len(data) == 4
        assert struct.unpack("<I", data)[0] == 1

    def test_build_yesno_response_no(self):
        """Select NO."""
        data = build_yesno_response(False)
        assert len(data) == 4
        assert struct.unpack("<I", data)[0] == 0


class TestSelectOptionResponse:
    """Tests for MSG_SELECT_OPTION response builder.

    Format: u32 (0-indexed option number)
    """

    def test_build_select_option_response_0(self):
        """Select option 0."""
        data = build_select_option_response(0)
        assert len(data) == 4
        assert struct.unpack("<I", data)[0] == 0

    def test_build_select_option_response_3(self):
        """Select option 3."""
        data = build_select_option_response(3)
        assert struct.unpack("<I", data)[0] == 3


class TestSelectUnselectCardResponses:
    """Tests for MSG_SELECT_UNSELECT_CARD response builders.

    Format: i32 (card index or -1 to finish)
    """

    def test_build_select_unselect_finish_response(self):
        """Finish selection."""
        value, data = build_select_unselect_finish_response()
        assert value == -1
        assert len(data) == 4
        assert struct.unpack("<i", data)[0] == -1

    def test_build_select_unselect_card_response_index_0(self):
        """Select card at index 0."""
        value, data = build_select_unselect_card_response(0)
        assert value == 0
        assert len(data) == 4
        assert struct.unpack("<i", data)[0] == 0

    def test_build_select_unselect_card_response_index_5(self):
        """Select card at index 5."""
        value, data = build_select_unselect_card_response(5)
        assert value == 5
        assert struct.unpack("<i", data)[0] == 5


class TestSelectTributeResponse:
    """Tests for MSG_SELECT_TRIBUTE response builder.

    Format: i32(type=0) + u32(count) + count*u32(indices)
    """

    def test_build_select_tribute_response_single(self):
        """Tribute a single monster."""
        data = build_select_tribute_response([2])
        # 4 bytes type + 4 bytes count + 4 bytes per index
        assert len(data) == 4 + 4 + 4

        type_val = struct.unpack_from("<i", data, 0)[0]
        count = struct.unpack_from("<I", data, 4)[0]
        idx0 = struct.unpack_from("<I", data, 8)[0]

        assert type_val == 0  # type 0 = u32 indices
        assert count == 1
        assert idx0 == 2

    def test_build_select_tribute_response_double(self):
        """Tribute two monsters (for tribute summon)."""
        data = build_select_tribute_response([0, 3])
        assert len(data) == 4 + 4 + 4 * 2  # 16 bytes

        type_val = struct.unpack_from("<i", data, 0)[0]
        count = struct.unpack_from("<I", data, 4)[0]
        idx0 = struct.unpack_from("<I", data, 8)[0]
        idx1 = struct.unpack_from("<I", data, 12)[0]

        assert type_val == 0
        assert count == 2
        assert idx0 == 0
        assert idx1 == 3

    def test_build_select_tribute_response_triple(self):
        """Tribute three monsters (for Obelisk, etc.)."""
        data = build_select_tribute_response([1, 2, 4])
        assert len(data) == 4 + 4 + 4 * 3

        type_val = struct.unpack_from("<i", data, 0)[0]
        count = struct.unpack_from("<I", data, 4)[0]

        assert type_val == 0
        assert count == 3

    def test_build_select_tribute_response_empty(self):
        """Empty tribute list (edge case)."""
        data = build_select_tribute_response([])
        assert len(data) == 8  # Just type + count

        type_val = struct.unpack_from("<i", data, 0)[0]
        count = struct.unpack_from("<I", data, 4)[0]

        assert type_val == 0
        assert count == 0


class TestByteOrderAndSize:
    """Tests verifying little-endian byte order and correct sizes."""

    def test_all_u32_responses_are_little_endian(self):
        """All u32 responses should be little-endian."""
        # Build a response with a known value
        value, data = build_activate_response(1)  # (1 << 16) | 5 = 65541 = 0x10005

        # Little-endian: least significant byte first
        # 0x10005 = bytes [0x05, 0x00, 0x01, 0x00]
        assert data[0] == 0x05
        assert data[1] == 0x00
        assert data[2] == 0x01
        assert data[3] == 0x00

    def test_all_i32_negative_responses_are_little_endian(self):
        """Negative i32 responses should be little-endian two's complement."""
        _, data = build_cancel_select_card_response()  # -1

        # -1 in two's complement = 0xFFFFFFFF
        # Little-endian: [0xFF, 0xFF, 0xFF, 0xFF]
        assert data == b'\xff\xff\xff\xff'

    def test_select_place_is_packed_bytes(self):
        """SELECT_PLACE uses packed u8 values (no padding)."""
        data = build_select_place_response(1, 4, 2)
        # Should be exactly 3 bytes, no padding
        assert len(data) == 3
        assert data == bytes([1, 4, 2])
