from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..state import GameState


@dataclass(frozen=True)
class EffectAction:
    cid: str
    name: str
    effect_id: str
    params: dict[str, Any]
    sort_key: tuple

    def describe(self) -> str:
        return f"{self.name} [{self.cid}] {self.effect_id}: {self.params}"


class EffectImpl(Protocol):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        ...

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        ...
