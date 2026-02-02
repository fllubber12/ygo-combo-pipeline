"""
Tests for validated board state types.

These tests verify that the anti-hallucination guards work correctly:
- Unknown field names raise ValueError at construction
- Invalid attribute access raises AttributeError
- Frozen dataclasses prevent mutation
"""

import pytest
from dataclasses import FrozenInstanceError

from src.ygo_combo.engine.board_types import CardInfo, PlayerState, BoardState


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def valid_card_dict():
    """Valid card dictionary."""
    return {"code": 60764609, "name": "Fiendsmith Engraver", "atk": 2400, "def": 1800}


@pytest.fixture
def valid_player_dict():
    """Valid player state dictionary."""
    return {
        "hand": [{"code": 60764609, "name": "Fiendsmith Engraver"}],
        "monsters": [{"code": 29301450, "name": "S:P Little Knight", "atk": 1500, "def": 1500}],
        "spells": [],
        "graveyard": [],
        "banished": [],
        "extra": [],
    }


@pytest.fixture
def valid_board_dict(valid_player_dict):
    """Valid board state dictionary."""
    return {
        "player0": valid_player_dict,
        "player1": {
            "hand": [],
            "monsters": [],
            "spells": [],
            "graveyard": [],
            "banished": [],
            "extra": [],
        },
    }


@pytest.fixture
def valid_board(valid_board_dict):
    """Valid BoardState instance."""
    return BoardState.from_dict(valid_board_dict)


# =============================================================================
# CARDINFO TESTS
# =============================================================================

class TestCardInfo:
    """Tests for CardInfo dataclass."""

    def test_from_dict_valid(self, valid_card_dict):
        """Valid dict converts without error."""
        card = CardInfo.from_dict(valid_card_dict)
        assert card.code == 60764609
        assert card.name == "Fiendsmith Engraver"
        assert card.atk == 2400
        assert card.def_ == 1800

    def test_from_dict_minimal(self):
        """Minimal dict (just code and name) converts."""
        card = CardInfo.from_dict({"code": 12345, "name": "Test Card"})
        assert card.code == 12345
        assert card.name == "Test Card"
        assert card.atk is None
        assert card.def_ is None

    def test_from_dict_missing_code_raises(self):
        """Missing 'code' raises ValueError."""
        with pytest.raises(ValueError, match="missing required 'code'"):
            CardInfo.from_dict({"name": "Test"})

    def test_from_dict_missing_name_raises(self):
        """Missing 'name' raises ValueError."""
        with pytest.raises(ValueError, match="missing required 'name'"):
            CardInfo.from_dict({"code": 12345})

    def test_frozen_prevents_mutation(self, valid_card_dict):
        """Cannot mutate frozen CardInfo."""
        card = CardInfo.from_dict(valid_card_dict)
        with pytest.raises(FrozenInstanceError):
            card.code = 99999


# =============================================================================
# PLAYERSTATE TESTS
# =============================================================================

class TestPlayerState:
    """Tests for PlayerState dataclass."""

    def test_from_dict_valid(self, valid_player_dict):
        """Valid dict converts without error."""
        player = PlayerState.from_dict(valid_player_dict)
        assert len(player.hand) == 1
        assert len(player.monsters) == 1
        assert player.hand[0].code == 60764609
        assert player.monsters[0].name == "S:P Little Knight"

    def test_from_dict_unknown_zone_raises(self, valid_player_dict):
        """Unknown zone name raises ValueError with helpful message."""
        valid_player_dict["extra_monster_zone"] = []  # WRONG KEY
        with pytest.raises(ValueError) as exc:
            PlayerState.from_dict(valid_player_dict)
        assert "extra_monster_zone" in str(exc.value)
        assert "unknown zone" in str(exc.value).lower()

    def test_from_dict_monster_zone_typo_raises(self, valid_player_dict):
        """Common typo 'monster_zone' raises ValueError."""
        del valid_player_dict["monsters"]
        valid_player_dict["monster_zone"] = []  # WRONG - should be 'monsters'
        with pytest.raises(ValueError) as exc:
            PlayerState.from_dict(valid_player_dict)
        # Should mention both the unknown key and the missing key
        assert "monster_zone" in str(exc.value) or "monsters" in str(exc.value)

    def test_from_dict_missing_zone_raises(self, valid_player_dict):
        """Missing required zone raises ValueError."""
        del valid_player_dict["graveyard"]
        with pytest.raises(ValueError) as exc:
            PlayerState.from_dict(valid_player_dict)
        assert "graveyard" in str(exc.value)
        assert "missing" in str(exc.value).lower()

    def test_get_monster_codes(self, valid_player_dict):
        """get_monster_codes returns list of codes."""
        player = PlayerState.from_dict(valid_player_dict)
        codes = player.get_monster_codes()
        assert codes == [29301450]

    def test_has_monster(self, valid_player_dict):
        """has_monster checks monster zone."""
        player = PlayerState.from_dict(valid_player_dict)
        assert player.has_monster(29301450) is True
        assert player.has_monster(99999999) is False

    def test_has_card(self, valid_player_dict):
        """has_card checks all zones."""
        player = PlayerState.from_dict(valid_player_dict)
        assert player.has_card(60764609) is True  # In hand
        assert player.has_card(29301450) is True  # On field
        assert player.has_card(99999999) is False

    def test_frozen_prevents_mutation(self, valid_player_dict):
        """Cannot mutate frozen PlayerState."""
        player = PlayerState.from_dict(valid_player_dict)
        with pytest.raises(FrozenInstanceError):
            player.hand = ()


# =============================================================================
# BOARDSTATE TESTS
# =============================================================================

class TestBoardState:
    """Tests for BoardState dataclass."""

    def test_from_dict_valid(self, valid_board_dict):
        """Valid dict converts without error."""
        board = BoardState.from_dict(valid_board_dict)
        assert board.player0.hand[0].code == 60764609
        assert len(board.player1.monsters) == 0

    def test_from_dict_unknown_key_raises(self, valid_board_dict):
        """Unknown top-level key raises ValueError."""
        valid_board_dict["extra_monster_zone"] = []  # WRONG KEY
        with pytest.raises(ValueError) as exc:
            BoardState.from_dict(valid_board_dict)
        assert "extra_monster_zone" in str(exc.value)
        assert "NOT valid" in str(exc.value)

    def test_from_dict_missing_player_raises(self, valid_board_dict):
        """Missing player raises ValueError."""
        del valid_board_dict["player1"]
        with pytest.raises(ValueError, match="missing required"):
            BoardState.from_dict(valid_board_dict)

    def test_get_player(self, valid_board):
        """get_player returns correct player."""
        assert valid_board.get_player(0) == valid_board.player0
        assert valid_board.get_player(1) == valid_board.player1

    def test_get_player_invalid_raises(self, valid_board):
        """Invalid player number raises ValueError."""
        with pytest.raises(ValueError, match="Invalid player number"):
            valid_board.get_player(2)

    def test_get_monsters(self, valid_board):
        """get_monsters returns monster tuple."""
        monsters = valid_board.get_monsters(player=0)
        assert len(monsters) == 1
        assert monsters[0].code == 29301450

    def test_get_monster_codes(self, valid_board):
        """get_monster_codes returns list of codes."""
        codes = valid_board.get_monster_codes(player=0)
        assert codes == [29301450]

    def test_has_monster(self, valid_board):
        """has_monster checks specific player."""
        assert valid_board.has_monster(29301450, player=0) is True
        assert valid_board.has_monster(29301450, player=1) is False

    def test_to_dict_roundtrip(self, valid_board_dict):
        """to_dict produces dict that can be re-parsed."""
        board = BoardState.from_dict(valid_board_dict)
        roundtrip_dict = board.to_dict()
        board2 = BoardState.from_dict(roundtrip_dict)
        assert board.player0.monsters[0].code == board2.player0.monsters[0].code

    def test_frozen_prevents_mutation(self, valid_board):
        """Cannot mutate frozen BoardState."""
        with pytest.raises(FrozenInstanceError):
            valid_board.player0 = None


# =============================================================================
# ATTRIBUTE ACCESS TESTS (ANTI-HALLUCINATION)
# =============================================================================

class TestAttributeAccessGuards:
    """Tests that verify hallucination-prone field names fail correctly."""

    def test_board_extra_monster_zone_attribute_error(self, valid_board):
        """Accessing board.extra_monster_zone raises AttributeError."""
        with pytest.raises(AttributeError):
            _ = valid_board.extra_monster_zone

    def test_board_monster_zone_attribute_error(self, valid_board):
        """Accessing board.monster_zone raises AttributeError."""
        with pytest.raises(AttributeError):
            _ = valid_board.monster_zone

    def test_player_extra_monster_zone_attribute_error(self, valid_board):
        """Accessing player.extra_monster_zone raises AttributeError."""
        with pytest.raises(AttributeError):
            _ = valid_board.player0.extra_monster_zone

    def test_player_monster_zone_attribute_error(self, valid_board):
        """Accessing player.monster_zone raises AttributeError."""
        with pytest.raises(AttributeError):
            _ = valid_board.player0.monster_zone

    def test_player_extra_deck_attribute_error(self, valid_board):
        """Accessing player.extra_deck raises AttributeError (should be 'extra')."""
        with pytest.raises(AttributeError):
            _ = valid_board.player0.extra_deck

    def test_player_gy_attribute_error(self, valid_board):
        """Accessing player.gy raises AttributeError (should be 'graveyard')."""
        with pytest.raises(AttributeError):
            _ = valid_board.player0.gy


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_empty_board(self):
        """Empty board (no cards anywhere) is valid."""
        empty_player = {
            "hand": [],
            "monsters": [],
            "spells": [],
            "graveyard": [],
            "banished": [],
            "extra": [],
        }
        board = BoardState.from_dict({
            "player0": empty_player,
            "player1": empty_player,
        })
        assert board.get_monster_codes() == []
        assert board.player0.has_card(12345) is False

    def test_many_monsters(self):
        """Board with many monsters."""
        monsters = [{"code": i, "name": f"Monster {i}"} for i in range(7)]
        player = {
            "hand": [],
            "monsters": monsters,
            "spells": [],
            "graveyard": [],
            "banished": [],
            "extra": [],
        }
        board = BoardState.from_dict({
            "player0": player,
            "player1": player,
        })
        assert len(board.player0.monsters) == 7
        assert board.get_monster_codes() == list(range(7))
