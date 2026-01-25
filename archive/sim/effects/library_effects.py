from __future__ import annotations

import itertools

from ..errors import IllegalActionError, SimModelError
from ..state import GameState, can_revive_from_gy, is_extra_deck_monster, validate_revive_from_gy
from .fiendsmith_effects import (
    FIENDSMITH_FUSION_CIDS,
    FIENDSMITH_LACRIMA_CID,
    FIENDSMITH_REXTREMENDE_CID,
    OPP_TURN_EVENT,
    fiendsmith_fusion_materials_ok,
    is_light_fiend_card,
    is_link_monster,
)
from .types import EffectAction, EffectImpl

CROSS_SHEEP_CID = "14856"
MUCKRAKER_CID = "17806"
SP_LITTLE_KNIGHT_CID = "19188"
FIENDSMITH_SEQUENCE_ALT_CID = "20226"
DUKE_OF_DEMISE_CID = "20389"
NECROQUIP_PRINCESS_CID = "20423"
AERIAL_EATER_CID = "20427"
SNAKE_EYES_DOOMED_DRAGON_CID = "20772"
A_BAO_A_QU_CID = "20786"
BUIO_DAWNS_LIGHT_CID = "21624"
LUCE_DUSKS_DARK_CID = "21625"
MUTINY_IN_THE_SKY_CID = "21626"
# Fabled Lurrie - LIGHT Fiend Level 1, SS when discarded to GY
# Passcode: 97651498, Konami CID: 8092
FABLED_LURRIE_CID = "8092"


def is_fiend_card(card) -> bool:
    race = str(card.metadata.get("race", "")).upper()
    if "FIEND" in race:
        return True
    return is_light_fiend_card(card)


def is_fairy_or_fiend(card) -> bool:
    race = str(card.metadata.get("race", "")).upper()
    return "FIEND" in race or "FAIRY" in race


def is_fiend_or_zombie(card) -> bool:
    race = str(card.metadata.get("race", "")).upper()
    return "FIEND" in race or "ZOMBIE" in race


def card_level(card) -> int | None:
    value = card.metadata.get("level")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class CrossSheepEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if state.opt_used.get(f"{CROSS_SHEEP_CID}:e1"):
            return actions

        open_mz = state.open_mz_indices()

        if "CROSS_SHEEP_TRIGGER" in state.events and open_mz:
            for zone, index, card in state.field_cards():
                if card.cid != CROSS_SHEEP_CID:
                    continue
                if not card.properly_summoned:
                    continue
                if str(card.metadata.get("summon_type", "")).lower() != "link":
                    continue
                for gy_index, target in enumerate(state.gy):
                    level = card_level(target)
                    if level is None or level > 4:
                        continue
                    for mz_index in open_mz:
                        actions.append(
                            EffectAction(
                                cid=CROSS_SHEEP_CID,
                                name=card.name,
                                effect_id="cross_sheep_revive",
                                params={
                                    "zone": zone,
                                    "field_index": index,
                                    "gy_index": gy_index,
                                    "mz_index": mz_index,
                                },
                                sort_key=(
                                    CROSS_SHEEP_CID,
                                    "cross_sheep_revive",
                                    zone,
                                    index,
                                    gy_index,
                                    mz_index,
                                ),
                            )
                        )

        if "CROSS_SHEEP_RITUAL" in state.events and len(state.deck) >= 2:
            for zone, index, card in state.field_cards():
                if card.cid != CROSS_SHEEP_CID:
                    continue
                if not card.properly_summoned:
                    continue
                if str(card.metadata.get("summon_type", "")).lower() != "link":
                    continue
                actions.append(
                    EffectAction(
                        cid=CROSS_SHEEP_CID,
                        name=card.name,
                        effect_id="cross_sheep_ritual_draw_discard",
                        params={"zone": zone, "field_index": index},
                        sort_key=(
                            CROSS_SHEEP_CID,
                            "cross_sheep_ritual_draw_discard",
                            zone,
                            index,
                        ),
                    )
                )

        if "CROSS_SHEEP_SYNCHRO" in state.events:
            for zone, index, card in state.field_cards():
                if card.cid != CROSS_SHEEP_CID:
                    continue
                if not card.properly_summoned:
                    continue
                if str(card.metadata.get("summon_type", "")).lower() != "link":
                    continue
                actions.append(
                    EffectAction(
                        cid=CROSS_SHEEP_CID,
                        name=card.name,
                        effect_id="cross_sheep_synchro_boost",
                        params={"zone": zone, "field_index": index},
                        sort_key=(
                            CROSS_SHEEP_CID,
                            "cross_sheep_synchro_boost",
                            zone,
                            index,
                        ),
                    )
                )

        if "CROSS_SHEEP_XYZ" in state.events:
            for zone, index, card in state.field_cards():
                if card.cid != CROSS_SHEEP_CID:
                    continue
                if not card.properly_summoned:
                    continue
                if str(card.metadata.get("summon_type", "")).lower() != "link":
                    continue
                actions.append(
                    EffectAction(
                        cid=CROSS_SHEEP_CID,
                        name=card.name,
                        effect_id="cross_sheep_xyz_debuff",
                        params={"zone": zone, "field_index": index},
                        sort_key=(
                            CROSS_SHEEP_CID,
                            "cross_sheep_xyz_debuff",
                            zone,
                            index,
                        ),
                    )
                )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "cross_sheep_ritual_draw_discard":
            if state.opt_used.get(f"{CROSS_SHEEP_CID}:e1"):
                raise IllegalActionError("Cross-Sheep effect already used.")
            if "CROSS_SHEEP_RITUAL" not in state.events:
                raise IllegalActionError("Cross-Sheep ritual trigger not present.")
            if len(state.deck) < 2:
                raise IllegalActionError("Not enough cards to draw for Cross-Sheep.")

            zone = action.params.get("zone")
            field_index = action.params.get("field_index")
            if zone not in {"mz", "emz"} or not isinstance(field_index, int):
                raise SimModelError("Invalid params for Cross-Sheep ritual effect.")

            new_state = state.clone()
            drawn = []
            for _ in range(2):
                drawn.append(new_state.deck.pop(0))
            new_state.hand.extend(drawn)
            if len(new_state.hand) < 2:
                raise IllegalActionError("Not enough cards to discard for Cross-Sheep.")
            # Deterministic: discard the two most recently drawn cards.
            for _ in range(2):
                new_state.gy.append(new_state.hand.pop())
            new_state.opt_used[f"{CROSS_SHEEP_CID}:e1"] = True
            new_state.events = [evt for evt in new_state.events if evt != "CROSS_SHEEP_RITUAL"]
            return new_state

        if action.effect_id == "cross_sheep_synchro_boost":
            if state.opt_used.get(f"{CROSS_SHEEP_CID}:e1"):
                raise IllegalActionError("Cross-Sheep effect already used.")
            if "CROSS_SHEEP_SYNCHRO" not in state.events:
                raise IllegalActionError("Cross-Sheep synchro trigger not present.")
            new_state = state.clone()
            new_state.restrictions.append("CROSS_SHEEP_ATK_BOOST_700")
            new_state.opt_used[f"{CROSS_SHEEP_CID}:e1"] = True
            new_state.events = [evt for evt in new_state.events if evt != "CROSS_SHEEP_SYNCHRO"]
            return new_state

        if action.effect_id == "cross_sheep_xyz_debuff":
            if state.opt_used.get(f"{CROSS_SHEEP_CID}:e1"):
                raise IllegalActionError("Cross-Sheep effect already used.")
            if "CROSS_SHEEP_XYZ" not in state.events:
                raise IllegalActionError("Cross-Sheep xyz trigger not present.")
            new_state = state.clone()
            new_state.restrictions.append("CROSS_SHEEP_OPP_ATK_REDUCE_700")
            new_state.opt_used[f"{CROSS_SHEEP_CID}:e1"] = True
            new_state.events = [evt for evt in new_state.events if evt != "CROSS_SHEEP_XYZ"]
            return new_state

        if action.effect_id != "cross_sheep_revive":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{CROSS_SHEEP_CID}:e1"):
            raise IllegalActionError("Cross-Sheep effect already used.")
        if "CROSS_SHEEP_TRIGGER" not in state.events:
            raise IllegalActionError("Cross-Sheep trigger not present.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        gy_index = action.params.get("gy_index")
        mz_index = action.params.get("mz_index")
        if None in (zone, field_index, gy_index, mz_index):
            raise SimModelError("Missing params for Cross-Sheep.")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for Cross-Sheep.")
        if not isinstance(field_index, int) or not isinstance(gy_index, int) or not isinstance(mz_index, int):
            raise SimModelError("Invalid index types for Cross-Sheep.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Cross-Sheep.")
        if gy_index < 0 or gy_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for Cross-Sheep.")

        if zone == "mz":
            if field_index < 0 or field_index >= len(state.field.mz):
                raise IllegalActionError("Field index out of range for Cross-Sheep.")
            card = state.field.mz[field_index]
        else:
            if field_index < 0 or field_index >= len(state.field.emz):
                raise IllegalActionError("Field index out of range for Cross-Sheep.")
            card = state.field.emz[field_index]
        if not card or card.cid != CROSS_SHEEP_CID:
            raise SimModelError("Selected field card is not Cross-Sheep.")
        if not card.properly_summoned:
            raise IllegalActionError("Cross-Sheep was not properly summoned.")
        if str(card.metadata.get("summon_type", "")).lower() != "link":
            raise IllegalActionError("Cross-Sheep is not a Link monster.")

        target = state.gy[gy_index]
        level = card_level(target)
        if level is None or level > 4:
            raise IllegalActionError("Cross-Sheep target must be level 4 or lower.")

        new_state = state.clone()
        revived = new_state.gy.pop(gy_index)
        new_state.field.mz[mz_index] = revived
        new_state.opt_used[f"{CROSS_SHEEP_CID}:e1"] = True
        if "CROSS_SHEEP_TRIGGER" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "CROSS_SHEEP_TRIGGER"]
        return new_state


class MuckrakerEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "MUCKRAKER_NO_LINK_MATERIAL" not in state.restrictions:
            for zone, index, card in state.field_cards():
                if card.cid != MUCKRAKER_CID:
                    continue
                if not card.properly_summoned:
                    continue
                if str(card.metadata.get("summon_type", "")).lower() != "link":
                    continue
                actions.append(
                    EffectAction(
                        cid=MUCKRAKER_CID,
                        name=card.name,
                        effect_id="muckraker_no_link_material",
                        params={"zone": zone, "field_index": index},
                        sort_key=(
                            MUCKRAKER_CID,
                            "muckraker_no_link_material",
                            zone,
                            index,
                        ),
                    )
                )

        if "MUCKRAKER_REPLACE_TRIGGER" in state.events and not state.opt_used.get(
            f"{MUCKRAKER_CID}:e1"
        ):
            tribute_candidates = []
            for zone, index, card in state.field_cards():
                if is_fiend_card(card):
                    tribute_candidates.append((zone, index, card))
            for zone, index, card in state.field_cards():
                if card.cid != MUCKRAKER_CID:
                    continue
                for tribute_zone, tribute_index, tribute_card in tribute_candidates:
                    actions.append(
                        EffectAction(
                            cid=MUCKRAKER_CID,
                            name=card.name,
                            effect_id="muckraker_replace_destruction",
                            params={
                                "zone": zone,
                                "field_index": index,
                                "tribute_zone": tribute_zone,
                                "tribute_index": tribute_index,
                            },
                            sort_key=(
                                MUCKRAKER_CID,
                                "muckraker_replace_destruction",
                                zone,
                                index,
                                tribute_zone,
                                tribute_index,
                            ),
                        )
                    )

        if "Main Phase" not in str(state.phase):
            return actions
        if state.opt_used.get(f"{MUCKRAKER_CID}:e2"):
            return actions
        open_mz = state.open_mz_indices()
        if not open_mz:
            return actions

        for zone, index, card in state.field_cards():
            if card.cid != MUCKRAKER_CID:
                continue
            if not card.properly_summoned:
                continue
            if str(card.metadata.get("summon_type", "")).lower() != "link":
                continue
            for hand_index, _hand_card in enumerate(state.hand):
                for gy_index, target in enumerate(state.gy):
                    if not is_fiend_card(target):
                        continue
                    if target.cid == MUCKRAKER_CID:
                        continue
                    for mz_index in open_mz:
                        actions.append(
                            EffectAction(
                                cid=MUCKRAKER_CID,
                                name=card.name,
                                effect_id="muckraker_discard_revive",
                                params={
                                    "zone": zone,
                                    "field_index": index,
                                    "hand_index": hand_index,
                                    "gy_index": gy_index,
                                    "mz_index": mz_index,
                                },
                                sort_key=(
                                    MUCKRAKER_CID,
                                    "muckraker_discard_revive",
                                    zone,
                                    index,
                                    hand_index,
                                    gy_index,
                                    mz_index,
                                ),
                            )
                        )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "muckraker_no_link_material":
            zone = action.params.get("zone")
            field_index = action.params.get("field_index")
            if zone not in {"mz", "emz"} or not isinstance(field_index, int):
                raise SimModelError("Invalid params for Muckraker restriction.")
            new_state = state.clone()
            new_state.restrictions.append("MUCKRAKER_NO_LINK_MATERIAL")
            return new_state

        if action.effect_id == "muckraker_replace_destruction":
            if state.opt_used.get(f"{MUCKRAKER_CID}:e1"):
                raise IllegalActionError("Muckraker replacement effect already used.")
            if "MUCKRAKER_REPLACE_TRIGGER" not in state.events:
                raise IllegalActionError("Muckraker replacement trigger not present.")

            tribute_zone = action.params.get("tribute_zone")
            tribute_index = action.params.get("tribute_index")
            if tribute_zone not in {"mz", "emz"} or not isinstance(tribute_index, int):
                raise SimModelError("Invalid params for Muckraker replacement.")

            new_state = state.clone()
            if tribute_zone == "mz":
                if tribute_index < 0 or tribute_index >= len(new_state.field.mz):
                    raise IllegalActionError("Tribute index out of range for Muckraker.")
                tribute = new_state.field.mz[tribute_index]
                new_state.field.mz[tribute_index] = None
            else:
                if tribute_index < 0 or tribute_index >= len(new_state.field.emz):
                    raise IllegalActionError("Tribute index out of range for Muckraker.")
                tribute = new_state.field.emz[tribute_index]
                new_state.field.emz[tribute_index] = None
            if tribute is None or not is_fiend_card(tribute):
                raise IllegalActionError("Tribute must be a Fiend monster.")
            new_state.gy.append(tribute)
            new_state.opt_used[f"{MUCKRAKER_CID}:e1"] = True
            new_state.restrictions.append("MUCKRAKER_DESTRUCTION_REPLACED")
            new_state.events = [evt for evt in new_state.events if evt != "MUCKRAKER_REPLACE_TRIGGER"]
            return new_state

        if action.effect_id != "muckraker_discard_revive":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{MUCKRAKER_CID}:e2"):
            raise IllegalActionError("Muckraker effect already used.")
        if "Main Phase" not in str(state.phase):
            raise IllegalActionError("Muckraker requires Main Phase.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        hand_index = action.params.get("hand_index")
        gy_index = action.params.get("gy_index")
        mz_index = action.params.get("mz_index")
        if None in (zone, field_index, hand_index, gy_index, mz_index):
            raise SimModelError("Missing params for Muckraker.")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for Muckraker.")
        if not isinstance(field_index, int) or not isinstance(hand_index, int) or not isinstance(gy_index, int):
            raise SimModelError("Invalid index types for Muckraker.")
        if hand_index < 0 or hand_index >= len(state.hand):
            raise IllegalActionError("Hand index out of range for Muckraker.")
        if gy_index < 0 or gy_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for Muckraker.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Muckraker.")

        if zone == "mz":
            if field_index < 0 or field_index >= len(state.field.mz):
                raise IllegalActionError("Field index out of range for Muckraker.")
            card = state.field.mz[field_index]
        else:
            if field_index < 0 or field_index >= len(state.field.emz):
                raise IllegalActionError("Field index out of range for Muckraker.")
            card = state.field.emz[field_index]
        if not card or card.cid != MUCKRAKER_CID:
            raise SimModelError("Selected field card is not Muckraker.")
        if not card.properly_summoned:
            raise IllegalActionError("Muckraker was not properly summoned.")
        if str(card.metadata.get("summon_type", "")).lower() != "link":
            raise IllegalActionError("Muckraker is not a Link monster.")

        target = state.gy[gy_index]
        if not is_fiend_card(target):
            raise IllegalActionError("Muckraker target must be a Fiend monster.")
        if target.cid == MUCKRAKER_CID:
            raise IllegalActionError("Muckraker cannot revive itself.")

        new_state = state.clone()
        discarded = new_state.hand.pop(hand_index)
        new_state.gy.append(discarded)
        revived = new_state.gy.pop(gy_index)
        new_state.field.mz[mz_index] = revived
        new_state.opt_used[f"{MUCKRAKER_CID}:e2"] = True
        new_state.restrictions.append("MUCKRAKER_NON_FIEND_SS_FORBIDDEN")
        return new_state


class SPLittleKnightEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "SP_LITTLE_KNIGHT_TRIGGER" in state.events and not state.opt_used.get(
            f"{SP_LITTLE_KNIGHT_CID}:e1"
        ):
            field_targets = []
            for zone, index, card in state.field_cards():
                field_targets.append((zone, index, card))
            for stz_index, stz_card in enumerate(state.field.stz):
                if stz_card:
                    field_targets.append(("stz", stz_index, stz_card))
            for fz_index, fz_card in enumerate(state.field.fz):
                if fz_card:
                    field_targets.append(("fz", fz_index, fz_card))
            for gy_index, gy_card in enumerate(state.gy):
                field_targets.append(("gy", gy_index, gy_card))

            if field_targets:
                for zone, index, card in state.field_cards():
                    if card.cid != SP_LITTLE_KNIGHT_CID:
                        continue
                    if not card.properly_summoned:
                        continue
                    if str(card.metadata.get("summon_type", "")).lower() != "link":
                        continue
                    for target_zone, target_index, target_card in field_targets:
                        if target_zone == zone and target_index == index:
                            continue
                        actions.append(
                            EffectAction(
                                cid=SP_LITTLE_KNIGHT_CID,
                                name=card.name,
                                effect_id="sp_little_knight_banish",
                                params={
                                    "zone": zone,
                                    "field_index": index,
                                    "target_zone": target_zone,
                                    "target_index": target_index,
                                },
                                sort_key=(
                                    SP_LITTLE_KNIGHT_CID,
                                    "sp_little_knight_banish",
                                    zone,
                                    index,
                                    target_zone,
                                    target_index,
                                ),
                            )
                        )

        if "SP_LITTLE_KNIGHT_QUICK" in state.events and not state.opt_used.get(
            f"{SP_LITTLE_KNIGHT_CID}:e2"
        ):
            monsters = [(zone, idx, card) for zone, idx, card in state.field_cards()]
            if len(monsters) >= 2:
                for zone, index, card in state.field_cards():
                    if card.cid != SP_LITTLE_KNIGHT_CID:
                        continue
                    if not card.properly_summoned:
                        continue
                    if str(card.metadata.get("summon_type", "")).lower() != "link":
                        continue
                    for i in range(len(monsters)):
                        for j in range(i + 1, len(monsters)):
                            a_zone, a_idx, _a_card = monsters[i]
                            b_zone, b_idx, _b_card = monsters[j]
                            actions.append(
                                EffectAction(
                                    cid=SP_LITTLE_KNIGHT_CID,
                                    name=card.name,
                                    effect_id="sp_little_knight_banish_pair",
                                    params={
                                        "zone": zone,
                                        "field_index": index,
                                        "a_zone": a_zone,
                                        "a_index": a_idx,
                                        "b_zone": b_zone,
                                        "b_index": b_idx,
                                    },
                                    sort_key=(
                                        SP_LITTLE_KNIGHT_CID,
                                        "sp_little_knight_banish_pair",
                                        zone,
                                        index,
                                        a_zone,
                                        a_idx,
                                        b_zone,
                                        b_idx,
                                    ),
                                )
                            )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "sp_little_knight_banish_pair":
            if state.opt_used.get(f"{SP_LITTLE_KNIGHT_CID}:e2"):
                raise IllegalActionError("S:P Little Knight effect already used.")
            if "SP_LITTLE_KNIGHT_QUICK" not in state.events:
                raise IllegalActionError("S:P Little Knight quick trigger not present.")

            zone = action.params.get("zone")
            field_index = action.params.get("field_index")
            a_zone = action.params.get("a_zone")
            a_index = action.params.get("a_index")
            b_zone = action.params.get("b_zone")
            b_index = action.params.get("b_index")
            if None in (zone, field_index, a_zone, a_index, b_zone, b_index):
                raise SimModelError("Missing params for S:P Little Knight.")
            if zone not in {"mz", "emz"} or a_zone not in {"mz", "emz"} or b_zone not in {"mz", "emz"}:
                raise SimModelError("Invalid zone for S:P Little Knight.")
            if not isinstance(field_index, int) or not isinstance(a_index, int) or not isinstance(b_index, int):
                raise SimModelError("Invalid index types for S:P Little Knight.")

            if zone == "mz":
                card = state.field.mz[field_index] if 0 <= field_index < len(state.field.mz) else None
            else:
                card = state.field.emz[field_index] if 0 <= field_index < len(state.field.emz) else None
            if not card or card.cid != SP_LITTLE_KNIGHT_CID:
                raise SimModelError("Selected field card is not S:P Little Knight.")
            if not card.properly_summoned:
                raise IllegalActionError("S:P Little Knight was not properly summoned.")

            new_state = state.clone()
            for target_zone, target_index in ((a_zone, a_index), (b_zone, b_index)):
                if target_zone == "mz":
                    target = new_state.field.mz[target_index]
                    new_state.field.mz[target_index] = None
                else:
                    target = new_state.field.emz[target_index]
                    new_state.field.emz[target_index] = None
                if target is None:
                    raise IllegalActionError("S:P Little Knight target missing.")
                new_state.banished.append(target)
            new_state.opt_used[f"{SP_LITTLE_KNIGHT_CID}:e2"] = True
            new_state.restrictions.append("SP_LITTLE_KNIGHT_RETURN_END_PHASE")
            new_state.events = [evt for evt in new_state.events if evt != "SP_LITTLE_KNIGHT_QUICK"]
            return new_state

        if action.effect_id != "sp_little_knight_banish":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{SP_LITTLE_KNIGHT_CID}:e1"):
            raise IllegalActionError("S:P Little Knight effect already used.")
        if "SP_LITTLE_KNIGHT_TRIGGER" not in state.events:
            raise IllegalActionError("S:P Little Knight trigger not present.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        target_zone = action.params.get("target_zone")
        target_index = action.params.get("target_index")
        if None in (zone, field_index, target_zone, target_index):
            raise SimModelError("Missing params for S:P Little Knight.")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for S:P Little Knight.")
        if target_zone not in {"mz", "emz", "stz", "fz", "gy"}:
            raise SimModelError("Invalid target zone for S:P Little Knight.")
        if not isinstance(field_index, int) or not isinstance(target_index, int):
            raise SimModelError("Invalid index types for S:P Little Knight.")

        if zone == "mz":
            card = state.field.mz[field_index] if 0 <= field_index < len(state.field.mz) else None
        else:
            card = state.field.emz[field_index] if 0 <= field_index < len(state.field.emz) else None
        if not card or card.cid != SP_LITTLE_KNIGHT_CID:
            raise SimModelError("Selected field card is not S:P Little Knight.")
        if not card.properly_summoned:
            raise IllegalActionError("S:P Little Knight was not properly summoned.")
        if str(card.metadata.get("summon_type", "")).lower() != "link":
            raise IllegalActionError("S:P Little Knight is not a Link monster.")

        new_state = state.clone()
        if target_zone == "mz":
            target = new_state.field.mz[target_index]
            new_state.field.mz[target_index] = None
        elif target_zone == "emz":
            target = new_state.field.emz[target_index]
            new_state.field.emz[target_index] = None
        elif target_zone == "stz":
            target = new_state.field.stz[target_index]
            new_state.field.stz[target_index] = None
        elif target_zone == "fz":
            target = new_state.field.fz[target_index]
            new_state.field.fz[target_index] = None
        else:
            if target_index < 0 or target_index >= len(new_state.gy):
                raise IllegalActionError("GY index out of range for S:P Little Knight.")
            target = new_state.gy[target_index]
            new_state.gy.pop(target_index)

        if target is None:
            raise IllegalActionError("S:P Little Knight target missing.")
        new_state.banished.append(target)
        new_state.opt_used[f"{SP_LITTLE_KNIGHT_CID}:e1"] = True
        new_state.restrictions.append("SP_LITTLE_KNIGHT_NO_DIRECT_ATTACKS")
        if "SP_LITTLE_KNIGHT_TRIGGER" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "SP_LITTLE_KNIGHT_TRIGGER"]
        return new_state


class FiendsmithSequenceAltEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if OPP_TURN_EVENT in state.events:
            return actions

        sequence_entries = []
        for index, card in enumerate(state.field.mz):
            if card and card.cid == FIENDSMITH_SEQUENCE_ALT_CID:
                sequence_entries.append(("mz", index, card))
        for index, card in enumerate(state.field.emz):
            if card and card.cid == FIENDSMITH_SEQUENCE_ALT_CID:
                sequence_entries.append(("emz", index, card))

        if not state.opt_used.get(f"{FIENDSMITH_SEQUENCE_ALT_CID}:e1") and "Main Phase" in state.phase:
            open_mz = state.open_mz_indices()
            if open_mz and sequence_entries:
                gy_entries = list(enumerate(state.gy))
                fusion_targets = [
                    (idx, card)
                    for idx, card in enumerate(state.extra)
                    if card.cid in FIENDSMITH_FUSION_CIDS
                ]
                for seq_zone, seq_index, seq_card in sequence_entries:
                    for extra_index, fusion_card in fusion_targets:
                        required = (
                            2
                            if fusion_card.cid in {FIENDSMITH_LACRIMA_CID, FIENDSMITH_REXTREMENDE_CID}
                            else 3
                        )
                        if len(gy_entries) < required:
                            continue
                        for mz_index in open_mz:
                            for combo in itertools.combinations(gy_entries, required):
                                gy_indices = [idx for idx, _card in combo]
                                material_cards = [card for _idx, card in combo]
                                if not fiendsmith_fusion_materials_ok(
                                    fusion_card.cid, material_cards
                                ):
                                    continue
                                actions.append(
                                    EffectAction(
                                        cid=FIENDSMITH_SEQUENCE_ALT_CID,
                                        name=seq_card.name,
                                        effect_id="sequence_20226_shuffle_fuse",
                                        params={
                                            "seq_zone": seq_zone,
                                            "seq_index": seq_index,
                                            "extra_index": extra_index,
                                            "mz_index": mz_index,
                                            "gy_indices": gy_indices,
                                        },
                                        sort_key=(
                                            FIENDSMITH_SEQUENCE_ALT_CID,
                                            "sequence_20226_shuffle_fuse",
                                            seq_zone,
                                            seq_index,
                                            extra_index,
                                            mz_index,
                                            tuple(gy_indices),
                                        ),
                                    )
                                )

        if not state.opt_used.get(f"{FIENDSMITH_SEQUENCE_ALT_CID}:e2"):
            targets = []
            for mz_index, card in enumerate(state.field.mz):
                if not card:
                    continue
                if not is_light_fiend_card(card):
                    continue
                if is_link_monster(card):
                    continue
                targets.append((mz_index, card))
            if targets:
                for zone, index, card in sequence_entries:
                    for mz_index, _target in targets:
                        actions.append(
                            EffectAction(
                                cid=FIENDSMITH_SEQUENCE_ALT_CID,
                                name=card.name,
                                effect_id="sequence_20226_equip",
                                params={
                                    "source": zone,
                                    "source_index": index,
                                    "target_mz_index": mz_index,
                                },
                                sort_key=(
                                    FIENDSMITH_SEQUENCE_ALT_CID,
                                    "sequence_20226_equip",
                                    zone,
                                    index,
                                    mz_index,
                                ),
                            )
                        )
                for gy_index, card in enumerate(state.gy):
                    if card.cid != FIENDSMITH_SEQUENCE_ALT_CID:
                        continue
                    for mz_index, _target in targets:
                        actions.append(
                            EffectAction(
                                cid=FIENDSMITH_SEQUENCE_ALT_CID,
                                name=card.name,
                                effect_id="sequence_20226_equip",
                                params={
                                    "source": "gy",
                                    "source_index": gy_index,
                                    "target_mz_index": mz_index,
                                },
                                sort_key=(
                                    FIENDSMITH_SEQUENCE_ALT_CID,
                                    "sequence_20226_equip",
                                    "gy",
                                    gy_index,
                                    mz_index,
                                ),
                            )
                        )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "sequence_20226_shuffle_fuse":
            if state.opt_used.get(f"{FIENDSMITH_SEQUENCE_ALT_CID}:e1"):
                raise IllegalActionError("Fiendsmith's Sequence effect already used.")
            if "Main Phase" not in state.phase:
                raise IllegalActionError("Fiendsmith's Sequence requires Main Phase.")

            seq_zone = action.params.get("seq_zone")
            seq_index = action.params.get("seq_index")
            extra_index = action.params.get("extra_index")
            mz_index = action.params.get("mz_index")
            gy_indices = action.params.get("gy_indices")
            if None in (seq_zone, seq_index, extra_index, mz_index, gy_indices):
                raise SimModelError("Missing params for Fiendsmith's Sequence fusion effect.")
            if seq_zone not in {"mz", "emz"}:
                raise SimModelError("Invalid zone for Fiendsmith's Sequence fusion effect.")
            if not isinstance(seq_index, int) or not isinstance(extra_index, int) or not isinstance(mz_index, int):
                raise SimModelError("Invalid index types for Fiendsmith's Sequence fusion effect.")
            if not isinstance(gy_indices, list):
                raise SimModelError("Invalid GY indices for Fiendsmith's Sequence fusion effect.")
            if mz_index not in state.open_mz_indices():
                raise IllegalActionError("No open Main Monster Zone for Fiendsmith's Sequence.")
            if extra_index < 0 or extra_index >= len(state.extra):
                raise IllegalActionError("Extra index out of range for Fiendsmith's Sequence.")

            if seq_zone == "mz":
                if seq_index < 0 or seq_index >= len(state.field.mz):
                    raise IllegalActionError("Field index out of range for Sequence.")
                seq_card = state.field.mz[seq_index]
            else:
                if seq_index < 0 or seq_index >= len(state.field.emz):
                    raise IllegalActionError("Field index out of range for Sequence.")
                seq_card = state.field.emz[seq_index]
            if not seq_card or seq_card.cid != FIENDSMITH_SEQUENCE_ALT_CID:
                raise SimModelError("Selected field card is not Fiendsmith's Sequence.")

            target_cid = state.extra[extra_index].cid
            if target_cid not in FIENDSMITH_FUSION_CIDS:
                raise IllegalActionError("Selected Extra Deck card is not a Fiendsmith Fusion monster.")

            seen = set()
            for idx in gy_indices:
                if not isinstance(idx, int):
                    raise SimModelError("Invalid GY index type for Fiendsmith's Sequence.")
                if idx in seen:
                    raise IllegalActionError("Duplicate GY index for Fiendsmith's Sequence.")
                seen.add(idx)
                if idx < 0 or idx >= len(state.gy):
                    raise IllegalActionError("GY index out of range for Fiendsmith's Sequence.")

            materials = [state.gy[idx] for idx in gy_indices]
            required_count = 2 if target_cid in {FIENDSMITH_LACRIMA_CID, FIENDSMITH_REXTREMENDE_CID} else 3
            if len(materials) != required_count:
                raise IllegalActionError("Fiendsmith's Sequence has invalid material count.")
            if not fiendsmith_fusion_materials_ok(target_cid, materials):
                raise IllegalActionError("Fiendsmith's Sequence materials do not satisfy fusion requirements.")

            new_state = state.clone()
            fusion = new_state.extra.pop(extra_index)
            fusion.properly_summoned = True
            fusion.metadata["from_extra"] = True
            new_state.field.mz[mz_index] = fusion

            removed_by_index = {}
            for idx in sorted(gy_indices, reverse=True):
                removed_by_index[idx] = new_state.gy.pop(idx)
            for idx in gy_indices:
                card = removed_by_index[idx]
                if is_extra_deck_monster(card):
                    new_state.extra.append(card)
                else:
                    new_state.deck.append(card)

            new_state.opt_used[f"{FIENDSMITH_SEQUENCE_ALT_CID}:e1"] = True
            return new_state

        if action.effect_id != "sequence_20226_equip":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{FIENDSMITH_SEQUENCE_ALT_CID}:e2"):
            raise IllegalActionError("Fiendsmith's Sequence equip effect already used.")

        source = action.params.get("source")
        source_index = action.params.get("source_index")
        target_index = action.params.get("target_mz_index")
        if None in (source, source_index, target_index):
            raise SimModelError("Missing params for Fiendsmith's Sequence.")
        if source not in {"mz", "emz", "gy"}:
            raise SimModelError("Invalid source for Fiendsmith's Sequence.")
        if not isinstance(source_index, int) or not isinstance(target_index, int):
            raise SimModelError("Invalid index types for Fiendsmith's Sequence.")
        if target_index < 0 or target_index >= len(state.field.mz):
            raise IllegalActionError("Target index out of range for Fiendsmith's Sequence.")

        target = state.field.mz[target_index]
        if not target or not is_light_fiend_card(target) or is_link_monster(target):
            raise IllegalActionError("Target is not a LIGHT non-Link Fiend monster.")

        if source == "mz":
            if source_index < 0 or source_index >= len(state.field.mz):
                raise IllegalActionError("Source index out of range for Fiendsmith's Sequence.")
            sequence = state.field.mz[source_index]
        elif source == "emz":
            if source_index < 0 or source_index >= len(state.field.emz):
                raise IllegalActionError("Source index out of range for Fiendsmith's Sequence.")
            sequence = state.field.emz[source_index]
        else:
            if source_index < 0 or source_index >= len(state.gy):
                raise IllegalActionError("Source index out of range for Fiendsmith's Sequence.")
            sequence = state.gy[source_index]
        if not sequence or sequence.cid != FIENDSMITH_SEQUENCE_ALT_CID:
            raise SimModelError("Selected source is not Fiendsmith's Sequence.")

        new_state = state.clone()
        if source == "gy":
            sequence_card = new_state.gy.pop(source_index)
        elif source == "mz":
            sequence_card = new_state.field.mz[source_index]
            new_state.field.mz[source_index] = None
        else:
            sequence_card = new_state.field.emz[source_index]
            new_state.field.emz[source_index] = None
        if sequence_card is None:
            raise IllegalActionError("Fiendsmith's Sequence missing for equip.")
        if "link_rating" not in sequence_card.metadata:
            sequence_card.metadata["link_rating"] = 2
        new_state.equip_card(sequence_card, new_state.field.mz[target_index])
        new_state.opt_used[f"{FIENDSMITH_SEQUENCE_ALT_CID}:e2"] = True
        return new_state


class DukeOfDemiseEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "DUKE_BATTLE_INDESTRUCTIBLE" not in state.restrictions:
            for zone, index, card in state.field_cards():
                if card.cid != DUKE_OF_DEMISE_CID:
                    continue
                actions.append(
                    EffectAction(
                        cid=DUKE_OF_DEMISE_CID,
                        name=card.name,
                        effect_id="duke_battle_indestructible",
                        params={"zone": zone, "field_index": index},
                        sort_key=(
                            DUKE_OF_DEMISE_CID,
                            "duke_battle_indestructible",
                            zone,
                            index,
                        ),
                    )
                )

        if "Standby" in str(state.phase) and not state.opt_used.get(f"{DUKE_OF_DEMISE_CID}:e0"):
            for zone, index, card in state.field_cards():
                if card.cid != DUKE_OF_DEMISE_CID:
                    continue
                actions.append(
                    EffectAction(
                        cid=DUKE_OF_DEMISE_CID,
                        name=card.name,
                        effect_id="duke_standby_pay",
                        params={"zone": zone, "field_index": index},
                        sort_key=(
                            DUKE_OF_DEMISE_CID,
                            "duke_standby_pay",
                            zone,
                            index,
                        ),
                    )
                )
                actions.append(
                    EffectAction(
                        cid=DUKE_OF_DEMISE_CID,
                        name=card.name,
                        effect_id="duke_standby_destroy",
                        params={"zone": zone, "field_index": index},
                        sort_key=(
                            DUKE_OF_DEMISE_CID,
                            "duke_standby_destroy",
                            zone,
                            index,
                        ),
                    )
                )

        if "Main Phase" in str(state.phase) and not state.opt_used.get(f"{DUKE_OF_DEMISE_CID}:e2"):
            open_mz = state.open_mz_indices()
            if open_mz:
                for zone, index, card in state.field_cards():
                    if card.cid != DUKE_OF_DEMISE_CID:
                        continue
                    for hand_index, hand_card in enumerate(state.hand):
                        for mz_index in open_mz:
                            actions.append(
                                EffectAction(
                                    cid=DUKE_OF_DEMISE_CID,
                                    name=card.name,
                                    effect_id="duke_extra_normal_summon",
                                    params={
                                        "zone": zone,
                                        "field_index": index,
                                        "hand_index": hand_index,
                                        "mz_index": mz_index,
                                    },
                                    sort_key=(
                                        DUKE_OF_DEMISE_CID,
                                        "duke_extra_normal_summon",
                                        zone,
                                        index,
                                        hand_index,
                                        mz_index,
                                    ),
                                )
                            )

        if "DUKE_DEMISE_GY_TRIGGER" not in state.events:
            return actions
        if state.opt_used.get(f"{DUKE_OF_DEMISE_CID}:e3"):
            return actions

        duke_indices = [idx for idx, card in enumerate(state.gy) if card.cid == DUKE_OF_DEMISE_CID]
        if not duke_indices:
            return actions
        target_indices = [
            idx
            for idx, card in enumerate(state.gy)
            if card.cid != DUKE_OF_DEMISE_CID
            and is_fiend_or_zombie(card)
            and (card_level(card) or 0) >= 4
        ]
        if not target_indices:
            return actions

        for duke_index in duke_indices:
            for target_index in target_indices:
                actions.append(
                    EffectAction(
                        cid=DUKE_OF_DEMISE_CID,
                        name=state.gy[duke_index].name,
                        effect_id="duke_demise_banish_recover",
                        params={"duke_gy_index": duke_index, "target_gy_index": target_index},
                        sort_key=(
                            DUKE_OF_DEMISE_CID,
                            "duke_demise_banish_recover",
                            duke_index,
                            target_index,
                        ),
                    )
                )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "duke_battle_indestructible":
            new_state = state.clone()
            new_state.restrictions.append("DUKE_BATTLE_INDESTRUCTIBLE")
            return new_state

        if action.effect_id == "duke_standby_pay":
            if state.opt_used.get(f"{DUKE_OF_DEMISE_CID}:e0"):
                raise IllegalActionError("The Duke of Demise effect already used.")
            if "Standby" not in str(state.phase):
                raise IllegalActionError("The Duke of Demise requires Standby Phase.")
            new_state = state.clone()
            new_state.restrictions.append("DUKE_STANDBY_COST_PAID")
            new_state.opt_used[f"{DUKE_OF_DEMISE_CID}:e0"] = True
            return new_state

        if action.effect_id == "duke_standby_destroy":
            if state.opt_used.get(f"{DUKE_OF_DEMISE_CID}:e0"):
                raise IllegalActionError("The Duke of Demise effect already used.")
            if "Standby" not in str(state.phase):
                raise IllegalActionError("The Duke of Demise requires Standby Phase.")
            zone = action.params.get("zone")
            field_index = action.params.get("field_index")
            if zone not in {"mz", "emz"} or not isinstance(field_index, int):
                raise SimModelError("Invalid params for The Duke of Demise.")
            new_state = state.clone()
            if zone == "mz":
                card = new_state.field.mz[field_index]
                new_state.field.mz[field_index] = None
            else:
                card = new_state.field.emz[field_index]
                new_state.field.emz[field_index] = None
            if card is None:
                raise IllegalActionError("The Duke of Demise missing for destruction.")
            new_state.gy.append(card)
            new_state.opt_used[f"{DUKE_OF_DEMISE_CID}:e0"] = True
            return new_state

        if action.effect_id == "duke_extra_normal_summon":
            if state.opt_used.get(f"{DUKE_OF_DEMISE_CID}:e2"):
                raise IllegalActionError("The Duke of Demise effect already used.")
            if "Main Phase" not in str(state.phase):
                raise IllegalActionError("The Duke of Demise requires Main Phase.")
            hand_index = action.params.get("hand_index")
            mz_index = action.params.get("mz_index")
            if hand_index is None or mz_index is None:
                raise SimModelError("Missing params for The Duke of Demise.")
            if not isinstance(hand_index, int) or not isinstance(mz_index, int):
                raise SimModelError("Invalid index types for The Duke of Demise.")
            if hand_index < 0 or hand_index >= len(state.hand):
                raise IllegalActionError("Hand index out of range for The Duke of Demise.")
            if mz_index not in state.open_mz_indices():
                raise IllegalActionError("No open Main Monster Zone for The Duke of Demise.")

            new_state = state.clone()
            summoned = new_state.hand.pop(hand_index)
            new_state.field.mz[mz_index] = summoned
            new_state.opt_used[f"{DUKE_OF_DEMISE_CID}:e2"] = True
            return new_state

        if action.effect_id != "duke_demise_banish_recover":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{DUKE_OF_DEMISE_CID}:e3"):
            raise IllegalActionError("The Duke of Demise effect already used.")
        if "DUKE_DEMISE_GY_TRIGGER" not in state.events:
            raise IllegalActionError("The Duke of Demise trigger not present.")

        duke_index = action.params.get("duke_gy_index")
        target_index = action.params.get("target_gy_index")
        if duke_index is None or target_index is None:
            raise SimModelError("Missing params for The Duke of Demise.")
        if not isinstance(duke_index, int) or not isinstance(target_index, int):
            raise SimModelError("Invalid index types for The Duke of Demise.")
        if duke_index < 0 or duke_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for The Duke of Demise.")
        if target_index < 0 or target_index >= len(state.gy):
            raise IllegalActionError("Target GY index out of range for The Duke of Demise.")
        if duke_index == target_index:
            raise IllegalActionError("Target must be another Fiend monster.")
        if state.gy[duke_index].cid != DUKE_OF_DEMISE_CID:
            raise SimModelError("Selected GY card is not The Duke of Demise.")
        target = state.gy[target_index]
        if not is_fiend_or_zombie(target):
            raise IllegalActionError("Target is not a Fiend or Zombie monster.")
        if (card_level(target) or 0) < 4:
            raise IllegalActionError("Target must be Level 4 or higher.")

        new_state = state.clone()
        duke = new_state.gy.pop(duke_index)
        new_state.banished.append(duke)
        target = new_state.gy.pop(target_index if target_index < duke_index else target_index - 1)
        new_state.hand.append(target)
        new_state.opt_used[f"{DUKE_OF_DEMISE_CID}:e3"] = True
        if "DUKE_DEMISE_GY_TRIGGER" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "DUKE_DEMISE_GY_TRIGGER"]
        return new_state


class NecroquipPrincessEffect(EffectImpl):
    """Necroquip Princess - Contact Fusion + Draw effect.

    Summoning Condition:
    "1 monster equipped with a Monster Card + 1 Fiend Monster Card.
    Must be Special Summoned (from your Extra Deck) by sending the above
    cards from your hand and/or field to the GY."

    On-field Effect:
    "If a monster(s) is sent from the hand to the GY to activate a card or effect:
    Draw 1 card. (OPT)"
    """

    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []

        # --- Contact Fusion: SS from Extra Deck ---
        # Requirements:
        # 1. A monster on field equipped with a Monster Card (the host)
        # 2. A Fiend monster (from hand or field)
        # Control: Can only control 1 Necroquip Princess
        necroquip_extra_indices = [
            idx
            for idx, card in enumerate(state.extra)
            if card.cid == NECROQUIP_PRINCESS_CID
        ]
        # Check if we already control Necroquip Princess
        already_controls = any(
            card.cid == NECROQUIP_PRINCESS_CID
            for card in state.field.mz + state.field.emz
            if card
        )
        open_mz = state.open_mz_indices()

        if necroquip_extra_indices and not already_controls and open_mz:
            # Find monsters on field with Monster Card equipped
            hosts_with_equip: list[tuple[str, int]] = []
            for mz_index, card in enumerate(state.field.mz):
                if card and card.equipped:
                    hosts_with_equip.append(("mz", mz_index))
            for emz_index, card in enumerate(state.field.emz):
                if card and card.equipped:
                    hosts_with_equip.append(("emz", emz_index))

            # Find Fiend monsters (from field or hand)
            fiend_sources: list[dict] = []
            for mz_index, card in enumerate(state.field.mz):
                if card and is_fiend_card(card):
                    fiend_sources.append({"source": "field_mz", "index": mz_index})
            for emz_index, card in enumerate(state.field.emz):
                if card and is_fiend_card(card):
                    fiend_sources.append({"source": "field_emz", "index": emz_index})
            for hand_index, card in enumerate(state.hand):
                if is_fiend_card(card):
                    fiend_sources.append({"source": "hand", "index": hand_index})

            for extra_index in necroquip_extra_indices:
                for mz_index in open_mz:
                    for host_zone, host_index in hosts_with_equip:
                        for fiend in fiend_sources:
                            # Cannot use the same monster for both materials
                            if fiend["source"] == "field_mz" and host_zone == "mz" and fiend["index"] == host_index:
                                continue
                            if fiend["source"] == "field_emz" and host_zone == "emz" and fiend["index"] == host_index:
                                continue
                            actions.append(
                                EffectAction(
                                    cid=NECROQUIP_PRINCESS_CID,
                                    name="Necroquip Princess",
                                    effect_id="necroquip_contact_fusion",
                                    params={
                                        "extra_index": extra_index,
                                        "mz_index": mz_index,
                                        "host_zone": host_zone,
                                        "host_index": host_index,
                                        "fiend_source": fiend["source"],
                                        "fiend_index": fiend["index"],
                                    },
                                    sort_key=(
                                        NECROQUIP_PRINCESS_CID,
                                        "necroquip_contact_fusion",
                                        extra_index,
                                        mz_index,
                                        host_zone,
                                        host_index,
                                        fiend["source"],
                                        fiend["index"],
                                    ),
                                )
                            )

        # --- On-field Draw Effect ---
        if "NECROQUIP_TRIGGER" not in state.events:
            return actions
        if state.opt_used.get(f"{NECROQUIP_PRINCESS_CID}:e1"):
            return actions

        for zone, index, card in state.field_cards():
            if card.cid != NECROQUIP_PRINCESS_CID:
                continue
            if not card.properly_summoned:
                continue
            if str(card.metadata.get("summon_type", "")).lower() != "fusion":
                continue
            if state.deck:
                actions.append(
                    EffectAction(
                        cid=NECROQUIP_PRINCESS_CID,
                        name=card.name,
                        effect_id="necroquip_draw",
                        params={"zone": zone, "field_index": index},
                        sort_key=(
                            NECROQUIP_PRINCESS_CID,
                            "necroquip_draw",
                            zone,
                            index,
                        ),
                    )
                )
            if state.last_moved_to_gy:
                for gy_index, target in enumerate(state.gy):
                    if target.cid not in state.last_moved_to_gy:
                        continue
                    actions.append(
                        EffectAction(
                            cid=NECROQUIP_PRINCESS_CID,
                            name=card.name,
                            effect_id="necroquip_equip",
                            params={
                                "zone": zone,
                                "field_index": index,
                                "gy_index": gy_index,
                            },
                            sort_key=(
                                NECROQUIP_PRINCESS_CID,
                                "necroquip_equip",
                                zone,
                                index,
                                gy_index,
                            ),
                        )
                    )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "necroquip_contact_fusion":
            return self._apply_contact_fusion(state, action)
        elif action.effect_id == "necroquip_draw":
            return self._apply_draw(state, action)
        elif action.effect_id == "necroquip_equip":
            return self._apply_equip(state, action)
        else:
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")

    def _apply_contact_fusion(self, state: GameState, action: EffectAction) -> GameState:
        """Contact Fusion: Send 1 monster with equip + 1 Fiend → SS Necroquip Princess."""
        extra_index = action.params.get("extra_index")
        mz_index = action.params.get("mz_index")
        host_zone = action.params.get("host_zone")
        host_index = action.params.get("host_index")
        fiend_source = action.params.get("fiend_source")
        fiend_index = action.params.get("fiend_index")

        if None in (extra_index, mz_index, host_zone, host_index, fiend_source, fiend_index):
            raise SimModelError("Missing params for Necroquip Contact Fusion.")

        # Validate Extra Deck card
        if extra_index < 0 or extra_index >= len(state.extra):
            raise IllegalActionError("Extra index out of range for Necroquip.")
        if state.extra[extra_index].cid != NECROQUIP_PRINCESS_CID:
            raise SimModelError("Selected Extra Deck card is not Necroquip Princess.")

        # Check control restriction
        already_controls = any(
            card.cid == NECROQUIP_PRINCESS_CID
            for card in state.field.mz + state.field.emz
            if card
        )
        if already_controls:
            raise IllegalActionError("Can only control 1 Necroquip Princess.")

        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Necroquip.")

        # Validate host (monster with equip)
        if host_zone == "mz":
            host_card = state.field.mz[host_index] if 0 <= host_index < len(state.field.mz) else None
        elif host_zone == "emz":
            host_card = state.field.emz[host_index] if 0 <= host_index < len(state.field.emz) else None
        else:
            raise SimModelError("Invalid host zone for Necroquip.")

        if not host_card:
            raise IllegalActionError("Host monster not found.")
        if not host_card.equipped:
            raise IllegalActionError("Host monster has no Monster Card equipped.")

        # Validate Fiend material
        if fiend_source == "field_mz":
            fiend_card = state.field.mz[fiend_index] if 0 <= fiend_index < len(state.field.mz) else None
        elif fiend_source == "field_emz":
            fiend_card = state.field.emz[fiend_index] if 0 <= fiend_index < len(state.field.emz) else None
        elif fiend_source == "hand":
            fiend_card = state.hand[fiend_index] if 0 <= fiend_index < len(state.hand) else None
        else:
            raise SimModelError("Invalid fiend source for Necroquip.")

        if not fiend_card:
            raise IllegalActionError("Fiend material not found.")
        if not is_fiend_card(fiend_card):
            raise IllegalActionError("Material is not a Fiend monster.")

        # Execute Contact Fusion
        new_state = state.clone()
        sent_to_gy = []

        # Send host and its equipped cards to GY
        if host_zone == "mz":
            host = new_state.field.mz[host_index]
            new_state.field.mz[host_index] = None
        else:
            host = new_state.field.emz[host_index]
            new_state.field.emz[host_index] = None

        # Equipped cards go to GY with the host
        for equip in host.equipped:
            new_state.gy.append(equip)
            sent_to_gy.append(equip.cid)
        host.equipped = []
        new_state.gy.append(host)
        sent_to_gy.append(host.cid)

        # Send Fiend material to GY
        if fiend_source == "field_mz":
            # Adjust index if host was also from mz and came before
            actual_index = fiend_index
            if host_zone == "mz" and host_index < fiend_index:
                # Host already removed, no adjustment needed as we're using indices
                pass
            fiend = new_state.field.mz[actual_index]
            new_state.field.mz[actual_index] = None
            # Send Fiend's equipped cards too if any
            if fiend.equipped:
                for equip in fiend.equipped:
                    new_state.gy.append(equip)
                    sent_to_gy.append(equip.cid)
                fiend.equipped = []
            new_state.gy.append(fiend)
            sent_to_gy.append(fiend.cid)
        elif fiend_source == "field_emz":
            actual_index = fiend_index
            fiend = new_state.field.emz[actual_index]
            new_state.field.emz[actual_index] = None
            if fiend.equipped:
                for equip in fiend.equipped:
                    new_state.gy.append(equip)
                    sent_to_gy.append(equip.cid)
                fiend.equipped = []
            new_state.gy.append(fiend)
            sent_to_gy.append(fiend.cid)
        else:  # hand
            fiend = new_state.hand.pop(fiend_index)
            new_state.gy.append(fiend)
            sent_to_gy.append(fiend.cid)

        # SS Necroquip Princess from Extra Deck
        necroquip = new_state.extra.pop(extra_index)
        necroquip.properly_summoned = True
        necroquip.metadata["from_extra"] = True
        new_state.field.mz[mz_index] = necroquip

        new_state.last_moved_to_gy = sent_to_gy
        return new_state

    def _apply_draw(self, state: GameState, action: EffectAction) -> GameState:
        """Draw effect when monster sent from hand to GY."""
        if state.opt_used.get(f"{NECROQUIP_PRINCESS_CID}:e1"):
            raise IllegalActionError("Necroquip Princess effect already used.")
        if "NECROQUIP_TRIGGER" not in state.events:
            raise IllegalActionError("Necroquip Princess trigger not present.")
        if not state.deck:
            raise IllegalActionError("No cards to draw for Necroquip Princess.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for Necroquip Princess.")
        if not isinstance(field_index, int):
            raise SimModelError("Invalid index for Necroquip Princess.")

        if zone == "mz":
            card = state.field.mz[field_index] if 0 <= field_index < len(state.field.mz) else None
        else:
            card = state.field.emz[field_index] if 0 <= field_index < len(state.field.emz) else None
        if not card or card.cid != NECROQUIP_PRINCESS_CID:
            raise SimModelError("Selected field card is not Necroquip Princess.")
        if not card.properly_summoned:
            raise IllegalActionError("Necroquip Princess was not properly summoned.")
        if str(card.metadata.get("summon_type", "")).lower() != "fusion":
            raise IllegalActionError("Necroquip Princess is not a Fusion monster.")

        new_state = state.clone()
        drawn = new_state.deck.pop(0)
        new_state.hand.append(drawn)
        new_state.opt_used[f"{NECROQUIP_PRINCESS_CID}:e1"] = True
        if "NECROQUIP_TRIGGER" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "NECROQUIP_TRIGGER"]
        return new_state

    def _apply_equip(self, state: GameState, action: EffectAction) -> GameState:
        if state.opt_used.get(f"{NECROQUIP_PRINCESS_CID}:e1"):
            raise IllegalActionError("Necroquip Princess effect already used.")
        if "NECROQUIP_TRIGGER" not in state.events:
            raise IllegalActionError("Necroquip Princess trigger not present.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        gy_index = action.params.get("gy_index")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for Necroquip Princess.")
        if not isinstance(field_index, int) or not isinstance(gy_index, int):
            raise SimModelError("Invalid index for Necroquip Princess.")
        if gy_index < 0 or gy_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for Necroquip Princess.")
        if state.gy[gy_index].cid not in state.last_moved_to_gy:
            raise IllegalActionError("Necroquip Princess target was not just sent to GY.")

        if zone == "mz":
            card = state.field.mz[field_index] if 0 <= field_index < len(state.field.mz) else None
        else:
            card = state.field.emz[field_index] if 0 <= field_index < len(state.field.emz) else None
        if not card or card.cid != NECROQUIP_PRINCESS_CID:
            raise SimModelError("Selected field card is not Necroquip Princess.")
        if not card.properly_summoned:
            raise IllegalActionError("Necroquip Princess was not properly summoned.")

        new_state = state.clone()
        target = new_state.gy.pop(gy_index)
        host = new_state.field.mz[field_index] if zone == "mz" else new_state.field.emz[field_index]
        new_state.equip_card(target, host)
        new_state.restrictions.append("NECROQUIP_EQUIP_ATK_500")
        new_state.opt_used[f"{NECROQUIP_PRINCESS_CID}:e1"] = True
        new_state.events = [evt for evt in new_state.events if evt != "NECROQUIP_TRIGGER"]
        return new_state


class AerialEaterEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "AERIAL_EATER_TRIGGER" not in state.events:
            pass
        if state.opt_used.get(f"{AERIAL_EATER_CID}:e1"):
            pass

        if "AERIAL_EATER_TRIGGER" in state.events and not state.opt_used.get(
            f"{AERIAL_EATER_CID}:e1"
        ):
            deck_indices = [idx for idx, card in enumerate(state.deck) if is_fiend_card(card)]
            if deck_indices:
                for zone, index, card in state.field_cards():
                    if card.cid != AERIAL_EATER_CID:
                        continue
                    if not card.properly_summoned:
                        continue
                    if str(card.metadata.get("summon_type", "")).lower() != "fusion":
                        continue
                    for deck_index in deck_indices:
                        actions.append(
                            EffectAction(
                                cid=AERIAL_EATER_CID,
                                name=card.name,
                                effect_id="aerial_eater_send",
                                params={"zone": zone, "field_index": index, "deck_index": deck_index},
                                sort_key=(
                                    AERIAL_EATER_CID,
                                    "aerial_eater_send",
                                    zone,
                                    index,
                                    deck_index,
                                ),
                            )
                        )

        if "Main Phase" in str(state.phase) and not state.opt_used.get(f"{AERIAL_EATER_CID}:e2"):
            open_mz = state.open_mz_indices()
            if open_mz:
                for gy_index, card in enumerate(state.gy):
                    if card.cid != AERIAL_EATER_CID:
                        continue
                    if not can_revive_from_gy(card):
                        continue
                    actions.append(
                        EffectAction(
                            cid=AERIAL_EATER_CID,
                            name=card.name,
                            effect_id="aerial_eater_gy_revive",
                            params={
                                "gy_index": gy_index,
                                "mz_index": open_mz[0],
                            },
                            sort_key=(
                                AERIAL_EATER_CID,
                                "aerial_eater_gy_revive",
                                gy_index,
                                open_mz[0],
                            ),
                        )
                    )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "aerial_eater_gy_revive":
            if state.opt_used.get(f"{AERIAL_EATER_CID}:e2"):
                raise IllegalActionError("Aerial Eater effect already used.")
            if "Main Phase" not in str(state.phase):
                raise IllegalActionError("Aerial Eater requires Main Phase.")
            gy_index = action.params.get("gy_index")
            mz_index = action.params.get("mz_index")
            if None in (gy_index, mz_index):
                raise SimModelError("Missing params for Aerial Eater.")
            if not isinstance(gy_index, int) or not isinstance(mz_index, int):
                raise SimModelError("Invalid index types for Aerial Eater.")
            if gy_index < 0 or gy_index >= len(state.gy):
                raise IllegalActionError("GY index out of range for Aerial Eater.")
            if mz_index not in state.open_mz_indices():
                raise IllegalActionError("No open Main Monster Zone for Aerial Eater.")
            if state.gy[gy_index].cid != AERIAL_EATER_CID:
                raise IllegalActionError("Selected GY card is not Aerial Eater.")
            validate_revive_from_gy(state.gy[gy_index])

            new_state = state.clone()
            aerial = new_state.gy.pop(gy_index)
            new_state.field.mz[mz_index] = aerial
            new_state.opt_used[f"{AERIAL_EATER_CID}:e2"] = True
            return new_state

        if action.effect_id != "aerial_eater_send":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{AERIAL_EATER_CID}:e1"):
            raise IllegalActionError("Aerial Eater effect already used.")
        if "AERIAL_EATER_TRIGGER" not in state.events:
            raise IllegalActionError("Aerial Eater trigger not present.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        deck_index = action.params.get("deck_index")
        if None in (zone, field_index, deck_index):
            raise SimModelError("Missing params for Aerial Eater.")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for Aerial Eater.")
        if not isinstance(field_index, int) or not isinstance(deck_index, int):
            raise SimModelError("Invalid index types for Aerial Eater.")
        if deck_index < 0 or deck_index >= len(state.deck):
            raise IllegalActionError("Deck index out of range for Aerial Eater.")

        if zone == "mz":
            card = state.field.mz[field_index] if 0 <= field_index < len(state.field.mz) else None
        else:
            card = state.field.emz[field_index] if 0 <= field_index < len(state.field.emz) else None
        if not card or card.cid != AERIAL_EATER_CID:
            raise SimModelError("Selected field card is not Aerial Eater.")
        if not card.properly_summoned:
            raise IllegalActionError("Aerial Eater was not properly summoned.")
        if str(card.metadata.get("summon_type", "")).lower() != "fusion":
            raise IllegalActionError("Aerial Eater is not a Fusion monster.")

        target = state.deck[deck_index]
        if not is_fiend_card(target):
            raise IllegalActionError("Aerial Eater target is not a Fiend monster.")

        new_state = state.clone()
        sent = new_state.deck.pop(deck_index)
        new_state.gy.append(sent)
        new_state.opt_used[f"{AERIAL_EATER_CID}:e1"] = True
        if "AERIAL_EATER_TRIGGER" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "AERIAL_EATER_TRIGGER"]
        return new_state


class SnakeEyesDoomedDragonEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "Main Phase" in str(state.phase):
            open_mz = state.open_mz_indices()
            stz_indices = [idx for idx, card in enumerate(state.field.stz) if card is not None]
            extra_indices = [
                idx for idx, card in enumerate(state.extra) if card.cid == SNAKE_EYES_DOOMED_DRAGON_CID
            ]
            if open_mz and len(stz_indices) >= 2 and extra_indices:
                for extra_index in extra_indices:
                    for i in range(len(stz_indices)):
                        for j in range(i + 1, len(stz_indices)):
                            actions.append(
                                EffectAction(
                                    cid=SNAKE_EYES_DOOMED_DRAGON_CID,
                                    name=state.extra[extra_index].name,
                                    effect_id="doomed_dragon_contact_summon",
                                    params={
                                        "extra_index": extra_index,
                                        "mz_index": open_mz[0],
                                        "stz_indices": [stz_indices[i], stz_indices[j]],
                                    },
                                    sort_key=(
                                        SNAKE_EYES_DOOMED_DRAGON_CID,
                                        "doomed_dragon_contact_summon",
                                        extra_index,
                                        open_mz[0],
                                        stz_indices[i],
                                        stz_indices[j],
                                    ),
                                )
                            )

        if "DOOMED_DRAGON_TRIGGER" not in state.events:
            return actions
        if state.opt_used.get(f"{SNAKE_EYES_DOOMED_DRAGON_CID}:e1"):
            return actions

        open_stz = [idx for idx, card in enumerate(state.field.stz) if card is None]
        if not open_stz:
            return actions

        for zone, index, card in state.field_cards():
            if card.cid != SNAKE_EYES_DOOMED_DRAGON_CID:
                continue
            if not card.properly_summoned:
                continue
            if str(card.metadata.get("summon_type", "")).lower() != "fusion":
                continue
            for target_index, target in enumerate(state.field.mz):
                if not target:
                    continue
                if target_index == index and zone == "mz":
                    continue
                actions.append(
                    EffectAction(
                        cid=SNAKE_EYES_DOOMED_DRAGON_CID,
                        name=card.name,
                        effect_id="doomed_dragon_move_to_stz",
                        params={
                            "zone": zone,
                            "field_index": index,
                            "target_mz_index": target_index,
                            "stz_index": open_stz[0],
                        },
                        sort_key=(
                            SNAKE_EYES_DOOMED_DRAGON_CID,
                            "doomed_dragon_move_to_stz",
                            zone,
                            index,
                            target_index,
                            open_stz[0],
                        ),
                    )
                )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "doomed_dragon_contact_summon":
            if "Main Phase" not in str(state.phase):
                raise IllegalActionError("Snake-Eyes Doomed Dragon requires Main Phase.")
            extra_index = action.params.get("extra_index")
            mz_index = action.params.get("mz_index")
            stz_indices = action.params.get("stz_indices")
            if None in (extra_index, mz_index, stz_indices):
                raise SimModelError("Missing params for Snake-Eyes Doomed Dragon.")
            if not isinstance(extra_index, int) or not isinstance(mz_index, int):
                raise SimModelError("Invalid index types for Snake-Eyes Doomed Dragon.")
            if not isinstance(stz_indices, list) or len(stz_indices) != 2:
                raise SimModelError("Invalid STZ indices for Snake-Eyes Doomed Dragon.")
            if extra_index < 0 or extra_index >= len(state.extra):
                raise IllegalActionError("Extra index out of range for Snake-Eyes Doomed Dragon.")
            if state.extra[extra_index].cid != SNAKE_EYES_DOOMED_DRAGON_CID:
                raise IllegalActionError("Selected Extra Deck card is not Snake-Eyes Doomed Dragon.")
            if mz_index not in state.open_mz_indices():
                raise IllegalActionError("No open Main Monster Zone for Snake-Eyes Doomed Dragon.")
            for idx in stz_indices:
                if idx < 0 or idx >= len(state.field.stz):
                    raise IllegalActionError("STZ index out of range for Snake-Eyes Doomed Dragon.")
                if state.field.stz[idx] is None:
                    raise IllegalActionError("STZ material missing for Snake-Eyes Doomed Dragon.")

            new_state = state.clone()
            for idx in sorted(stz_indices, reverse=True):
                card = new_state.field.stz[idx]
                new_state.field.stz[idx] = None
                new_state.gy.append(card)

            dragon = new_state.extra.pop(extra_index)
            dragon.properly_summoned = True
            dragon.metadata["from_extra"] = True
            new_state.field.mz[mz_index] = dragon
            return new_state

        if action.effect_id != "doomed_dragon_move_to_stz":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{SNAKE_EYES_DOOMED_DRAGON_CID}:e1"):
            raise IllegalActionError("Snake-Eyes Doomed Dragon effect already used.")
        if "DOOMED_DRAGON_TRIGGER" not in state.events:
            raise IllegalActionError("Snake-Eyes Doomed Dragon trigger not present.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        target_index = action.params.get("target_mz_index")
        stz_index = action.params.get("stz_index")
        if None in (zone, field_index, target_index, stz_index):
            raise SimModelError("Missing params for Snake-Eyes Doomed Dragon.")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for Snake-Eyes Doomed Dragon.")
        if not isinstance(field_index, int) or not isinstance(target_index, int) or not isinstance(stz_index, int):
            raise SimModelError("Invalid index types for Snake-Eyes Doomed Dragon.")
        if stz_index < 0 or stz_index >= len(state.field.stz):
            raise IllegalActionError("STZ index out of range for Snake-Eyes Doomed Dragon.")

        if zone == "mz":
            card = state.field.mz[field_index] if 0 <= field_index < len(state.field.mz) else None
        else:
            card = state.field.emz[field_index] if 0 <= field_index < len(state.field.emz) else None
        if not card or card.cid != SNAKE_EYES_DOOMED_DRAGON_CID:
            raise SimModelError("Selected field card is not Snake-Eyes Doomed Dragon.")
        if not card.properly_summoned:
            raise IllegalActionError("Snake-Eyes Doomed Dragon was not properly summoned.")
        if str(card.metadata.get("summon_type", "")).lower() != "fusion":
            raise IllegalActionError("Snake-Eyes Doomed Dragon is not a Fusion monster.")

        if target_index < 0 or target_index >= len(state.field.mz):
            raise IllegalActionError("Target index out of range for Snake-Eyes Doomed Dragon.")
        if stz_index not in [idx for idx, card in enumerate(state.field.stz) if card is None]:
            raise IllegalActionError("No open STZ for Snake-Eyes Doomed Dragon.")

        new_state = state.clone()
        target = new_state.field.mz[target_index]
        if target is None:
            raise IllegalActionError("Target missing for Snake-Eyes Doomed Dragon.")
        new_state.field.mz[target_index] = None
        target.metadata["as_spell"] = True
        new_state.field.stz[stz_index] = target
        new_state.opt_used[f"{SNAKE_EYES_DOOMED_DRAGON_CID}:e1"] = True
        if "DOOMED_DRAGON_TRIGGER" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "DOOMED_DRAGON_TRIGGER"]
        return new_state


class ABaoAQuEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "Main Phase" in str(state.phase) and not state.opt_used.get(f"{A_BAO_A_QU_CID}:e1"):
            open_mz = state.open_mz_indices()
            if state.hand:
                for zone, index, card in state.field_cards():
                    if card.cid != A_BAO_A_QU_CID:
                        continue
                    if not card.properly_summoned:
                        continue
                    if str(card.metadata.get("summon_type", "")).lower() != "link":
                        continue
                    field_targets = []
                    for t_zone, t_index, t_card in state.field_cards():
                        if t_zone == zone and t_index == index:
                            continue
                        field_targets.append((t_zone, t_index))
                    for stz_index, stz_card in enumerate(state.field.stz):
                        if stz_card:
                            field_targets.append(("stz", stz_index))
                    for fz_index, fz_card in enumerate(state.field.fz):
                        if fz_card:
                            field_targets.append(("fz", fz_index))
                    for hand_index, _hand in enumerate(state.hand):
                        for target_zone, target_index in field_targets:
                            actions.append(
                                EffectAction(
                                    cid=A_BAO_A_QU_CID,
                                    name=card.name,
                                    effect_id="abao_discard_destroy",
                                    params={
                                        "zone": zone,
                                        "field_index": index,
                                        "hand_index": hand_index,
                                        "target_zone": target_zone,
                                        "target_index": target_index,
                                    },
                                    sort_key=(
                                        A_BAO_A_QU_CID,
                                        "abao_discard_destroy",
                                        zone,
                                        index,
                                        hand_index,
                                        target_zone,
                                        target_index,
                                    ),
                                )
                            )
                        if not open_mz:
                            continue
                        for gy_index, target in enumerate(state.gy):
                            attr = str(target.metadata.get("attribute", "")).upper()
                            if attr not in {"LIGHT", "DARK"}:
                                continue
                            for mz_index in open_mz:
                                actions.append(
                                    EffectAction(
                                        cid=A_BAO_A_QU_CID,
                                        name=card.name,
                                        effect_id="abao_discard_banish_revive",
                                        params={
                                            "zone": zone,
                                            "field_index": index,
                                            "hand_index": hand_index,
                                            "gy_index": gy_index,
                                            "mz_index": mz_index,
                                        },
                                        sort_key=(
                                            A_BAO_A_QU_CID,
                                            "abao_discard_banish_revive",
                                            zone,
                                            index,
                                            hand_index,
                                            gy_index,
                                            mz_index,
                                        ),
                                    )
                                )

        if "Standby" in str(state.phase) and not state.opt_used.get(f"{A_BAO_A_QU_CID}:e2"):
            for zone, index, card in state.field_cards():
                if card.cid != A_BAO_A_QU_CID:
                    continue
                types = {str(c.metadata.get("race", "")).upper() for c in state.gy if c}
                types.discard("")
                count = len(types)
                if count <= 0:
                    continue
                if len(state.deck) < count or len(state.hand) < count:
                    continue
                actions.append(
                    EffectAction(
                        cid=A_BAO_A_QU_CID,
                        name=card.name,
                        effect_id="abao_standby_draw_cycle",
                        params={"zone": zone, "field_index": index, "count": count},
                        sort_key=(
                            A_BAO_A_QU_CID,
                            "abao_standby_draw_cycle",
                            zone,
                            index,
                            count,
                        ),
                    )
                )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "abao_discard_destroy":
            if state.opt_used.get(f"{A_BAO_A_QU_CID}:e1"):
                raise IllegalActionError("A Bao A Qu effect already used.")
            if "Main Phase" not in str(state.phase):
                raise IllegalActionError("A Bao A Qu requires Main Phase.")

            zone = action.params.get("zone")
            field_index = action.params.get("field_index")
            hand_index = action.params.get("hand_index")
            target_zone = action.params.get("target_zone")
            target_index = action.params.get("target_index")
            if None in (zone, field_index, hand_index, target_zone, target_index):
                raise SimModelError("Missing params for A Bao A Qu.")
            if zone not in {"mz", "emz"}:
                raise SimModelError("Invalid zone for A Bao A Qu.")
            if target_zone not in {"mz", "emz", "stz", "fz"}:
                raise SimModelError("Invalid target zone for A Bao A Qu.")
            if not isinstance(field_index, int) or not isinstance(hand_index, int):
                raise SimModelError("Invalid index types for A Bao A Qu.")
            if hand_index < 0 or hand_index >= len(state.hand):
                raise IllegalActionError("Hand index out of range for A Bao A Qu.")

            if zone == "mz":
                card = state.field.mz[field_index] if 0 <= field_index < len(state.field.mz) else None
            else:
                card = state.field.emz[field_index] if 0 <= field_index < len(state.field.emz) else None
            if not card or card.cid != A_BAO_A_QU_CID:
                raise SimModelError("Selected field card is not A Bao A Qu.")
            if not card.properly_summoned:
                raise IllegalActionError("A Bao A Qu was not properly summoned.")
            if str(card.metadata.get("summon_type", "")).lower() != "link":
                raise IllegalActionError("A Bao A Qu is not a Link monster.")

            new_state = state.clone()
            discarded = new_state.hand.pop(hand_index)
            new_state.gy.append(discarded)

            if target_zone == "mz":
                if target_index < 0 or target_index >= len(new_state.field.mz):
                    raise IllegalActionError("Target index out of range for A Bao A Qu.")
                target = new_state.field.mz[target_index]
                new_state.field.mz[target_index] = None
            elif target_zone == "emz":
                if target_index < 0 or target_index >= len(new_state.field.emz):
                    raise IllegalActionError("Target index out of range for A Bao A Qu.")
                target = new_state.field.emz[target_index]
                new_state.field.emz[target_index] = None
            elif target_zone == "stz":
                if target_index < 0 or target_index >= len(new_state.field.stz):
                    raise IllegalActionError("Target index out of range for A Bao A Qu.")
                target = new_state.field.stz[target_index]
                new_state.field.stz[target_index] = None
            else:
                if target_index < 0 or target_index >= len(new_state.field.fz):
                    raise IllegalActionError("Target index out of range for A Bao A Qu.")
                target = new_state.field.fz[target_index]
                new_state.field.fz[target_index] = None
            if target is None:
                raise IllegalActionError("A Bao A Qu target missing.")
            new_state.gy.append(target)
            new_state.opt_used[f"{A_BAO_A_QU_CID}:e1"] = True
            return new_state

        if action.effect_id == "abao_standby_draw_cycle":
            if state.opt_used.get(f"{A_BAO_A_QU_CID}:e2"):
                raise IllegalActionError("A Bao A Qu effect already used.")
            if "Standby" not in str(state.phase):
                raise IllegalActionError("A Bao A Qu requires Standby Phase.")

            count = action.params.get("count")
            if not isinstance(count, int) or count <= 0:
                raise SimModelError("Invalid draw count for A Bao A Qu.")
            if len(state.deck) < count or len(state.hand) < count:
                raise IllegalActionError("Not enough cards for A Bao A Qu draw/cycle.")

            new_state = state.clone()
            drawn = []
            for _ in range(count):
                drawn.append(new_state.deck.pop(0))
            new_state.hand.extend(drawn)

            hand_indices = list(range(len(new_state.hand)))
            hand_indices.sort(
                key=lambda idx: (new_state.hand[idx].name.lower(), idx)
            )
            for idx in sorted(hand_indices[:count], reverse=True):
                new_state.deck.append(new_state.hand.pop(idx))

            new_state.opt_used[f"{A_BAO_A_QU_CID}:e2"] = True
            return new_state

        if action.effect_id != "abao_discard_banish_revive":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{A_BAO_A_QU_CID}:e1"):
            raise IllegalActionError("A Bao A Qu effect already used.")
        if "Main Phase" not in str(state.phase):
            raise IllegalActionError("A Bao A Qu requires Main Phase.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        hand_index = action.params.get("hand_index")
        gy_index = action.params.get("gy_index")
        mz_index = action.params.get("mz_index")
        if None in (zone, field_index, hand_index, gy_index, mz_index):
            raise SimModelError("Missing params for A Bao A Qu.")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for A Bao A Qu.")
        if not isinstance(field_index, int) or not isinstance(hand_index, int) or not isinstance(gy_index, int):
            raise SimModelError("Invalid index types for A Bao A Qu.")
        if hand_index < 0 or hand_index >= len(state.hand):
            raise IllegalActionError("Hand index out of range for A Bao A Qu.")
        if gy_index < 0 or gy_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for A Bao A Qu.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for A Bao A Qu.")

        if zone == "mz":
            card = state.field.mz[field_index] if 0 <= field_index < len(state.field.mz) else None
        else:
            card = state.field.emz[field_index] if 0 <= field_index < len(state.field.emz) else None
        if not card or card.cid != A_BAO_A_QU_CID:
            raise SimModelError("Selected field card is not A Bao A Qu.")
        if not card.properly_summoned:
            raise IllegalActionError("A Bao A Qu was not properly summoned.")
        if str(card.metadata.get("summon_type", "")).lower() != "link":
            raise IllegalActionError("A Bao A Qu is not a Link monster.")

        target = state.gy[gy_index]
        attr = str(target.metadata.get("attribute", "")).upper()
        if attr not in {"LIGHT", "DARK"}:
            raise IllegalActionError("A Bao A Qu target must be LIGHT or DARK.")

        new_state = state.clone()
        discarded = new_state.hand.pop(hand_index)
        new_state.gy.append(discarded)
        if zone == "mz":
            abao = new_state.field.mz[field_index]
            new_state.field.mz[field_index] = None
        else:
            abao = new_state.field.emz[field_index]
            new_state.field.emz[field_index] = None
        if abao is None:
            raise IllegalActionError("A Bao A Qu missing from field.")
        new_state.banished.append(abao)
        revived = new_state.gy.pop(gy_index)
        new_state.field.mz[mz_index] = revived
        new_state.opt_used[f"{A_BAO_A_QU_CID}:e1"] = True
        return new_state


class BuioDawnsLightEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "LR_MZ_INDESTRUCTIBLE" not in state.restrictions:
            for zone, index, card in state.field_cards():
                if card.cid != BUIO_DAWNS_LIGHT_CID:
                    continue
                actions.append(
                    EffectAction(
                        cid=BUIO_DAWNS_LIGHT_CID,
                        name=card.name,
                        effect_id="buio_lr_protect",
                        params={"zone": zone, "field_index": index},
                        sort_key=(
                            BUIO_DAWNS_LIGHT_CID,
                            "buio_lr_protect",
                            zone,
                            index,
                        ),
                    )
                )
        if "Main Phase" in str(state.phase) and not state.opt_used.get(f"{BUIO_DAWNS_LIGHT_CID}:e1"):
            open_mz = state.open_mz_indices()
            if open_mz:
                for hand_index, card in enumerate(state.hand):
                    if card.cid != BUIO_DAWNS_LIGHT_CID:
                        continue
                    for target_index, target in enumerate(state.field.mz):
                        if not target:
                            continue
                        if not is_fiend_card(target):
                            continue
                        actions.append(
                            EffectAction(
                                cid=BUIO_DAWNS_LIGHT_CID,
                                name=card.name,
                                effect_id="buio_hand_ss",
                                params={
                                    "hand_index": hand_index,
                                    "target_mz_index": target_index,
                                    "mz_index": open_mz[0],
                                },
                                sort_key=(
                                    BUIO_DAWNS_LIGHT_CID,
                                    "buio_hand_ss",
                                    hand_index,
                                    target_index,
                                    open_mz[0],
                                ),
                            )
                        )

        if not state.opt_used.get(f"{BUIO_DAWNS_LIGHT_CID}:e2"):
            if BUIO_DAWNS_LIGHT_CID in state.last_moved_to_gy:
                buio_indices = [
                    idx for idx, card in enumerate(state.gy) if card.cid == BUIO_DAWNS_LIGHT_CID
                ]
                if buio_indices:
                    for deck_index, card in enumerate(state.deck):
                        if card.cid != MUTINY_IN_THE_SKY_CID:
                            continue
                        for buio_index in buio_indices:
                            actions.append(
                                EffectAction(
                                    cid=BUIO_DAWNS_LIGHT_CID,
                                    name=state.gy[buio_index].name,
                                    effect_id="buio_gy_search_mutiny",
                                    params={
                                        "buio_gy_index": buio_index,
                                        "deck_index": deck_index,
                                    },
                                    sort_key=(
                                        BUIO_DAWNS_LIGHT_CID,
                                        "buio_gy_search_mutiny",
                                        buio_index,
                                        deck_index,
                                    ),
                                )
                            )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "buio_lr_protect":
            new_state = state.clone()
            new_state.restrictions.append("LR_MZ_INDESTRUCTIBLE")
            return new_state

        if action.effect_id == "buio_hand_ss":
            if state.opt_used.get(f"{BUIO_DAWNS_LIGHT_CID}:e1"):
                raise IllegalActionError("Buio effect already used.")
            if "Main Phase" not in str(state.phase):
                raise IllegalActionError("Buio requires Main Phase.")

            hand_index = action.params.get("hand_index")
            target_index = action.params.get("target_mz_index")
            mz_index = action.params.get("mz_index")
            if None in (hand_index, target_index, mz_index):
                raise SimModelError("Missing params for Buio.")
            if not isinstance(hand_index, int) or not isinstance(target_index, int) or not isinstance(mz_index, int):
                raise SimModelError("Invalid index types for Buio.")
            if hand_index < 0 or hand_index >= len(state.hand):
                raise IllegalActionError("Hand index out of range for Buio.")
            if mz_index not in state.open_mz_indices():
                raise IllegalActionError("No open Main Monster Zone for Buio.")
            if target_index < 0 or target_index >= len(state.field.mz):
                raise IllegalActionError("Target index out of range for Buio.")

            target = state.field.mz[target_index]
            if not target or not is_fiend_card(target):
                raise IllegalActionError("Buio target must be a Fiend monster.")
            if state.hand[hand_index].cid != BUIO_DAWNS_LIGHT_CID:
                raise SimModelError("Selected hand card is not Buio.")

            new_state = state.clone()
            buio = new_state.hand.pop(hand_index)
            new_state.field.mz[mz_index] = buio
            new_state.field.mz[target_index].metadata["effects_negated"] = True
            new_state.opt_used[f"{BUIO_DAWNS_LIGHT_CID}:e1"] = True
            return new_state

        if action.effect_id == "buio_gy_search_mutiny":
            if state.opt_used.get(f"{BUIO_DAWNS_LIGHT_CID}:e2"):
                raise IllegalActionError("Buio GY effect already used.")
            if BUIO_DAWNS_LIGHT_CID not in state.last_moved_to_gy:
                raise IllegalActionError("Buio was not just sent to GY.")

            buio_index = action.params.get("buio_gy_index")
            deck_index = action.params.get("deck_index")
            if buio_index is None or deck_index is None:
                raise SimModelError("Missing params for Buio GY.")
            if not isinstance(buio_index, int) or not isinstance(deck_index, int):
                raise SimModelError("Invalid index types for Buio GY.")
            if buio_index < 0 or buio_index >= len(state.gy):
                raise IllegalActionError("Buio GY index out of range.")
            if deck_index < 0 or deck_index >= len(state.deck):
                raise IllegalActionError("Deck index out of range for Buio.")
            if state.gy[buio_index].cid != BUIO_DAWNS_LIGHT_CID:
                raise SimModelError("Selected GY card is not Buio.")
            if state.deck[deck_index].cid != MUTINY_IN_THE_SKY_CID:
                raise IllegalActionError("Deck target is not Mutiny in the Sky.")

            new_state = state.clone()
            mutiny = new_state.deck.pop(deck_index)
            new_state.hand.append(mutiny)
            new_state.opt_used[f"{BUIO_DAWNS_LIGHT_CID}:e2"] = True
            new_state.last_moved_to_gy = []
            return new_state

        raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")


class LuceDusksDarkEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "LR_MZ_INDESTRUCTIBLE" not in state.restrictions:
            for zone, index, card in state.field_cards():
                if card.cid != LUCE_DUSKS_DARK_CID:
                    continue
                actions.append(
                    EffectAction(
                        cid=LUCE_DUSKS_DARK_CID,
                        name=card.name,
                        effect_id="luce_lr_protect",
                        params={"zone": zone, "field_index": index},
                        sort_key=(
                            LUCE_DUSKS_DARK_CID,
                            "luce_lr_protect",
                            zone,
                            index,
                        ),
                    )
                )
        if "Main Phase" not in str(state.phase):
            return actions

        if not state.opt_used.get(f"{LUCE_DUSKS_DARK_CID}:e1"):
            deck_indices = [idx for idx, card in enumerate(state.deck) if is_fairy_or_fiend(card)]
            field_targets = []
            for zone, index, card in state.field_cards():
                field_targets.append((zone, index, card))
            for stz_index, stz_card in enumerate(state.field.stz):
                if stz_card:
                    field_targets.append(("stz", stz_index, stz_card))
            for fz_index, fz_card in enumerate(state.field.fz):
                if fz_card:
                    field_targets.append(("fz", fz_index, fz_card))
            if deck_indices and field_targets:
                for zone, index, card in state.field_cards():
                    if card.cid != LUCE_DUSKS_DARK_CID:
                        continue
                    if not card.properly_summoned:
                        continue
                    if str(card.metadata.get("summon_type", "")).lower() != "fusion":
                        continue
                    for deck_index in deck_indices:
                        for target_zone, target_index, target_card in field_targets:
                            if target_zone == zone and target_index == index:
                                continue
                            actions.append(
                                EffectAction(
                                    cid=LUCE_DUSKS_DARK_CID,
                                    name=card.name,
                                    effect_id="luce_send_and_destroy",
                                    params={
                                        "zone": zone,
                                        "field_index": index,
                                        "deck_index": deck_index,
                                        "target_zone": target_zone,
                                        "target_index": target_index,
                                    },
                                    sort_key=(
                                        LUCE_DUSKS_DARK_CID,
                                        "luce_send_and_destroy",
                                        zone,
                                        index,
                                        deck_index,
                                        target_zone,
                                        target_index,
                                    ),
                                )
                            )

        if "LUCE_DESTROY_TRIGGER" not in state.events:
            return actions
        if state.opt_used.get(f"{LUCE_DUSKS_DARK_CID}:e2"):
            return actions

        field_targets = []
        for zone, index, card in state.field_cards():
            field_targets.append((zone, index, card))
        for stz_index, stz_card in enumerate(state.field.stz):
            if stz_card:
                field_targets.append(("stz", stz_index, stz_card))
        for fz_index, fz_card in enumerate(state.field.fz):
            if fz_card:
                field_targets.append(("fz", fz_index, fz_card))

        for zone, index, card in state.field_cards():
            if card.cid != LUCE_DUSKS_DARK_CID:
                continue
            if not card.properly_summoned:
                continue
            if str(card.metadata.get("summon_type", "")).lower() != "fusion":
                continue
            for target_zone, target_index, target_card in field_targets:
                if target_zone == zone and target_index == index:
                    continue
                actions.append(
                    EffectAction(
                        cid=LUCE_DUSKS_DARK_CID,
                        name=card.name,
                        effect_id="luce_destroy_card",
                        params={
                            "zone": zone,
                            "field_index": index,
                            "target_zone": target_zone,
                            "target_index": target_index,
                        },
                        sort_key=(
                            LUCE_DUSKS_DARK_CID,
                            "luce_destroy_card",
                            zone,
                            index,
                            target_zone,
                            target_index,
                        ),
                    )
                )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "luce_lr_protect":
            new_state = state.clone()
            new_state.restrictions.append("LR_MZ_INDESTRUCTIBLE")
            return new_state

        if action.effect_id == "luce_destroy_card":
            if state.opt_used.get(f"{LUCE_DUSKS_DARK_CID}:e2"):
                raise IllegalActionError("Luce effect already used.")
            if "LUCE_DESTROY_TRIGGER" not in state.events:
                raise IllegalActionError("Luce trigger not present.")

            zone = action.params.get("zone")
            field_index = action.params.get("field_index")
            target_zone = action.params.get("target_zone")
            target_index = action.params.get("target_index")
            if None in (zone, field_index, target_zone, target_index):
                raise SimModelError("Missing params for Luce.")
            if zone not in {"mz", "emz"}:
                raise SimModelError("Invalid zone for Luce.")
            if target_zone not in {"mz", "emz", "stz", "fz"}:
                raise SimModelError("Invalid target zone for Luce.")
            if not isinstance(field_index, int) or not isinstance(target_index, int):
                raise SimModelError("Invalid index types for Luce.")

            if zone == "mz":
                card = state.field.mz[field_index] if 0 <= field_index < len(state.field.mz) else None
            else:
                card = state.field.emz[field_index] if 0 <= field_index < len(state.field.emz) else None
            if not card or card.cid != LUCE_DUSKS_DARK_CID:
                raise SimModelError("Selected field card is not Luce.")
            if not card.properly_summoned:
                raise IllegalActionError("Luce was not properly summoned.")
            if str(card.metadata.get("summon_type", "")).lower() != "fusion":
                raise IllegalActionError("Luce is not a Fusion monster.")

            new_state = state.clone()
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
                raise IllegalActionError("Luce target missing.")
            new_state.gy.append(target)
            new_state.opt_used[f"{LUCE_DUSKS_DARK_CID}:e2"] = True
            new_state.events = [evt for evt in new_state.events if evt != "LUCE_DESTROY_TRIGGER"]
            return new_state

        if action.effect_id != "luce_send_and_destroy":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{LUCE_DUSKS_DARK_CID}:e1"):
            raise IllegalActionError("Luce effect already used.")
        if "Main Phase" not in str(state.phase):
            raise IllegalActionError("Luce requires Main Phase.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        deck_index = action.params.get("deck_index")
        target_zone = action.params.get("target_zone")
        target_index = action.params.get("target_index")
        if None in (zone, field_index, deck_index, target_zone, target_index):
            raise SimModelError("Missing params for Luce.")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for Luce.")
        if target_zone not in {"mz", "emz", "stz", "fz"}:
            raise SimModelError("Invalid target zone for Luce.")
        if not isinstance(field_index, int) or not isinstance(deck_index, int) or not isinstance(target_index, int):
            raise SimModelError("Invalid index types for Luce.")
        if deck_index < 0 or deck_index >= len(state.deck):
            raise IllegalActionError("Deck index out of range for Luce.")

        if zone == "mz":
            card = state.field.mz[field_index] if 0 <= field_index < len(state.field.mz) else None
        else:
            card = state.field.emz[field_index] if 0 <= field_index < len(state.field.emz) else None
        if not card or card.cid != LUCE_DUSKS_DARK_CID:
            raise SimModelError("Selected field card is not Luce.")
        if not card.properly_summoned:
            raise IllegalActionError("Luce was not properly summoned.")
        if str(card.metadata.get("summon_type", "")).lower() != "fusion":
            raise IllegalActionError("Luce is not a Fusion monster.")

        target_deck = state.deck[deck_index]
        if not is_fairy_or_fiend(target_deck):
            raise IllegalActionError("Luce deck target must be Fiend or Fairy.")

        new_state = state.clone()
        sent = new_state.deck.pop(deck_index)
        new_state.gy.append(sent)

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
            raise IllegalActionError("Luce target missing.")
        new_state.gy.append(target)
        new_state.opt_used[f"{LUCE_DUSKS_DARK_CID}:e1"] = True
        return new_state


class MutinyInTheSkyEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if "Main Phase" in str(state.phase) and not state.opt_used.get(f"{MUTINY_IN_THE_SKY_CID}:e1"):
            open_mz = state.open_mz_indices()
            mutiny_indices = [idx for idx, card in enumerate(state.hand) if card.cid == MUTINY_IN_THE_SKY_CID]
            if open_mz and mutiny_indices:
                fusion_targets = [
                    (idx, card)
                    for idx, card in enumerate(state.extra)
                    if str(card.metadata.get("summon_type", "")).lower() == "fusion"
                    and is_fairy_or_fiend(card)
                ]
                gy_indices = [
                    idx for idx, card in enumerate(state.gy) if is_fairy_or_fiend(card)
                ]
                for hand_index in mutiny_indices:
                    for extra_index, fusion_card in fusion_targets:
                        min_materials = int(fusion_card.metadata.get("min_materials", 2))
                        if len(gy_indices) < min_materials:
                            continue
                        for combo in itertools.combinations(gy_indices, min_materials):
                            actions.append(
                                EffectAction(
                                    cid=MUTINY_IN_THE_SKY_CID,
                                    name=state.hand[hand_index].name,
                                    effect_id="mutiny_fusion_summon",
                                    params={
                                        "hand_index": hand_index,
                                        "extra_index": extra_index,
                                        "mz_index": open_mz[0],
                                        "gy_indices": list(combo),
                                    },
                                    sort_key=(
                                        MUTINY_IN_THE_SKY_CID,
                                        "mutiny_fusion_summon",
                                        hand_index,
                                        extra_index,
                                        open_mz[0],
                                        tuple(combo),
                                    ),
                                )
                            )

        if "Main Phase" in str(state.phase) and not state.opt_used.get(f"{MUTINY_IN_THE_SKY_CID}:e2"):
            for gy_index, card in enumerate(state.gy):
                if card.cid != MUTINY_IN_THE_SKY_CID:
                    continue
                actions.append(
                    EffectAction(
                        cid=MUTINY_IN_THE_SKY_CID,
                        name=card.name,
                        effect_id="mutiny_gy_add",
                        params={"gy_index": gy_index},
                        sort_key=(
                            MUTINY_IN_THE_SKY_CID,
                            "mutiny_gy_add",
                            gy_index,
                        ),
                    )
                )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "mutiny_fusion_summon":
            if state.opt_used.get(f"{MUTINY_IN_THE_SKY_CID}:e1"):
                raise IllegalActionError("Mutiny effect already used.")
            if "Main Phase" not in str(state.phase):
                raise IllegalActionError("Mutiny requires Main Phase.")

            hand_index = action.params.get("hand_index")
            extra_index = action.params.get("extra_index")
            mz_index = action.params.get("mz_index")
            gy_indices = action.params.get("gy_indices")
            if None in (hand_index, extra_index, mz_index, gy_indices):
                raise SimModelError("Missing params for Mutiny.")
            if not isinstance(hand_index, int) or not isinstance(extra_index, int) or not isinstance(mz_index, int):
                raise SimModelError("Invalid index types for Mutiny.")
            if not isinstance(gy_indices, list):
                raise SimModelError("Invalid GY indices for Mutiny.")
            if hand_index < 0 or hand_index >= len(state.hand):
                raise IllegalActionError("Hand index out of range for Mutiny.")
            if extra_index < 0 or extra_index >= len(state.extra):
                raise IllegalActionError("Extra index out of range for Mutiny.")
            if mz_index not in state.open_mz_indices():
                raise IllegalActionError("No open Main Monster Zone for Mutiny.")

            if state.hand[hand_index].cid != MUTINY_IN_THE_SKY_CID:
                raise SimModelError("Selected hand card is not Mutiny in the Sky.")
            extra_card = state.extra[extra_index]
            if str(extra_card.metadata.get("summon_type", "")).lower() != "fusion":
                raise IllegalActionError("Selected Extra Deck card is not a Fusion monster.")
            if not is_fairy_or_fiend(extra_card):
                raise IllegalActionError("Selected Extra Deck card is not Fiend or Fairy.")
            min_materials = int(extra_card.metadata.get("min_materials", 2))

            seen = set()
            for idx in gy_indices:
                if not isinstance(idx, int):
                    raise SimModelError("Invalid GY index type for Mutiny.")
                if idx in seen:
                    raise IllegalActionError("Duplicate GY index for Mutiny.")
                seen.add(idx)
                if idx < 0 or idx >= len(state.gy):
                    raise IllegalActionError("GY index out of range for Mutiny.")
            if len(gy_indices) != min_materials:
                raise IllegalActionError("Invalid GY indices for Mutiny.")

            materials = [state.gy[idx] for idx in gy_indices]
            if not all(is_fairy_or_fiend(card) for card in materials):
                raise IllegalActionError("Mutiny materials must be Fiend or Fairy monsters.")

            new_state = state.clone()
            mutiny = new_state.hand.pop(hand_index)
            new_state.gy.append(mutiny)

            fusion = new_state.extra.pop(extra_index)
            fusion.properly_summoned = True
            fusion.metadata["from_extra"] = True
            new_state.field.mz[mz_index] = fusion

            removed = {}
            for idx in sorted(gy_indices, reverse=True):
                removed[idx] = new_state.gy.pop(idx)
            for idx in gy_indices:
                card = removed[idx]
                if is_extra_deck_monster(card):
                    new_state.extra.append(card)
                else:
                    new_state.deck.append(card)

            new_state.opt_used[f"{MUTINY_IN_THE_SKY_CID}:e1"] = True
            return new_state

        if action.effect_id == "mutiny_gy_add":
            if state.opt_used.get(f"{MUTINY_IN_THE_SKY_CID}:e2"):
                raise IllegalActionError("Mutiny GY effect already used.")
            if "Main Phase" not in str(state.phase):
                raise IllegalActionError("Mutiny requires Main Phase.")

            gy_index = action.params.get("gy_index")
            if gy_index is None:
                raise SimModelError("Missing params for Mutiny GY.")
            if not isinstance(gy_index, int):
                raise SimModelError("Invalid index type for Mutiny GY.")
            if gy_index < 0 or gy_index >= len(state.gy):
                raise IllegalActionError("GY index out of range for Mutiny GY.")
            if state.gy[gy_index].cid != MUTINY_IN_THE_SKY_CID:
                raise SimModelError("Selected GY card is not Mutiny in the Sky.")

            new_state = state.clone()
            mutiny = new_state.gy.pop(gy_index)
            new_state.hand.append(mutiny)
            new_state.opt_used[f"{MUTINY_IN_THE_SKY_CID}:e2"] = True
            return new_state

        raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")


class FabledLurrieEffect(EffectImpl):
    """Fabled Lurrie: If this card is discarded to the GY: Special Summon it.

    Verified against: https://github.com/ProjectIgnis/CardScripts/blob/master/official/c97651498.lua
    Trigger: When discarded from hand to GY (REASON_DISCARD)
    NOT once per turn - triggers every time it's discarded
    """

    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        # Check for LURRIE_DISCARD_TRIGGER event (set when Lurrie is discarded)
        if "LURRIE_DISCARD_TRIGGER" not in state.events:
            return actions
        if FABLED_LURRIE_CID not in state.last_moved_to_gy:
            return actions

        # Find Lurrie in GY
        lurrie_indices = [
            idx for idx, card in enumerate(state.gy) if card.cid == FABLED_LURRIE_CID
        ]
        if not lurrie_indices:
            return actions

        open_mz = state.open_mz_indices()
        if not open_mz:
            return actions

        for gy_index in lurrie_indices:
            for mz_index in open_mz:
                actions.append(
                    EffectAction(
                        cid=FABLED_LURRIE_CID,
                        name=state.gy[gy_index].name,
                        effect_id="lurrie_discard_ss_self",
                        params={"gy_index": gy_index, "mz_index": mz_index},
                        sort_key=(
                            FABLED_LURRIE_CID,
                            "lurrie_discard_ss_self",
                            gy_index,
                            mz_index,
                        ),
                    )
                )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id != "lurrie_discard_ss_self":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if "LURRIE_DISCARD_TRIGGER" not in state.events:
            raise IllegalActionError("Fabled Lurrie trigger not present.")
        if FABLED_LURRIE_CID not in state.last_moved_to_gy:
            raise IllegalActionError("Fabled Lurrie was not just discarded.")

        gy_index = action.params.get("gy_index")
        mz_index = action.params.get("mz_index")
        if gy_index is None or mz_index is None:
            raise SimModelError("Missing params for Fabled Lurrie effect.")
        if not isinstance(gy_index, int) or not isinstance(mz_index, int):
            raise SimModelError("Invalid index types for Fabled Lurrie effect.")
        if gy_index < 0 or gy_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for Fabled Lurrie.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Fabled Lurrie.")
        if state.gy[gy_index].cid != FABLED_LURRIE_CID:
            raise SimModelError("Selected GY card is not Fabled Lurrie.")

        new_state = state.clone()
        lurrie = new_state.gy.pop(gy_index)
        lurrie.properly_summoned = True
        new_state.field.mz[mz_index] = lurrie
        # Clear the trigger (Lurrie's effect is NOT OPT, but each discard is a separate trigger)
        new_state.last_moved_to_gy = [cid for cid in new_state.last_moved_to_gy if cid != FABLED_LURRIE_CID]
        if "LURRIE_DISCARD_TRIGGER" in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != "LURRIE_DISCARD_TRIGGER"]
        return new_state
