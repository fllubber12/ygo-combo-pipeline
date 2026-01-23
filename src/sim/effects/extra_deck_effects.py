from __future__ import annotations

from ..errors import IllegalActionError, SimModelError
from ..state import GameState
from .types import EffectAction, EffectImpl

EVILSWARM_EXCITON_KNIGHT_CID = "10942"
DDD_WAVE_HIGH_KING_CAESAR_CID = "13081"


class EvilswarmExcitonKnightEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "Main Phase" not in state.phase:
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
        if "Main Phase" not in state.phase:
            raise IllegalActionError("Evilswarm Exciton Knight requires Main Phase.")
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
        new_state.opt_used[f"{EVILSWARM_EXCITON_KNIGHT_CID}:e1"] = True
        if "COND_EXCITON_ONLINE" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "COND_EXCITON_ONLINE"]
        return new_state


class DDDWaveHighKingCaesarEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "Main Phase" not in state.phase:
            return actions
        if "OPP_ACTIVATED_EFFECT" not in state.events:
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
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id != "caesar_negate_send":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{DDD_WAVE_HIGH_KING_CAESAR_CID}:e1"):
            raise IllegalActionError("D/D/D Wave High King Caesar effect already used.")
        if "Main Phase" not in state.phase:
            raise IllegalActionError("D/D/D Wave High King Caesar requires Main Phase.")
        if "OPP_ACTIVATED_EFFECT" not in state.events:
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
        new_state.opt_used[f"{DDD_WAVE_HIGH_KING_CAESAR_CID}:e1"] = True
        if "OPP_ACTIVATED_EFFECT" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "OPP_ACTIVATED_EFFECT"]
        return new_state
