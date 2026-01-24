from __future__ import annotations

from ..errors import IllegalActionError, SimModelError
from ..state import GameState
from .types import EffectAction, EffectImpl

EVILSWARM_EXCITON_KNIGHT_CID = "10942"
DDD_WAVE_HIGH_KING_CAESAR_CID = "13081"
CAESAR_GY_TRIGGER_EVENT = "CAESAR_GY_TRIGGER"
CAESAR_SS_EFFECT_EVENT = "OPP_SPECIAL_SUMMON_EFFECT"


def _is_main_or_battle_phase(phase: str) -> bool:
    return "Main Phase" in phase or "Battle Phase" in phase


def _is_dark_contract(card) -> bool:
    return "dark contract" in str(card.name).lower()


class EvilswarmExcitonKnightEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if not _is_main_or_battle_phase(state.phase):
            return actions
        if "COND_EXCITON_ONLINE" not in state.events:
            return actions
        if state.opt_used.get(f"{EVILSWARM_EXCITON_KNIGHT_CID}:e1"):
            return actions

        for zone, index, card in state.field_cards():
            if card.cid != EVILSWARM_EXCITON_KNIGHT_CID:
                continue
            if not card.properly_summoned:
                continue
            if str(card.metadata.get("summon_type", "")).lower() != "xyz":
                continue
            field_targets = []
            for target_zone, target_index, target_card in state.field_cards():
                if target_zone == zone and target_index == index:
                    continue
                field_targets.append((target_zone, target_index, target_card))
            for stz_index, stz_card in enumerate(state.field.stz):
                if stz_card:
                    field_targets.append(("stz", stz_index, stz_card))
            for fz_index, fz_card in enumerate(state.field.fz):
                if fz_card:
                    field_targets.append(("fz", fz_index, fz_card))
            if not field_targets:
                continue
            actions.append(
                EffectAction(
                    cid=EVILSWARM_EXCITON_KNIGHT_CID,
                    name=card.name,
                    effect_id="exciton_knight_wipe",
                    params={"zone": zone, "field_index": index},
                    sort_key=(
                        EVILSWARM_EXCITON_KNIGHT_CID,
                        "exciton_knight_wipe",
                        zone,
                        index,
                    ),
                )
            )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id != "exciton_knight_wipe":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{EVILSWARM_EXCITON_KNIGHT_CID}:e1"):
            raise IllegalActionError("Evilswarm Exciton Knight effect already used.")
        if not _is_main_or_battle_phase(state.phase):
            raise IllegalActionError("Evilswarm Exciton Knight requires Main/Battle Phase.")
        if "COND_EXCITON_ONLINE" not in state.events:
            raise IllegalActionError("Evilswarm Exciton Knight condition not met.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for Evilswarm Exciton Knight.")
        if not isinstance(field_index, int):
            raise SimModelError("Invalid index types for Evilswarm Exciton Knight.")

        if zone == "mz":
            if field_index < 0 or field_index >= len(state.field.mz):
                raise IllegalActionError("Field index out of range for Evilswarm Exciton Knight.")
            card = state.field.mz[field_index]
        else:
            if field_index < 0 or field_index >= len(state.field.emz):
                raise IllegalActionError("Field index out of range for Evilswarm Exciton Knight.")
            card = state.field.emz[field_index]
        if not card or card.cid != EVILSWARM_EXCITON_KNIGHT_CID:
            raise SimModelError("Selected field card is not Evilswarm Exciton Knight.")
        if not card.properly_summoned:
            raise IllegalActionError("Evilswarm Exciton Knight was not properly summoned.")
        if str(card.metadata.get("summon_type", "")).lower() != "xyz":
            raise IllegalActionError("Evilswarm Exciton Knight is not an Xyz monster.")

        new_state = state.clone()
        field_targets = []
        for target_zone, target_index, target_card in new_state.field_cards():
            if target_zone == zone and target_index == field_index:
                continue
            field_targets.append((target_zone, target_index, target_card))
        for stz_index, stz_card in enumerate(new_state.field.stz):
            if stz_card:
                field_targets.append(("stz", stz_index, stz_card))
        for fz_index, fz_card in enumerate(new_state.field.fz):
            if fz_card:
                field_targets.append(("fz", fz_index, fz_card))
        if not field_targets:
            raise IllegalActionError("Evilswarm Exciton Knight has no valid targets.")
        for target_zone, target_index, _target_card in field_targets:
            if target_zone == "mz":
                target = new_state.field.mz[target_index]
                new_state.field.mz[target_index] = None
            elif target_zone == "emz":
                target = new_state.field.emz[target_index]
                new_state.field.emz[target_index] = None
            elif target_zone == "stz":
                target = new_state.field.stz[target_index]
                new_state.field.stz[target_index] = None
            else:
                target = new_state.field.fz[target_index]
                new_state.field.fz[target_index] = None
            if target is not None:
                new_state.gy.append(target)
        # Opponent takes no damage this turn (marker only).
        new_state.restrictions.append("OPPONENT_NO_DAMAGE_THIS_TURN")
        new_state.opt_used[f"{EVILSWARM_EXCITON_KNIGHT_CID}:e1"] = True
        if "COND_EXCITON_ONLINE" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "COND_EXCITON_ONLINE"]
        return new_state


class DDDWaveHighKingCaesarEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "OPP_ACTIVATED_EFFECT" not in state.events and CAESAR_SS_EFFECT_EVENT not in state.events:
            return actions
        if state.opt_used.get(f"{DDD_WAVE_HIGH_KING_CAESAR_CID}:e1"):
            return actions

        for zone, index, card in state.field_cards():
            if card.cid != DDD_WAVE_HIGH_KING_CAESAR_CID:
                continue
            if not card.properly_summoned:
                continue
            if str(card.metadata.get("summon_type", "")).lower() != "xyz":
                continue
            field_targets = []
            for target_zone, target_index, target_card in state.field_cards():
                if target_zone == zone and target_index == index:
                    continue
                field_targets.append((target_zone, target_index, target_card))
            for stz_index, stz_card in enumerate(state.field.stz):
                if stz_card:
                    field_targets.append(("stz", stz_index, stz_card))
            for fz_index, fz_card in enumerate(state.field.fz):
                if fz_card:
                    field_targets.append(("fz", fz_index, fz_card))
            if not field_targets:
                continue
            actions.append(
                EffectAction(
                    cid=DDD_WAVE_HIGH_KING_CAESAR_CID,
                    name=card.name,
                    effect_id="caesar_negate_send",
                    params={"zone": zone, "field_index": index},
                    sort_key=(
                        DDD_WAVE_HIGH_KING_CAESAR_CID,
                        "caesar_negate_send",
                        zone,
                        index,
                    ),
                )
            )

        # GY trigger: add 1 "Dark Contract" card from Deck to hand.
        if (
            not state.opt_used.get(f"{DDD_WAVE_HIGH_KING_CAESAR_CID}:e2")
            and (
                CAESAR_GY_TRIGGER_EVENT in state.events
                or DDD_WAVE_HIGH_KING_CAESAR_CID in state.last_moved_to_gy
            )
        ):
            gy_indices = [
                idx
                for idx, card in enumerate(state.gy)
                if card.cid == DDD_WAVE_HIGH_KING_CAESAR_CID
            ]
            if gy_indices:
                deck_indices = [
                    idx for idx, card in enumerate(state.deck) if _is_dark_contract(card)
                ]
                for gy_index in gy_indices:
                    for deck_index in deck_indices:
                        actions.append(
                            EffectAction(
                                cid=DDD_WAVE_HIGH_KING_CAESAR_CID,
                                name=state.gy[gy_index].name,
                                effect_id="caesar_gy_search_dark_contract",
                                params={
                                    "gy_index": gy_index,
                                    "deck_index": deck_index,
                                },
                                sort_key=(
                                    DDD_WAVE_HIGH_KING_CAESAR_CID,
                                    "caesar_gy_search_dark_contract",
                                    gy_index,
                                    deck_index,
                                ),
                            )
                        )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "caesar_gy_search_dark_contract":
            if state.opt_used.get(f"{DDD_WAVE_HIGH_KING_CAESAR_CID}:e2"):
                raise IllegalActionError("D/D/D Wave High King Caesar GY effect already used.")
            if (
                CAESAR_GY_TRIGGER_EVENT not in state.events
                and DDD_WAVE_HIGH_KING_CAESAR_CID not in state.last_moved_to_gy
            ):
                raise IllegalActionError("D/D/D Wave High King Caesar GY trigger not present.")

            gy_index = action.params.get("gy_index")
            deck_index = action.params.get("deck_index")
            if gy_index is None or deck_index is None:
                raise SimModelError("Missing params for D/D/D Wave High King Caesar GY effect.")
            if not isinstance(gy_index, int) or not isinstance(deck_index, int):
                raise SimModelError("Invalid index types for D/D/D Wave High King Caesar GY effect.")
            if gy_index < 0 or gy_index >= len(state.gy):
                raise IllegalActionError("GY index out of range for D/D/D Wave High King Caesar.")
            if deck_index < 0 or deck_index >= len(state.deck):
                raise IllegalActionError("Deck index out of range for D/D/D Wave High King Caesar.")
            if state.gy[gy_index].cid != DDD_WAVE_HIGH_KING_CAESAR_CID:
                raise SimModelError("Selected GY card is not D/D/D Wave High King Caesar.")
            if not _is_dark_contract(state.deck[deck_index]):
                raise IllegalActionError("Selected deck card is not a Dark Contract.")

            new_state = state.clone()
            card = new_state.deck.pop(deck_index)
            new_state.hand.append(card)
            new_state.opt_used[f"{DDD_WAVE_HIGH_KING_CAESAR_CID}:e2"] = True
            if CAESAR_GY_TRIGGER_EVENT in new_state.events:
                new_state.events = [evt for evt in new_state.events if evt != CAESAR_GY_TRIGGER_EVENT]
            return new_state

        if action.effect_id != "caesar_negate_send":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{DDD_WAVE_HIGH_KING_CAESAR_CID}:e1"):
            raise IllegalActionError("D/D/D Wave High King Caesar effect already used.")
        if "OPP_ACTIVATED_EFFECT" not in state.events and CAESAR_SS_EFFECT_EVENT not in state.events:
            raise IllegalActionError("D/D/D Wave High King Caesar requires opponent effect.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for D/D/D Wave High King Caesar.")
        if not isinstance(field_index, int):
            raise SimModelError("Invalid index types for D/D/D Wave High King Caesar.")

        if zone == "mz":
            if field_index < 0 or field_index >= len(state.field.mz):
                raise IllegalActionError("Field index out of range for D/D/D Wave High King Caesar.")
            card = state.field.mz[field_index]
        else:
            if field_index < 0 or field_index >= len(state.field.emz):
                raise IllegalActionError("Field index out of range for D/D/D Wave High King Caesar.")
            card = state.field.emz[field_index]
        if not card or card.cid != DDD_WAVE_HIGH_KING_CAESAR_CID:
            raise SimModelError("Selected field card is not D/D/D Wave High King Caesar.")
        if not card.properly_summoned:
            raise IllegalActionError("D/D/D Wave High King Caesar was not properly summoned.")
        if str(card.metadata.get("summon_type", "")).lower() != "xyz":
            raise IllegalActionError("D/D/D Wave High King Caesar is not an Xyz monster.")

        new_state = state.clone()
        field_targets = []
        for target_zone, target_index, target_card in new_state.field_cards():
            if target_zone == zone and target_index == field_index:
                continue
            field_targets.append((target_zone, target_index, target_card))
        for stz_index, stz_card in enumerate(new_state.field.stz):
            if stz_card:
                field_targets.append(("stz", stz_index, stz_card))
        for fz_index, fz_card in enumerate(new_state.field.fz):
            if fz_card:
                field_targets.append(("fz", fz_index, fz_card))
        if not field_targets:
            raise IllegalActionError("D/D/D Wave High King Caesar has no valid targets.")
        target_zone, target_index, _target_card = field_targets[0]
        if target_zone == "mz":
            target = new_state.field.mz[target_index]
            new_state.field.mz[target_index] = None
        elif target_zone == "emz":
            target = new_state.field.emz[target_index]
            new_state.field.emz[target_index] = None
        elif target_zone == "stz":
            target = new_state.field.stz[target_index]
            new_state.field.stz[target_index] = None
        else:
            target = new_state.field.fz[target_index]
            new_state.field.fz[target_index] = None
        if target is None:
            raise IllegalActionError("D/D/D Wave High King Caesar target missing.")
        new_state.gy.append(target)
        # Optional ATK boost (marker only).
        new_state.restrictions.append("CAESAR_ATK_BOOST_APPLIED")
        new_state.opt_used[f"{DDD_WAVE_HIGH_KING_CAESAR_CID}:e1"] = True
        if "OPP_ACTIVATED_EFFECT" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "OPP_ACTIVATED_EFFECT"]
        if CAESAR_SS_EFFECT_EVENT in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != CAESAR_SS_EFFECT_EVENT]
        return new_state
