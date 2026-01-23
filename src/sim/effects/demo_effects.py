from __future__ import annotations

from ..errors import IllegalActionError, SimModelError
from ..state import GameState
from .types import EffectAction, EffectImpl

DEMO_EXTENDER_CID = "DEMO_EXTENDER_001"
DEMO_EXTENDER_NAME = "Demo Extender"


class DemoExtenderEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        open_mz = state.open_mz_indices()
        if not open_mz:
            return actions

        for hand_index, card in enumerate(state.hand):
            if card.cid != DEMO_EXTENDER_CID:
                continue
            for mz_index in open_mz:
                actions.append(
                    EffectAction(
                        cid=DEMO_EXTENDER_CID,
                        name=card.name or DEMO_EXTENDER_NAME,
                        effect_id="special_summon_self",
                        params={"hand_index": hand_index, "mz_index": mz_index},
                        sort_key=(DEMO_EXTENDER_CID, hand_index, mz_index),
                    )
                )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id != "special_summon_self":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        hand_index = action.params.get("hand_index")
        mz_index = action.params.get("mz_index")
        if hand_index is None or mz_index is None:
            raise SimModelError("Missing params for Demo Extender effect.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Demo Extender.")
        if hand_index < 0 or hand_index >= len(state.hand):
            raise IllegalActionError("Hand index out of range for Demo Extender.")
        card = state.hand[hand_index]
        if card.cid != DEMO_EXTENDER_CID:
            raise SimModelError("Action does not match Demo Extender card.")

        new_state = state.clone()
        card = new_state.hand.pop(hand_index)
        new_state.field.mz[mz_index] = card
        return new_state
