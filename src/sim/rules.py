"""Yu-Gi-Oh rules enforcement layer.

Every effect activation must pass through these checks BEFORE
the effect-specific logic runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CardType(Enum):
    MONSTER = "monster"
    SPELL = "spell"
    TRAP = "trap"


class EffectLocation(Enum):
    """Where an effect can be activated FROM."""

    HAND = "hand"
    FIELD = "field"
    GY = "gy"
    BANISHED = "banished"
    DECK = "deck"  # Rare, for cards like Necrovalley
    EXTRA = "extra"


class EffectType(Enum):
    """How the effect activates."""

    IGNITION = "ignition"  # Manual activation during your MP
    TRIGGER = "trigger"  # Activates when condition occurs
    QUICK = "quick"  # Can chain, activate on either turn
    CONTINUOUS = "continuous"  # Always applying while face-up


@dataclass
class ActivationContext:
    """State needed to validate an activation."""

    card_type: CardType
    effect_location: EffectLocation  # Where effect activates FROM
    effect_type: EffectType
    current_location: str  # Where the card actually IS right now
    is_set: bool = False
    turns_since_set: int = 0
    trigger_event_occurred: bool = True  # For trigger effects
    is_your_turn: bool = True
    is_main_phase: bool = True


def validate_activation(ctx: ActivationContext) -> tuple[bool, str]:
    """
    Check if an effect activation is legal per Yu-Gi-Oh rules.
    Returns (is_legal, reason).
    """

    # Rule: Trap cards must be Set and cannot activate the turn they were Set
    if ctx.card_type == CardType.TRAP and ctx.effect_location == EffectLocation.FIELD:
        if ctx.current_location == "hand":
            return False, "Trap cards cannot be activated from hand"
        if not ctx.is_set:
            return False, "Trap cards must be Set before activation"
        if ctx.turns_since_set < 1:
            return False, "Trap cards cannot activate the turn they were Set"

    # Rule: Effect location must match card's current location
    # e.g., GY effect requires card to be in GY
    location_map = {
        EffectLocation.HAND: "hand",
        EffectLocation.FIELD: ["mz", "emz", "stz", "fz"],
        EffectLocation.GY: "gy",
        EffectLocation.BANISHED: "banished",
    }
    expected = location_map.get(ctx.effect_location)
    if expected:
        if isinstance(expected, list):
            if ctx.current_location not in expected:
                return (
                    False,
                    f"Effect requires card in {expected}, but card is in {ctx.current_location}",
                )
        elif ctx.current_location != expected:
            return (
                False,
                f"Effect requires card in {expected}, but card is in {ctx.current_location}",
            )

    # Rule: Trigger effects require their trigger to have occurred
    if ctx.effect_type == EffectType.TRIGGER:
        if not ctx.trigger_event_occurred:
            return False, "Trigger effect requires trigger condition to occur first"

    # Rule: Ignition effects can only be activated during your Main Phase
    if ctx.effect_type == EffectType.IGNITION:
        if not ctx.is_your_turn:
            return False, "Ignition effects can only be activated during your turn"
        if not ctx.is_main_phase:
            return False, "Ignition effects can only be activated during Main Phase"

    return True, "Activation is legal"
