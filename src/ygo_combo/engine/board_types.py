"""
Validated board state types.

These dataclasses replace raw Dict access with type-safe validated structures.
Any attempt to access invalid fields raises AttributeError immediately.
Any attempt to construct with invalid data raises ValueError at the boundary.

This module exists to prevent hallucination errors where incorrect field names
(like 'extra_monster_zone' instead of 'monsters') silently return None.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple


@dataclass(frozen=True)
class CardInfo:
    """A card on the board or in a zone.

    Frozen to prevent accidental mutation after validation.

    Attributes:
        code: Card passcode (unique identifier)
        name: Card name
        atk: Attack value (None for spells/traps)
        def_: Defense value (None for spells/traps, named def_ because 'def' is reserved)
    """
    code: int
    name: str
    atk: Optional[int] = None
    def_: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CardInfo":
        """Convert from dict with validation.

        Args:
            data: Dict with at least 'code' and 'name' keys

        Returns:
            Validated CardInfo instance

        Raises:
            ValueError: If required fields are missing
        """
        if "code" not in data:
            raise ValueError(f"CardInfo missing required 'code' field: {data}")
        if "name" not in data:
            raise ValueError(f"CardInfo missing required 'name' field: {data}")

        return cls(
            code=data["code"],
            name=data["name"],
            atk=data.get("atk"),
            def_=data.get("def"),
        )


@dataclass(frozen=True)
class PlayerState:
    """Complete state for one player.

    All zone fields are explicitly defined - no dynamic access allowed.
    This prevents hallucination errors where wrong field names are used.

    Attributes:
        hand: Cards in hand
        monsters: Cards in monster zones (seq 0-4 main, 5-6 EMZ)
        spells: Cards in spell/trap zones
        graveyard: Cards in graveyard
        banished: Banished cards
        extra: Extra Deck pile (face-down, NOT summoned monsters)
    """
    hand: Tuple[CardInfo, ...]
    monsters: Tuple[CardInfo, ...]
    spells: Tuple[CardInfo, ...]
    graveyard: Tuple[CardInfo, ...]
    banished: Tuple[CardInfo, ...]
    extra: Tuple[CardInfo, ...]

    # Class-level constant for validation
    VALID_ZONE_NAMES = frozenset({
        "hand", "monsters", "spells", "graveyard", "banished", "extra"
    })

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerState":
        """Convert from dict with strict validation.

        Args:
            data: Dict with zone names as keys

        Returns:
            Validated PlayerState instance

        Raises:
            ValueError: If keys don't match expected zone names exactly
        """
        actual_keys = set(data.keys())

        # Check for missing keys
        missing = cls.VALID_ZONE_NAMES - actual_keys
        if missing:
            raise ValueError(
                f"PlayerState missing required zone(s): {missing}. "
                f"Valid zones are: {cls.VALID_ZONE_NAMES}"
            )

        # Check for unknown keys (THIS IS THE ANTI-HALLUCINATION GUARD)
        unknown = actual_keys - cls.VALID_ZONE_NAMES
        if unknown:
            raise ValueError(
                f"PlayerState has unknown zone(s): {unknown}. "
                f"Valid zones are: {cls.VALID_ZONE_NAMES}. "
                f"Did you mean one of: {cls.VALID_ZONE_NAMES}?"
            )

        def convert_zone(zone_data: List[Dict]) -> Tuple[CardInfo, ...]:
            return tuple(CardInfo.from_dict(c) for c in zone_data)

        return cls(
            hand=convert_zone(data["hand"]),
            monsters=convert_zone(data["monsters"]),
            spells=convert_zone(data["spells"]),
            graveyard=convert_zone(data["graveyard"]),
            banished=convert_zone(data["banished"]),
            extra=convert_zone(data["extra"]),
        )

    def get_monster_codes(self) -> List[int]:
        """Get all monster passcodes on field."""
        return [card.code for card in self.monsters]

    def get_graveyard_codes(self) -> List[int]:
        """Get all passcodes in graveyard."""
        return [card.code for card in self.graveyard]

    def has_card(self, code: int) -> bool:
        """Check if a card with given code is anywhere for this player."""
        all_cards = self.hand + self.monsters + self.spells + self.graveyard + self.banished
        return any(card.code == code for card in all_cards)

    def has_monster(self, code: int) -> bool:
        """Check if a monster with given code is on field."""
        return any(card.code == code for card in self.monsters)


@dataclass(frozen=True)
class BoardState:
    """Complete validated board state.

    This is the ONLY way to represent board state in the codebase.
    Raw dicts should never be passed around after capture_board_state().

    Attributes:
        player0: Our player's state
        player1: Opponent's state
    """
    player0: PlayerState
    player1: PlayerState

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BoardState":
        """Convert from raw dict with strict validation.

        This is the BOUNDARY where validation happens.
        All downstream code receives a validated BoardState.

        Args:
            data: Dict with 'player0' and 'player1' keys

        Returns:
            Validated BoardState instance

        Raises:
            ValueError: If structure doesn't match expected format
        """
        expected_keys = {"player0", "player1"}
        actual_keys = set(data.keys())

        missing = expected_keys - actual_keys
        if missing:
            raise ValueError(f"BoardState missing required key(s): {missing}")

        unknown = actual_keys - expected_keys
        if unknown:
            raise ValueError(
                f"BoardState has unknown key(s): {unknown}. "
                f"Valid keys are: {expected_keys}. "
                f"NOTE: 'extra_monster_zone' and 'monster_zone' are NOT valid keys. "
                f"EMZ monsters are in player0.monsters at sequences 5-6."
            )

        return cls(
            player0=PlayerState.from_dict(data["player0"]),
            player1=PlayerState.from_dict(data["player1"]),
        )

    def get_player(self, player_num: int) -> PlayerState:
        """Get player state by number with validation."""
        if player_num == 0:
            return self.player0
        elif player_num == 1:
            return self.player1
        else:
            raise ValueError(f"Invalid player number: {player_num}. Must be 0 or 1.")

    def get_monsters(self, player: int = 0) -> Tuple[CardInfo, ...]:
        """Get monsters for a player."""
        return self.get_player(player).monsters

    def get_monster_codes(self, player: int = 0) -> List[int]:
        """Get all monster passcodes for a player."""
        return self.get_player(player).get_monster_codes()

    def has_monster(self, code: int, player: int = 0) -> bool:
        """Check if a monster with given code is on field."""
        return self.get_player(player).has_monster(code)

    def to_dict(self) -> Dict[str, Any]:
        """Convert back to dict for JSON serialization."""
        def player_to_dict(p: PlayerState) -> Dict[str, Any]:
            def zone_to_list(zone: Tuple[CardInfo, ...]) -> List[Dict]:
                return [
                    {"code": c.code, "name": c.name, "atk": c.atk, "def": c.def_}
                    for c in zone
                ]
            return {
                "hand": zone_to_list(p.hand),
                "monsters": zone_to_list(p.monsters),
                "spells": zone_to_list(p.spells),
                "graveyard": zone_to_list(p.graveyard),
                "banished": zone_to_list(p.banished),
                "extra": zone_to_list(p.extra),
            }
        return {
            "player0": player_to_dict(self.player0),
            "player1": player_to_dict(self.player1),
        }


__all__ = ['CardInfo', 'PlayerState', 'BoardState']
