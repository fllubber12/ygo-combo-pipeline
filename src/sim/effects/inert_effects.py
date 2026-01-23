from __future__ import annotations

# These are stubs; they satisfy coverage only and do NOT count as modeled.

from ..errors import SimModelError
from ..state import GameState
from .types import EffectAction, EffectImpl

INERT_EFFECT_CIDS: dict[str, str] = {}


class InertEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        return []

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
