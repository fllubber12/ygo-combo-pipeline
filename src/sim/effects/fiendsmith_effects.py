from __future__ import annotations

from ..errors import IllegalActionError, SimModelError
from ..state import (
    CardInstance,
    GameState,
    can_revive_from_gy,
    is_extra_deck_monster,
    validate_revive_from_gy,
)
from .types import EffectAction, EffectImpl

FIENDSMITH_ENGRAVER_CID = "20196"
FIENDSMITH_TRACT_CID = "20240"
FIENDSMITH_SANCT_CID = "20241"
FIENDSMITH_DESIRAE_CID = "20215"
FIENDSMITH_REQUIEM_CID = "20225"
FIENDSMITH_LACRIMA_CID = "20214"
FIENDSMITH_LACRIMA_CRIMSON_CID = "20490"
FIENDSMITH_PARADISE_CID = "20251"
FIENDSMITH_IN_PARADISE_CID = FIENDSMITH_PARADISE_CID
FIENDSMITH_KYRIE_CID = "20816"
FIENDSMITH_AGNUMDAY_CID = "20521"
FIENDSMITH_SEQUENCE_CID = "20238"
FIENDSMITH_REXTREMENDE_CID = "20774"

OPP_TURN_EVENT = "OPP_TURN"
OPP_SPECIAL_SUMMON_EVENT = "OPP_SPECIAL_SUMMON"

# Verified against docs/CARD_DATA.md
# Fiendsmith Spell/Trap cards (for Engraver's search effect)
# 20240=Tract(Spell), 20241=Sanct(Spell), 20251=Paradise(Trap), 20816=Kyrie(Trap)
FIENDSMITH_ST_CIDS = {"20240", "20241", "20251", "20816"}

# Lacrima the Crimson Tears: "send 1 'Fiendsmith' card from Deck, except itself"
# Includes all monsters with "Fiendsmith" in name + all Fiendsmith S/T
LACRIMA_CT_SEND_TARGET_CIDS = {
    "20196",  # Engraver
    "20214",  # Fiendsmith's Lacrima (Fusion) - can't be in deck, but included for completeness
    "20215",  # Desirae (Fusion)
    "20225",  # Requiem (Link)
    "20238",  # Sequence (Link)
    "20521",  # Agnumday (Link)
    "20774",  # Rextremende (Fusion)
    "20240",  # Tract (Spell)
    "20241",  # Sanct (Spell)
    "20251",  # Paradise (Trap)
    "20816",  # Kyrie (Trap)
    # NOTE: Does NOT include 20490 (Lacrima CT itself) - card text says "except"
}

# All LIGHT Fiend monsters in the archetype (verified from CDB)
# Used for material validation and effect targeting
LIGHT_FIEND_MONSTER_CIDS = {
    "20196",  # Engraver (Main Deck, Level 6)
    "20214",  # Fiendsmith's Lacrima (Fusion)
    "20215",  # Desirae (Fusion)
    "20225",  # Requiem (Link-1)
    "20238",  # Sequence (Link-2)
    "20521",  # Agnumday (Link-3)
    "20774",  # Rextremende (Fusion)
    "20490",  # Lacrima the Crimson Tears (Main Deck, Level 4, "treated as Fiendsmith")
}

# Fiendsmith monster CIDs (by name, not "treated as")
FIENDSMITH_MONSTER_CIDS = {
    "20196",  # Engraver
    "20214",  # Fiendsmith's Lacrima (Fusion)
    "20215",  # Desirae (Fusion)
    "20225",  # Requiem (Link)
    "20238",  # Sequence (Link)
    "20521",  # Agnumday (Link)
    "20774",  # Rextremende (Fusion)
}

# Requiem effect: "SS 1 'Fiendsmith' monster from your hand or Deck"
# MUST be Main Deck monsters only (cannot summon from Extra Deck)
# Verified against docs/CARD_DATA.md
REQUIEM_QUICK_TARGET_CIDS = {
    FIENDSMITH_ENGRAVER_CID,         # 20196 - Main Deck Fiendsmith
    FIENDSMITH_LACRIMA_CRIMSON_CID,  # 20490 - Main Deck, "treated as Fiendsmith"
    # NOTE: FIENDSMITH_LACRIMA_CID (20214) is a FUSION monster - cannot be summoned from deck!
}
LACRIMA_GY_LINK_TARGET_CIDS = {
    FIENDSMITH_REQUIEM_CID,
    FIENDSMITH_AGNUMDAY_CID,
    FIENDSMITH_SEQUENCE_CID,
}
LINK_RATING_BY_CID = {
    FIENDSMITH_REQUIEM_CID: 1,
    FIENDSMITH_AGNUMDAY_CID: 3,
    FIENDSMITH_SEQUENCE_CID: 2,
}

REXTREMENDE_SEND_ALLOWLIST = {
    FIENDSMITH_ENGRAVER_CID,
    FIENDSMITH_DESIRAE_CID,
}
REXTREMENDE_RECOVER_ALLOWLIST = {
    FIENDSMITH_TRACT_CID,
    FIENDSMITH_SANCT_CID,
    FIENDSMITH_PARADISE_CID,
    FIENDSMITH_SEQUENCE_CID,
    FIENDSMITH_REQUIEM_CID,
    FIENDSMITH_AGNUMDAY_CID,
    FIENDSMITH_DESIRAE_CID,
}
PARADISE_SEND_ALLOWLIST = {
    FIENDSMITH_ENGRAVER_CID,
    FIENDSMITH_DESIRAE_CID,
    FIENDSMITH_LACRIMA_CID,
    FIENDSMITH_REQUIEM_CID,
    FIENDSMITH_SEQUENCE_CID,
    FIENDSMITH_REXTREMENDE_CID,
}
KYRIE_FUSION_MATERIAL_CIDS = {
    FIENDSMITH_DESIRAE_CID,
    FIENDSMITH_LACRIMA_CID,
}

# All Fiendsmith Fusion monsters (targets for Kyrie's GY effect)
# Kyrie: "Fusion Summon 1 'Fiendsmith' Fusion Monster from your Extra Deck"
FIENDSMITH_FUSION_CIDS = {
    FIENDSMITH_LACRIMA_CID,      # 20214 - Fiendsmith's Lacrima
    FIENDSMITH_DESIRAE_CID,      # 20215 - Fiendsmith's Desirae
    FIENDSMITH_REXTREMENDE_CID,  # 20774 - Fiendsmith's Rextremende
}
FIENDSMITH_EQUIP_CIDS = {
    FIENDSMITH_REQUIEM_CID,
    FIENDSMITH_SEQUENCE_CID,
    FIENDSMITH_AGNUMDAY_CID,
}


def is_fiendsmith_st(card_cid: str) -> bool:
    return card_cid in FIENDSMITH_ST_CIDS


def is_light_fiend_card(card: CardInstance) -> bool:
    if card.cid in LIGHT_FIEND_MONSTER_CIDS:
        return True
    attribute = str(card.metadata.get("attribute", "")).upper()
    race = str(card.metadata.get("race", "")).upper()
    return attribute == "LIGHT" and race == "FIEND"


def is_light_fiend_monster(card_cid: str) -> bool:
    return card_cid in LIGHT_FIEND_MONSTER_CIDS


def controls_only_light_fiends(state: GameState) -> bool:
    field_cards = [card for card in state.field.mz + state.field.emz if card]
    if not field_cards:
        return True
    return all(is_light_fiend_card(card) for card in field_cards)


def is_link_monster(card: CardInstance) -> bool:
    if card.cid in LACRIMA_GY_LINK_TARGET_CIDS:
        return True
    try:
        return int(card.metadata.get("link_rating", 0)) > 0
    except (TypeError, ValueError):
        return False


def total_equipped_link_rating(card: CardInstance) -> int:
    total = 0
    for equipped in card.equipped:
        rating = LINK_RATING_BY_CID.get(equipped.cid)
        if rating is None:
            try:
                rating = int(equipped.metadata.get("link_rating", 0))
            except (TypeError, ValueError):
                rating = 0
        total += rating
    return total


def make_fiendsmith_token() -> CardInstance:
    return CardInstance(
        cid="FIENDSMITH_TOKEN",
        name="Fiendsmith Token",
        metadata={
            "card_type": "monster",
            "subtype": "token",
            "attribute": "LIGHT",
            "race": "FIEND",
            "level": 1,
            "atk": 0,
            "def": 0,
        },
    )


class FiendsmithEngraverEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if not state.opt_used.get(f"{FIENDSMITH_ENGRAVER_CID}:e1"):
            for hand_index, card in enumerate(state.hand):
                if card.cid != FIENDSMITH_ENGRAVER_CID:
                    continue
                for deck_index, deck_card in enumerate(state.deck):
                    if not is_fiendsmith_st(deck_card.cid):
                        continue
                    actions.append(
                        EffectAction(
                            cid=FIENDSMITH_ENGRAVER_CID,
                            name=card.name,
                            effect_id="discard_search_fiendsmith_st",
                            params={"hand_index": hand_index, "deck_index": deck_index},
                            sort_key=(
                                FIENDSMITH_ENGRAVER_CID,
                                "discard_search_fiendsmith_st",
                                hand_index,
                                deck_index,
                            ),
                        )
                    )

        # e2: Target 1 Fiendsmith Equip + 1 monster on field; send both to GY
        if not state.opt_used.get(f"{FIENDSMITH_ENGRAVER_CID}:e2"):
            equip_entries: list[tuple[str, int, int, CardInstance]] = []
            for mz_idx, monster in enumerate(state.field.mz):
                if monster:
                    for eq_idx, eq_card in enumerate(monster.equipped):
                        if eq_card.cid in FIENDSMITH_EQUIP_CIDS:
                            equip_entries.append(("mz", mz_idx, eq_idx, eq_card))
            for emz_idx, monster in enumerate(state.field.emz):
                if monster:
                    for eq_idx, eq_card in enumerate(monster.equipped):
                        if eq_card.cid in FIENDSMITH_EQUIP_CIDS:
                            equip_entries.append(("emz", emz_idx, eq_idx, eq_card))

            monster_targets: list[tuple[str, int, CardInstance]] = []
            for mz_idx, monster in enumerate(state.field.mz):
                if monster:
                    monster_targets.append(("mz", mz_idx, monster))
            for emz_idx, monster in enumerate(state.field.emz):
                if monster:
                    monster_targets.append(("emz", emz_idx, monster))

            for eq_zone, eq_host_idx, eq_idx, eq_card in equip_entries:
                for mon_zone, mon_idx, mon_card in monster_targets:
                    actions.append(
                        EffectAction(
                            cid=FIENDSMITH_ENGRAVER_CID,
                            name=eq_card.name,
                            effect_id="send_equip_and_monster_to_gy",
                            params={
                                "equip_zone": eq_zone,
                                "equip_host_index": eq_host_idx,
                                "equip_index": eq_idx,
                                "monster_zone": mon_zone,
                                "monster_index": mon_idx,
                            },
                            sort_key=(
                                FIENDSMITH_ENGRAVER_CID,
                                "send_equip_and_monster_to_gy",
                                eq_zone,
                                eq_host_idx,
                                eq_idx,
                                mon_zone,
                                mon_idx,
                            ),
                        )
                    )

        if not state.opt_used.get(f"{FIENDSMITH_ENGRAVER_CID}:e3"):
            open_mz = state.open_mz_indices()
            if open_mz:
                for gy_index, card in enumerate(state.gy):
                    if card.cid != FIENDSMITH_ENGRAVER_CID:
                        continue
                    for target_index, target in enumerate(state.gy):
                        if target_index == gy_index:
                            continue
                        if not is_light_fiend_monster(target.cid):
                            continue
                        for mz_index in open_mz:
                            actions.append(
                                EffectAction(
                                    cid=FIENDSMITH_ENGRAVER_CID,
                                    name=card.name,
                                    effect_id="gy_shuffle_light_fiend_then_ss_self",
                                    params={
                                        "gy_index": gy_index,
                                        "target_gy_index": target_index,
                                        "mz_index": mz_index,
                                    },
                                    sort_key=(
                                        FIENDSMITH_ENGRAVER_CID,
                                        "gy_shuffle_light_fiend_then_ss_self",
                                        gy_index,
                                        target_index,
                                        mz_index,
                                    ),
                                )
                            )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "gy_shuffle_light_fiend_then_ss_self":
            return self._apply_gy_revive(state, action)
        if action.effect_id == "send_equip_and_monster_to_gy":
            return self._apply_send_equip_and_monster(state, action)
        if action.effect_id != "discard_search_fiendsmith_st":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{FIENDSMITH_ENGRAVER_CID}:e1"):
            raise IllegalActionError("Fiendsmith Engraver effect already used.")

        hand_index = action.params.get("hand_index")
        deck_index = action.params.get("deck_index")
        if hand_index is None or deck_index is None:
            raise SimModelError("Missing params for Fiendsmith Engraver effect.")

        if hand_index < 0 or hand_index >= len(state.hand):
            raise IllegalActionError("Hand index out of range for Fiendsmith Engraver.")
        if deck_index < 0 or deck_index >= len(state.deck):
            raise IllegalActionError("Deck index out of range for Fiendsmith Engraver.")

        if state.hand[hand_index].cid != FIENDSMITH_ENGRAVER_CID:
            raise SimModelError("Action does not match Fiendsmith Engraver card.")
        if not is_fiendsmith_st(state.deck[deck_index].cid):
            raise IllegalActionError("Selected deck card is not a Fiendsmith Spell/Trap.")

        new_state = state.clone()
        engraver = new_state.hand.pop(hand_index)
        new_state.gy.append(engraver)
        selected = new_state.deck.pop(deck_index)
        new_state.hand.append(selected)
        new_state.opt_used[f"{FIENDSMITH_ENGRAVER_CID}:e1"] = True
        return new_state

    def _apply_gy_revive(self, state: GameState, action: EffectAction) -> GameState:
        if state.opt_used.get(f"{FIENDSMITH_ENGRAVER_CID}:e3"):
            raise IllegalActionError("Fiendsmith Engraver GY effect already used.")

        gy_index = action.params.get("gy_index")
        target_index = action.params.get("target_gy_index")
        mz_index = action.params.get("mz_index")
        if gy_index is None or target_index is None or mz_index is None:
            raise SimModelError("Missing params for Fiendsmith Engraver GY effect.")

        if gy_index < 0 or gy_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for Fiendsmith Engraver.")
        if target_index < 0 or target_index >= len(state.gy):
            raise IllegalActionError("Target GY index out of range for Fiendsmith Engraver.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Fiendsmith Engraver.")
        if gy_index == target_index:
            raise IllegalActionError("Target GY card must be different from Engraver.")

        if state.gy[gy_index].cid != FIENDSMITH_ENGRAVER_CID:
            raise SimModelError("Selected GY card is not Fiendsmith Engraver.")
        if not is_light_fiend_monster(state.gy[target_index].cid):
            raise IllegalActionError("Target GY card is not a LIGHT Fiend monster.")

        new_state = state.clone()
        indices = sorted([gy_index, target_index], reverse=True)
        removed = []
        for index in indices:
            removed.append(new_state.gy.pop(index))
        removed.reverse()
        engraver = removed[0] if gy_index < target_index else removed[1]
        target = removed[1] if gy_index < target_index else removed[0]
        new_state.deck.append(target)
        new_state.field.mz[mz_index] = engraver
        new_state.opt_used[f"{FIENDSMITH_ENGRAVER_CID}:e3"] = True
        return new_state

    def _apply_send_equip_and_monster(self, state: GameState, action: EffectAction) -> GameState:
        if state.opt_used.get(f"{FIENDSMITH_ENGRAVER_CID}:e2"):
            raise IllegalActionError("Fiendsmith Engraver e2 effect already used.")

        equip_zone = action.params.get("equip_zone")
        equip_host_index = action.params.get("equip_host_index")
        equip_index = action.params.get("equip_index")
        monster_zone = action.params.get("monster_zone")
        monster_index = action.params.get("monster_index")

        if None in (equip_zone, equip_host_index, equip_index, monster_zone, monster_index):
            raise SimModelError("Missing params for Fiendsmith Engraver e2 effect.")

        # Get the host monster with the equipped card
        if equip_zone == "mz":
            if equip_host_index < 0 or equip_host_index >= len(state.field.mz):
                raise IllegalActionError("Equip host index out of range.")
            host = state.field.mz[equip_host_index]
        elif equip_zone == "emz":
            if equip_host_index < 0 or equip_host_index >= len(state.field.emz):
                raise IllegalActionError("Equip host index out of range.")
            host = state.field.emz[equip_host_index]
        else:
            raise SimModelError("Invalid equip zone for Fiendsmith Engraver e2.")

        if host is None:
            raise IllegalActionError("No monster at equip host location.")
        if equip_index < 0 or equip_index >= len(host.equipped):
            raise IllegalActionError("Equip index out of range.")
        if host.equipped[equip_index].cid not in FIENDSMITH_EQUIP_CIDS:
            raise IllegalActionError("Selected equip is not a Fiendsmith Equip Card.")

        # Get the target monster
        if monster_zone == "mz":
            if monster_index < 0 or monster_index >= len(state.field.mz):
                raise IllegalActionError("Monster index out of range.")
            target = state.field.mz[monster_index]
        elif monster_zone == "emz":
            if monster_index < 0 or monster_index >= len(state.field.emz):
                raise IllegalActionError("Monster index out of range.")
            target = state.field.emz[monster_index]
        else:
            raise SimModelError("Invalid monster zone for Fiendsmith Engraver e2.")

        if target is None:
            raise IllegalActionError("No monster at target location.")

        new_state = state.clone()

        # Get the equip card from the host in new_state
        if equip_zone == "mz":
            new_host = new_state.field.mz[equip_host_index]
        else:
            new_host = new_state.field.emz[equip_host_index]

        equip_card = new_host.equipped.pop(equip_index)
        new_state.gy.append(equip_card)

        # Remove the target monster and send to GY
        if monster_zone == "mz":
            target_card = new_state.field.mz[monster_index]
            new_state.field.mz[monster_index] = None
        else:
            target_card = new_state.field.emz[monster_index]
            new_state.field.emz[monster_index] = None

        # Send any equipped cards on the target to GY first
        for eq in target_card.equipped:
            new_state.gy.append(eq)
        target_card.equipped = []
        new_state.gy.append(target_card)

        new_state.opt_used[f"{FIENDSMITH_ENGRAVER_CID}:e2"] = True
        return new_state


class FiendsmithTractEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if not state.opt_used.get(f"{FIENDSMITH_TRACT_CID}:e1"):
            if len(state.hand) > 1:
                for hand_index, card in enumerate(state.hand):
                    if card.cid != FIENDSMITH_TRACT_CID:
                        continue
                    for deck_index, deck_card in enumerate(state.deck):
                        if not is_light_fiend_monster(deck_card.cid):
                            continue
                        for discard_index in range(len(state.hand)):
                            if discard_index == hand_index:
                                continue
                            actions.append(
                                EffectAction(
                                    cid=FIENDSMITH_TRACT_CID,
                                    name=card.name,
                                    effect_id="search_light_fiend_then_discard",
                                    params={
                                        "hand_index": hand_index,
                                        "deck_index": deck_index,
                                        "discard_hand_index": discard_index,
                                    },
                                    sort_key=(
                                        FIENDSMITH_TRACT_CID,
                                        "search_light_fiend_then_discard",
                                        hand_index,
                                        deck_index,
                                        discard_index,
                                    ),
                                )
                            )

        if not state.opt_used.get(f"{FIENDSMITH_TRACT_CID}:e2"):
            open_mz = state.open_mz_indices()
            if open_mz:
                tract_indices = [idx for idx, card in enumerate(state.gy) if card.cid == FIENDSMITH_TRACT_CID]
                desirae_indices = [
                    idx for idx, card in enumerate(state.extra) if card.cid == FIENDSMITH_DESIRAE_CID
                ]
                if tract_indices and desirae_indices:
                    candidates: list[tuple[str, int, CardInstance]] = []
                    for hand_index, card in enumerate(state.hand):
                        candidates.append(("hand", hand_index, card))
                    for mz_index, card in enumerate(state.field.mz):
                        if card:
                            candidates.append(("mz", mz_index, card))
                    for emz_index, card in enumerate(state.field.emz):
                        if card:
                            candidates.append(("emz", emz_index, card))

                    engravers = [
                        entry for entry in candidates if entry[2].cid == FIENDSMITH_ENGRAVER_CID
                    ]
                    light_fiends = [entry for entry in candidates if is_light_fiend_card(entry[2])]

                    for gy_index in tract_indices:
                        tract_card = state.gy[gy_index]
                        for extra_index in desirae_indices:
                            for engraver in engravers:
                                other_lights = [
                                    entry
                                    for entry in light_fiends
                                    if (entry[0], entry[1]) != (engraver[0], engraver[1])
                                ]
                                for first_idx in range(len(other_lights)):
                                    for second_idx in range(first_idx + 1, len(other_lights)):
                                        materials = [
                                            {
                                                "source": engraver[0],
                                                "index": engraver[1],
                                            },
                                            {
                                                "source": other_lights[first_idx][0],
                                                "index": other_lights[first_idx][1],
                                            },
                                            {
                                                "source": other_lights[second_idx][0],
                                                "index": other_lights[second_idx][1],
                                            },
                                        ]
                                        material_key = tuple(
                                            (entry["source"], entry["index"]) for entry in materials
                                        )
                                        actions.append(
                                            EffectAction(
                                                cid=FIENDSMITH_TRACT_CID,
                                                name=tract_card.name,
                                                effect_id="gy_banish_fuse_fiendsmith",
                                                params={
                                                    "gy_index": gy_index,
                                                    "extra_index": extra_index,
                                                    "mz_index": open_mz[0],
                                                    "materials": materials,
                                                },
                                                sort_key=(
                                                    FIENDSMITH_TRACT_CID,
                                                    "gy_banish_fuse_fiendsmith",
                                                    gy_index,
                                                    extra_index,
                                                    material_key,
                                                ),
                                            )
                                        )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "search_light_fiend_then_discard":
            if state.opt_used.get(f"{FIENDSMITH_TRACT_CID}:e1"):
                raise IllegalActionError("Fiendsmith's Tract effect already used.")

            hand_index = action.params.get("hand_index")
            deck_index = action.params.get("deck_index")
            discard_hand_index = action.params.get("discard_hand_index")
            if hand_index is None or deck_index is None or discard_hand_index is None:
                raise SimModelError("Missing params for Fiendsmith's Tract effect.")

            if hand_index < 0 or hand_index >= len(state.hand):
                raise IllegalActionError("Hand index out of range for Fiendsmith's Tract.")
            if deck_index < 0 or deck_index >= len(state.deck):
                raise IllegalActionError("Deck index out of range for Fiendsmith's Tract.")
            if discard_hand_index < 0 or discard_hand_index >= len(state.hand):
                raise IllegalActionError("Discard index out of range for Fiendsmith's Tract.")
            if discard_hand_index == hand_index:
                raise IllegalActionError("Discard choice cannot be the Tract itself.")

            if state.hand[hand_index].cid != FIENDSMITH_TRACT_CID:
                raise SimModelError("Action does not match Fiendsmith's Tract card.")
            if not is_light_fiend_monster(state.deck[deck_index].cid):
                raise IllegalActionError("Selected deck card is not a LIGHT Fiend monster.")

            new_state = state.clone()
            tract_card = new_state.hand.pop(hand_index)
            new_state.gy.append(tract_card)

            selected = new_state.deck.pop(deck_index)
            new_state.hand.append(selected)

            adjusted_discard_index = discard_hand_index
            if discard_hand_index > hand_index:
                adjusted_discard_index -= 1
            if adjusted_discard_index < 0 or adjusted_discard_index >= len(new_state.hand):
                raise IllegalActionError("Discard index invalid after Tract removal.")

            discarded = new_state.hand.pop(adjusted_discard_index)
            new_state.gy.append(discarded)
            new_state.last_moved_to_gy = [discarded.cid]

            new_state.opt_used[f"{FIENDSMITH_TRACT_CID}:e1"] = True
            return new_state

        if action.effect_id == "gy_banish_fuse_fiendsmith":
            return self._apply_gy_fusion(state, action)

        raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")

    def _apply_gy_fusion(self, state: GameState, action: EffectAction) -> GameState:
        if state.opt_used.get(f"{FIENDSMITH_TRACT_CID}:e2"):
            raise IllegalActionError("Fiendsmith's Tract GY effect already used.")

        gy_index = action.params.get("gy_index")
        extra_index = action.params.get("extra_index")
        mz_index = action.params.get("mz_index")
        materials = action.params.get("materials")
        if gy_index is None or extra_index is None or mz_index is None or materials is None:
            raise SimModelError("Missing params for Fiendsmith's Tract GY effect.")
        if not isinstance(materials, list) or len(materials) != 3:
            raise SimModelError("Invalid materials for Fiendsmith's Tract GY effect.")

        if gy_index < 0 or gy_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for Fiendsmith's Tract.")
        if extra_index < 0 or extra_index >= len(state.extra):
            raise IllegalActionError("Extra index out of range for Fiendsmith's Tract.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Fiendsmith's Tract.")

        if state.gy[gy_index].cid != FIENDSMITH_TRACT_CID:
            raise SimModelError("Selected GY card is not Fiendsmith's Tract.")
        if state.extra[extra_index].cid != FIENDSMITH_DESIRAE_CID:
            raise IllegalActionError("Selected Extra Deck target is not Fiendsmith's Desirae.")

        seen = set()
        material_cards: list[CardInstance] = []
        for entry in materials:
            source = entry.get("source")
            index = entry.get("index")
            if source is None or index is None:
                raise SimModelError("Invalid material entry for Fiendsmith's Tract.")
            key = (source, index)
            if key in seen:
                raise IllegalActionError("Duplicate material selection for Fiendsmith's Tract.")
            seen.add(key)

            if source == "hand":
                if index < 0 or index >= len(state.hand):
                    raise IllegalActionError("Hand index out of range for Fiendsmith's Tract.")
                card = state.hand[index]
            elif source == "mz":
                if index < 0 or index >= len(state.field.mz):
                    raise IllegalActionError("Field index out of range for Fiendsmith's Tract.")
                card = state.field.mz[index]
            elif source == "emz":
                if index < 0 or index >= len(state.field.emz):
                    raise IllegalActionError("Field index out of range for Fiendsmith's Tract.")
                card = state.field.emz[index]
            else:
                raise SimModelError("Invalid material source for Fiendsmith's Tract.")
            if card is None:
                raise IllegalActionError("Material missing from field for Fiendsmith's Tract.")
            material_cards.append(card)

        if not any(card.cid == FIENDSMITH_ENGRAVER_CID for card in material_cards):
            raise IllegalActionError("Fiendsmith's Tract requires Fiendsmith Engraver.")
        if not all(is_light_fiend_card(card) for card in material_cards):
            raise IllegalActionError("Fiendsmith's Tract requires LIGHT Fiend materials.")

        new_state = state.clone()
        tract_card = new_state.gy.pop(gy_index)
        new_state.banished.append(tract_card)

        removed_cards: dict[tuple[str, int], CardInstance] = {}
        for entry in materials:
            source = entry["source"]
            index = entry["index"]
            if source == "hand":
                card = new_state.hand[index]
            elif source == "mz":
                card = new_state.field.mz[index]
            else:
                card = new_state.field.emz[index]
            if card is None:
                raise IllegalActionError("Material missing during Fiendsmith's Tract resolution.")
            removed_cards[(source, index)] = card

        hand_indices = sorted(
            [index for (source, index) in removed_cards if source == "hand"],
            reverse=True,
        )
        for index in hand_indices:
            new_state.hand.pop(index)

        for (source, index), _card in removed_cards.items():
            if source == "mz":
                new_state.field.mz[index] = None
            elif source == "emz":
                new_state.field.emz[index] = None

        for entry in materials:
            card = removed_cards[(entry["source"], entry["index"])]
            new_state.gy.append(card)

        summoned = new_state.extra.pop(extra_index)
        summoned.properly_summoned = True
        summoned.metadata["from_extra"] = True
        new_state.field.mz[mz_index] = summoned
        new_state.opt_used[f"{FIENDSMITH_TRACT_CID}:e2"] = True
        return new_state


class FiendsmithLacrimaCrimsonEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []

        if not state.opt_used.get(f"{FIENDSMITH_LACRIMA_CRIMSON_CID}:e1"):
            field_entries = []
            for index, card in enumerate(state.field.mz):
                if card and card.cid == FIENDSMITH_LACRIMA_CRIMSON_CID:
                    field_entries.append(("mz", index, card))
            for index, card in enumerate(state.field.emz):
                if card and card.cid == FIENDSMITH_LACRIMA_CRIMSON_CID:
                    field_entries.append(("emz", index, card))

            for zone, field_index, card in field_entries:
                for deck_index, deck_card in enumerate(state.deck):
                    # Can send ANY "Fiendsmith" card except itself
                    if deck_card.cid not in LACRIMA_CT_SEND_TARGET_CIDS:
                        continue
                    actions.append(
                        EffectAction(
                            cid=FIENDSMITH_LACRIMA_CRIMSON_CID,
                            name=card.name,
                            effect_id="send_fiendsmith_from_deck",
                            params={
                                "zone": zone,
                                "field_index": field_index,
                                "deck_index": deck_index,
                            },
                            sort_key=(
                                FIENDSMITH_LACRIMA_CRIMSON_CID,
                                "send_fiendsmith_from_deck",
                                zone,
                                field_index,
                                deck_index,
                            ),
                        )
                    )

        if (
            not state.opt_used.get(f"{FIENDSMITH_LACRIMA_CRIMSON_CID}:e2")
            and OPP_TURN_EVENT in state.events
        ):
            open_emz = state.open_emz_indices()
            if open_emz:
                for gy_index, card in enumerate(state.gy):
                    if card.cid != FIENDSMITH_LACRIMA_CRIMSON_CID:
                        continue
                    for target_index, target in enumerate(state.gy):
                        if target_index == gy_index:
                            continue
                        if target.cid not in LACRIMA_GY_LINK_TARGET_CIDS:
                            continue
                        if not can_revive_from_gy(target):
                            continue
                        for emz_index in open_emz:
                            actions.append(
                                EffectAction(
                                    cid=FIENDSMITH_LACRIMA_CRIMSON_CID,
                                    name=card.name,
                                    effect_id="gy_shuffle_ss_fiendsmith_link",
                                    params={
                                        "gy_index": gy_index,
                                        "target_gy_index": target_index,
                                        "emz_index": emz_index,
                                    },
                                    sort_key=(
                                        FIENDSMITH_LACRIMA_CRIMSON_CID,
                                        "gy_shuffle_ss_fiendsmith_link",
                                        gy_index,
                                        target_index,
                                        emz_index,
                                    ),
                                )
                            )

        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "send_fiendsmith_from_deck":
            if state.opt_used.get(f"{FIENDSMITH_LACRIMA_CRIMSON_CID}:e1"):
                raise IllegalActionError("Lacrima CT effect already used.")

            zone = action.params.get("zone")
            field_index = action.params.get("field_index")
            deck_index = action.params.get("deck_index")
            if zone is None or field_index is None or deck_index is None:
                raise SimModelError("Missing params for Lacrima CT effect.")
            if zone not in {"mz", "emz"}:
                raise SimModelError("Invalid zone for Lacrima CT effect.")
            if not isinstance(field_index, int) or not isinstance(deck_index, int):
                raise SimModelError("Invalid index types for Lacrima CT effect.")
            if deck_index < 0 or deck_index >= len(state.deck):
                raise IllegalActionError("Deck index out of range for Lacrima CT.")

            if zone == "mz":
                if field_index < 0 or field_index >= len(state.field.mz):
                    raise IllegalActionError("Field index out of range for Lacrima CT.")
                lacrima = state.field.mz[field_index]
            else:
                if field_index < 0 or field_index >= len(state.field.emz):
                    raise IllegalActionError("Field index out of range for Lacrima CT.")
                lacrima = state.field.emz[field_index]
            if not lacrima or lacrima.cid != FIENDSMITH_LACRIMA_CRIMSON_CID:
                raise SimModelError("Selected field card is not Lacrima CT.")

            if state.deck[deck_index].cid not in LACRIMA_CT_SEND_TARGET_CIDS:
                raise IllegalActionError("Selected deck card is not a Fiendsmith card.")

            new_state = state.clone()
            sent = new_state.deck.pop(deck_index)
            new_state.gy.append(sent)
            new_state.last_moved_to_gy = [sent.cid]
            new_state.opt_used[f"{FIENDSMITH_LACRIMA_CRIMSON_CID}:e1"] = True
            return new_state

        if action.effect_id == "gy_shuffle_ss_fiendsmith_link":
            if state.opt_used.get(f"{FIENDSMITH_LACRIMA_CRIMSON_CID}:e2"):
                raise IllegalActionError("Fiendsmith's Lacrima GY effect already used.")
            if OPP_TURN_EVENT not in state.events:
                raise IllegalActionError("Fiendsmith's Lacrima GY effect requires opponent turn.")

            gy_index = action.params.get("gy_index")
            target_index = action.params.get("target_gy_index")
            emz_index = action.params.get("emz_index")
            if gy_index is None or target_index is None or emz_index is None:
                raise SimModelError("Missing params for Fiendsmith's Lacrima GY effect.")
            if not isinstance(gy_index, int) or not isinstance(target_index, int) or not isinstance(emz_index, int):
                raise SimModelError("Invalid index types for Fiendsmith's Lacrima GY effect.")
            if gy_index < 0 or gy_index >= len(state.gy):
                raise IllegalActionError("GY index out of range for Fiendsmith's Lacrima.")
            if target_index < 0 or target_index >= len(state.gy):
                raise IllegalActionError("Target GY index out of range for Fiendsmith's Lacrima.")
            if emz_index not in state.open_emz_indices():
                raise IllegalActionError("No open EMZ for Fiendsmith's Lacrima.")
            if gy_index == target_index:
                raise IllegalActionError("Target must differ from Fiendsmith's Lacrima.")

            if state.gy[gy_index].cid != FIENDSMITH_LACRIMA_CRIMSON_CID:
                raise SimModelError("Selected GY card is not Fiendsmith's Lacrima.")
            if state.gy[target_index].cid not in LACRIMA_GY_LINK_TARGET_CIDS:
                raise IllegalActionError("Selected target is not a Fiendsmith Link monster.")

            lacrima_card = state.gy[gy_index]
            target_card = state.gy[target_index]
            validate_revive_from_gy(target_card)

            new_state = state.clone()
            for index in sorted([gy_index, target_index], reverse=True):
                new_state.gy.pop(index)

            new_state.deck.append(lacrima_card)
            new_state.field.emz[emz_index] = target_card
            new_state.opt_used[f"{FIENDSMITH_LACRIMA_CRIMSON_CID}:e2"] = True
            return new_state

        raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")


class FiendsmithAgnumdayEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        if state.opt_used.get(f"{FIENDSMITH_AGNUMDAY_CID}:e1"):
            return []

        open_mz = state.open_mz_indices()
        if not open_mz:
            return []

        field_entries = []
        for index, card in enumerate(state.field.mz):
            if card and card.cid == FIENDSMITH_AGNUMDAY_CID:
                field_entries.append(("mz", index, card))
        for index, card in enumerate(state.field.emz):
            if card and card.cid == FIENDSMITH_AGNUMDAY_CID:
                field_entries.append(("emz", index, card))
        if not field_entries:
            return []

        targets = []
        for gy_index, card in enumerate(state.gy):
            if not is_light_fiend_card(card):
                continue
            if is_link_monster(card):
                continue
            if not can_revive_from_gy(card):
                continue
            targets.append((gy_index, card))

        actions: list[EffectAction] = []
        for zone, field_index, card in field_entries:
            for gy_index, target in targets:
                for mz_index in open_mz:
                    actions.append(
                        EffectAction(
                            cid=FIENDSMITH_AGNUMDAY_CID,
                            name=card.name,
                            effect_id="agnumday_revive_equip",
                            params={
                                "zone": zone,
                                "field_index": field_index,
                                "gy_index": gy_index,
                                "mz_index": mz_index,
                            },
                            sort_key=(
                                FIENDSMITH_AGNUMDAY_CID,
                                "agnumday_revive_equip",
                                zone,
                                field_index,
                                gy_index,
                                mz_index,
                            ),
                        )
                    )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id != "agnumday_revive_equip":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{FIENDSMITH_AGNUMDAY_CID}:e1"):
            raise IllegalActionError("Fiendsmith's Agnumday effect already used.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        gy_index = action.params.get("gy_index")
        mz_index = action.params.get("mz_index")
        if None in (zone, field_index, gy_index, mz_index):
            raise SimModelError("Missing params for Fiendsmith's Agnumday effect.")
        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for Fiendsmith's Agnumday effect.")
        if not isinstance(field_index, int) or not isinstance(gy_index, int) or not isinstance(mz_index, int):
            raise SimModelError("Invalid index types for Fiendsmith's Agnumday effect.")
        if gy_index < 0 or gy_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for Fiendsmith's Agnumday.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Fiendsmith's Agnumday.")

        if zone == "mz":
            if field_index < 0 or field_index >= len(state.field.mz):
                raise IllegalActionError("Field index out of range for Agnumday.")
            agnumday = state.field.mz[field_index]
        else:
            if field_index < 0 or field_index >= len(state.field.emz):
                raise IllegalActionError("Field index out of range for Agnumday.")
            agnumday = state.field.emz[field_index]
        if not agnumday or agnumday.cid != FIENDSMITH_AGNUMDAY_CID:
            raise SimModelError("Selected field card is not Fiendsmith's Agnumday.")

        target = state.gy[gy_index]
        if not is_light_fiend_card(target):
            raise IllegalActionError("Target is not a LIGHT Fiend monster.")
        if is_link_monster(target):
            raise IllegalActionError("Target is a Link monster.")
        validate_revive_from_gy(target)

        new_state = state.clone()
        revived = new_state.gy.pop(gy_index)
        new_state.field.mz[mz_index] = revived

        if zone == "mz":
            agnumday_card = new_state.field.mz[field_index]
            new_state.field.mz[field_index] = None
        else:
            agnumday_card = new_state.field.emz[field_index]
            new_state.field.emz[field_index] = None
        if agnumday_card is None:
            raise IllegalActionError("Fiendsmith's Agnumday missing for equip.")
        if "link_rating" not in agnumday_card.metadata:
            agnumday_card.metadata["link_rating"] = LINK_RATING_BY_CID.get(agnumday_card.cid, 3)

        new_state.equip_card(agnumday_card, new_state.field.mz[mz_index])
        new_state.opt_used[f"{FIENDSMITH_AGNUMDAY_CID}:e1"] = True
        return new_state


class FiendsmithSequenceEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        if OPP_TURN_EVENT in state.events:
            return []

        actions: list[EffectAction] = []
        sequence_entries = []
        for index, card in enumerate(state.field.mz):
            if card and card.cid == FIENDSMITH_SEQUENCE_CID:
                sequence_entries.append(("mz", index, card))
        for index, card in enumerate(state.field.emz):
            if card and card.cid == FIENDSMITH_SEQUENCE_CID:
                sequence_entries.append(("emz", index, card))

        if not state.opt_used.get(f"{FIENDSMITH_SEQUENCE_CID}:e1") and "Main Phase" in state.phase:
            open_mz = state.open_mz_indices()
            if open_mz and sequence_entries:
                engraver_indices = [
                    idx for idx, card in enumerate(state.gy) if card.cid == FIENDSMITH_ENGRAVER_CID
                ]
                light_indices = [
                    idx for idx, card in enumerate(state.gy) if is_light_fiend_card(card)
                ]
                desirae_indices = [
                    idx for idx, card in enumerate(state.extra) if card.cid == FIENDSMITH_DESIRAE_CID
                ]
                for seq_zone, seq_index, seq_card in sequence_entries:
                    for extra_index in desirae_indices:
                        for mz_index in open_mz:
                            for engraver_index in engraver_indices:
                                other_indices = [
                                    idx for idx in light_indices if idx != engraver_index
                                ]
                                for first_pos in range(len(other_indices)):
                                    for second_pos in range(first_pos + 1, len(other_indices)):
                                        gy_indices = [
                                            engraver_index,
                                            other_indices[first_pos],
                                            other_indices[second_pos],
                                        ]
                                        actions.append(
                                            EffectAction(
                                                cid=FIENDSMITH_SEQUENCE_CID,
                                                name=seq_card.name,
                                                effect_id="sequence_shuffle_fuse_fiend",
                                                params={
                                                    "seq_zone": seq_zone,
                                                    "seq_index": seq_index,
                                                    "extra_index": extra_index,
                                                    "mz_index": mz_index,
                                                    "gy_indices": gy_indices,
                                                },
                                                sort_key=(
                                                    FIENDSMITH_SEQUENCE_CID,
                                                    "sequence_shuffle_fuse_fiend",
                                                    seq_zone,
                                                    seq_index,
                                                    extra_index,
                                                    mz_index,
                                                    tuple(gy_indices),
                                                ),
                                            )
                                        )

                rext_indices = [
                    idx
                    for idx, card in enumerate(state.extra)
                    if card.cid == FIENDSMITH_REXTREMENDE_CID
                ]
                desirae_gy_indices = [
                    idx for idx, card in enumerate(state.gy) if card.cid == FIENDSMITH_DESIRAE_CID
                ]
                extra_gy_indices = [
                    idx
                    for idx, card in enumerate(state.gy)
                    if card.cid != FIENDSMITH_DESIRAE_CID and is_extra_deck_monster(card)
                ]
                if rext_indices and desirae_gy_indices and extra_gy_indices:
                    for seq_zone, seq_index, seq_card in sequence_entries:
                        for extra_index in rext_indices:
                            for mz_index in open_mz:
                                for desirae_index in desirae_gy_indices:
                                    for other_index in extra_gy_indices:
                                        gy_indices = [desirae_index, other_index]
                                        actions.append(
                                            EffectAction(
                                                cid=FIENDSMITH_SEQUENCE_CID,
                                                name=seq_card.name,
                                                effect_id="sequence_shuffle_fuse_rextremende",
                                                params={
                                                    "seq_zone": seq_zone,
                                                    "seq_index": seq_index,
                                                    "extra_index": extra_index,
                                                    "mz_index": mz_index,
                                                    "gy_indices": gy_indices,
                                                },
                                                sort_key=(
                                                    FIENDSMITH_SEQUENCE_CID,
                                                    "sequence_shuffle_fuse_rextremende",
                                                    seq_zone,
                                                    seq_index,
                                                    extra_index,
                                                    mz_index,
                                                    tuple(gy_indices),
                                                ),
                                            )
                                        )

        if not state.opt_used.get(f"{FIENDSMITH_SEQUENCE_CID}:e2"):
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
                for zone, seq_index, seq_card in sequence_entries:
                    for mz_index, target in targets:
                        actions.append(
                            EffectAction(
                                cid=FIENDSMITH_SEQUENCE_CID,
                                name=seq_card.name,
                                effect_id="equip_sequence_to_fiend",
                                params={
                                    "source": zone,
                                    "source_index": seq_index,
                                    "target_mz_index": mz_index,
                                },
                                sort_key=(
                                    FIENDSMITH_SEQUENCE_CID,
                                    "equip_sequence_to_fiend",
                                    zone,
                                    seq_index,
                                    mz_index,
                                ),
                            )
                        )
                for gy_index, card in enumerate(state.gy):
                    if card.cid != FIENDSMITH_SEQUENCE_CID:
                        continue
                    for mz_index, target in targets:
                        actions.append(
                            EffectAction(
                                cid=FIENDSMITH_SEQUENCE_CID,
                                name=card.name,
                                effect_id="equip_sequence_to_fiend",
                                params={
                                    "source": "gy",
                                    "source_index": gy_index,
                                    "target_mz_index": mz_index,
                                },
                                sort_key=(
                                    FIENDSMITH_SEQUENCE_CID,
                                    "equip_sequence_to_fiend",
                                    "gy",
                                    gy_index,
                                    mz_index,
                                ),
                            )
                        )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "sequence_shuffle_fuse_fiend":
            if OPP_TURN_EVENT in state.events:
                raise IllegalActionError("Fiendsmith's Sequence cannot be used on opponent turn.")
            if state.opt_used.get(f"{FIENDSMITH_SEQUENCE_CID}:e1"):
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
            if not isinstance(gy_indices, list) or len(gy_indices) != 3:
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
            if not seq_card or seq_card.cid != FIENDSMITH_SEQUENCE_CID:
                raise SimModelError("Selected field card is not Fiendsmith's Sequence.")

            if state.extra[extra_index].cid != FIENDSMITH_DESIRAE_CID:
                raise IllegalActionError("Selected Extra Deck card is not Fiendsmith's Desirae.")

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
            if not any(card.cid == FIENDSMITH_ENGRAVER_CID for card in materials):
                raise IllegalActionError("Fiendsmith's Sequence requires Fiendsmith Engraver.")
            if not all(is_light_fiend_card(card) for card in materials):
                raise IllegalActionError("Fiendsmith's Sequence requires LIGHT Fiend materials.")

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

            new_state.opt_used[f"{FIENDSMITH_SEQUENCE_CID}:e1"] = True
            return new_state

        if action.effect_id == "sequence_shuffle_fuse_rextremende":
            if OPP_TURN_EVENT in state.events:
                raise IllegalActionError("Fiendsmith's Sequence cannot be used on opponent turn.")
            if state.opt_used.get(f"{FIENDSMITH_SEQUENCE_CID}:e1"):
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
            if not isinstance(gy_indices, list) or len(gy_indices) != 2:
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
            if not seq_card or seq_card.cid != FIENDSMITH_SEQUENCE_CID:
                raise SimModelError("Selected field card is not Fiendsmith's Sequence.")

            if state.extra[extra_index].cid != FIENDSMITH_REXTREMENDE_CID:
                raise IllegalActionError("Selected Extra Deck card is not Fiendsmith's Rextremende.")

            if len(set(gy_indices)) != 2:
                raise IllegalActionError("Duplicate GY index for Fiendsmith's Sequence.")
            for idx in gy_indices:
                if not isinstance(idx, int):
                    raise SimModelError("Invalid GY index type for Fiendsmith's Sequence.")
                if idx < 0 or idx >= len(state.gy):
                    raise IllegalActionError("GY index out of range for Fiendsmith's Sequence.")

            materials = [state.gy[idx] for idx in gy_indices]
            if not any(card.cid == FIENDSMITH_DESIRAE_CID for card in materials):
                raise IllegalActionError("Fiendsmith's Sequence requires Fiendsmith's Desirae.")
            other = next(card for card in materials if card.cid != FIENDSMITH_DESIRAE_CID)
            if not is_extra_deck_monster(other):
                raise IllegalActionError("Fiendsmith's Sequence requires an extra deck monster.")

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

            new_state.opt_used[f"{FIENDSMITH_SEQUENCE_CID}:e1"] = True
            return new_state

        if action.effect_id == "equip_sequence_to_fiend":
            if OPP_TURN_EVENT in state.events:
                raise IllegalActionError("Fiendsmith's Sequence cannot be used on opponent turn.")
            if state.opt_used.get(f"{FIENDSMITH_SEQUENCE_CID}:e2"):
                raise IllegalActionError("Fiendsmith's Sequence equip effect already used.")

            source = action.params.get("source")
            source_index = action.params.get("source_index")
            target_index = action.params.get("target_mz_index")
            if None in (source, source_index, target_index):
                raise SimModelError("Missing params for Fiendsmith's Sequence equip effect.")
            if source not in {"mz", "emz", "gy"}:
                raise SimModelError("Invalid source for Fiendsmith's Sequence equip effect.")
            if not isinstance(source_index, int) or not isinstance(target_index, int):
                raise SimModelError("Invalid index types for Fiendsmith's Sequence equip effect.")
            if target_index < 0 or target_index >= len(state.field.mz):
                raise IllegalActionError("Target index out of range for Fiendsmith's Sequence.")

            target = state.field.mz[target_index]
            if not target or not is_light_fiend_card(target) or is_link_monster(target):
                raise IllegalActionError("Target is not a LIGHT non-Link Fiend monster.")

            if source == "gy":
                if source_index < 0 or source_index >= len(state.gy):
                    raise IllegalActionError("Source index out of range for Fiendsmith's Sequence.")
                sequence = state.gy[source_index]
            elif source == "mz":
                if source_index < 0 or source_index >= len(state.field.mz):
                    raise IllegalActionError("Source index out of range for Fiendsmith's Sequence.")
                sequence = state.field.mz[source_index]
            else:
                if source_index < 0 or source_index >= len(state.field.emz):
                    raise IllegalActionError("Source index out of range for Fiendsmith's Sequence.")
                sequence = state.field.emz[source_index]
            if not sequence or sequence.cid != FIENDSMITH_SEQUENCE_CID:
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
                sequence_card.metadata["link_rating"] = LINK_RATING_BY_CID.get(sequence_card.cid, 2)
            new_state.equip_card(sequence_card, new_state.field.mz[target_index])
            new_state.opt_used[f"{FIENDSMITH_SEQUENCE_CID}:e2"] = True
            return new_state

        raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")


class FiendsmithRextremendeEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        if OPP_TURN_EVENT in state.events:
            return []

        actions: list[EffectAction] = []

        if not state.opt_used.get(f"{FIENDSMITH_REXTREMENDE_CID}:e1"):
            for mz_index, card in enumerate(state.field.mz):
                if not card or card.cid != FIENDSMITH_REXTREMENDE_CID:
                    continue
                if not card.properly_summoned:
                    continue
                for hand_index, _hand_card in enumerate(state.hand):
                    for deck_index, deck_card in enumerate(state.deck):
                        if deck_card.cid not in REXTREMENDE_SEND_ALLOWLIST:
                            continue
                        if not is_light_fiend_card(deck_card):
                            continue
                        actions.append(
                            EffectAction(
                                cid=FIENDSMITH_REXTREMENDE_CID,
                                name=card.name,
                                effect_id="rextremende_discard_send_light_fiend",
                                params={
                                    "mz_index": mz_index,
                                    "hand_index": hand_index,
                                    "send_source": "deck",
                                    "send_index": deck_index,
                                },
                                sort_key=(
                                    FIENDSMITH_REXTREMENDE_CID,
                                    "rextremende_discard_send_light_fiend",
                                    mz_index,
                                    hand_index,
                                    "deck",
                                    deck_index,
                                ),
                            )
                        )
                    for extra_index, extra_card in enumerate(state.extra):
                        if extra_card.cid not in REXTREMENDE_SEND_ALLOWLIST:
                            continue
                        if not is_light_fiend_card(extra_card):
                            continue
                        actions.append(
                            EffectAction(
                                cid=FIENDSMITH_REXTREMENDE_CID,
                                name=card.name,
                                effect_id="rextremende_discard_send_light_fiend",
                                params={
                                    "mz_index": mz_index,
                                    "hand_index": hand_index,
                                    "send_source": "extra",
                                    "send_index": extra_index,
                                },
                                sort_key=(
                                    FIENDSMITH_REXTREMENDE_CID,
                                    "rextremende_discard_send_light_fiend",
                                    mz_index,
                                    hand_index,
                                    "extra",
                                    extra_index,
                                ),
                            )
                        )

        if (
            not state.opt_used.get(f"{FIENDSMITH_REXTREMENDE_CID}:e2")
            and FIENDSMITH_REXTREMENDE_CID in state.last_moved_to_gy
        ):
            rext_indices = [
                idx for idx, card in enumerate(state.gy) if card.cid == FIENDSMITH_REXTREMENDE_CID
            ]
            if rext_indices:
                for rext_index in rext_indices:
                    for target_index, card in enumerate(state.gy):
                        if target_index == rext_index:
                            continue
                        if card.cid not in REXTREMENDE_RECOVER_ALLOWLIST:
                            continue
                        actions.append(
                            EffectAction(
                                cid=FIENDSMITH_REXTREMENDE_CID,
                                name=card.name,
                                effect_id="gy_rextremende_recover_fiendsmith",
                                params={
                                    "rext_gy_index": rext_index,
                                    "target_zone": "gy",
                                    "target_index": target_index,
                                },
                                sort_key=(
                                    FIENDSMITH_REXTREMENDE_CID,
                                    "gy_rextremende_recover_fiendsmith",
                                    rext_index,
                                    "gy",
                                    target_index,
                                ),
                            )
                        )
                    for target_index, card in enumerate(state.banished):
                        if card.cid not in REXTREMENDE_RECOVER_ALLOWLIST:
                            continue
                        actions.append(
                            EffectAction(
                                cid=FIENDSMITH_REXTREMENDE_CID,
                                name=card.name,
                                effect_id="gy_rextremende_recover_fiendsmith",
                                params={
                                    "rext_gy_index": rext_index,
                                    "target_zone": "banished",
                                    "target_index": target_index,
                                },
                                sort_key=(
                                    FIENDSMITH_REXTREMENDE_CID,
                                    "gy_rextremende_recover_fiendsmith",
                                    rext_index,
                                    "banished",
                                    target_index,
                                ),
                            )
                        )

        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "rextremende_discard_send_light_fiend":
            if OPP_TURN_EVENT in state.events:
                raise IllegalActionError("Fiendsmith's Rextremende cannot be used on opponent turn.")
            if state.opt_used.get(f"{FIENDSMITH_REXTREMENDE_CID}:e1"):
                raise IllegalActionError("Fiendsmith's Rextremende effect already used.")

            mz_index = action.params.get("mz_index")
            hand_index = action.params.get("hand_index")
            send_source = action.params.get("send_source")
            send_index = action.params.get("send_index")
            if None in (mz_index, hand_index, send_source, send_index):
                raise SimModelError("Missing params for Fiendsmith's Rextremende effect.")
            if send_source not in {"deck", "extra"}:
                raise SimModelError("Invalid send source for Fiendsmith's Rextremende effect.")
            if not isinstance(mz_index, int) or not isinstance(hand_index, int) or not isinstance(send_index, int):
                raise SimModelError("Invalid index types for Fiendsmith's Rextremende effect.")
            if mz_index < 0 or mz_index >= len(state.field.mz):
                raise IllegalActionError("MZ index out of range for Fiendsmith's Rextremende.")
            if hand_index < 0 or hand_index >= len(state.hand):
                raise IllegalActionError("Hand index out of range for Fiendsmith's Rextremende.")

            rext = state.field.mz[mz_index]
            if not rext or rext.cid != FIENDSMITH_REXTREMENDE_CID:
                raise SimModelError("Selected field card is not Fiendsmith's Rextremende.")
            if not rext.properly_summoned:
                raise IllegalActionError("Fiendsmith's Rextremende must be properly summoned.")

            if send_source == "deck":
                if send_index < 0 or send_index >= len(state.deck):
                    raise IllegalActionError("Deck index out of range for Fiendsmith's Rextremende.")
                target = state.deck[send_index]
            else:
                if send_index < 0 or send_index >= len(state.extra):
                    raise IllegalActionError("Extra index out of range for Fiendsmith's Rextremende.")
                target = state.extra[send_index]
            if target.cid not in REXTREMENDE_SEND_ALLOWLIST or not is_light_fiend_card(target):
                raise IllegalActionError("Selected target is not an allowed LIGHT Fiend.")

            new_state = state.clone()
            discarded = new_state.hand.pop(hand_index)
            new_state.gy.append(discarded)

            if send_source == "deck":
                sent = new_state.deck.pop(send_index)
                new_state.gy.append(sent)
            else:
                sent = new_state.extra.pop(send_index)
                sent.metadata.setdefault("from_extra", True)
                new_state.gy.append(sent)

            new_state.opt_used[f"{FIENDSMITH_REXTREMENDE_CID}:e1"] = True
            return new_state

        if action.effect_id == "gy_rextremende_recover_fiendsmith":
            if OPP_TURN_EVENT in state.events:
                raise IllegalActionError("Fiendsmith's Rextremende cannot be used on opponent turn.")
            if state.opt_used.get(f"{FIENDSMITH_REXTREMENDE_CID}:e2"):
                raise IllegalActionError("Fiendsmith's Rextremende effect already used.")
            if FIENDSMITH_REXTREMENDE_CID not in state.last_moved_to_gy:
                raise IllegalActionError("Fiendsmith's Rextremende was not just sent to GY.")

            rext_index = action.params.get("rext_gy_index")
            target_zone = action.params.get("target_zone")
            target_index = action.params.get("target_index")
            if None in (rext_index, target_zone, target_index):
                raise SimModelError("Missing params for Fiendsmith's Rextremende recovery.")
            if target_zone not in {"gy", "banished"}:
                raise SimModelError("Invalid target zone for Fiendsmith's Rextremende recovery.")
            if not isinstance(rext_index, int) or not isinstance(target_index, int):
                raise SimModelError("Invalid index types for Fiendsmith's Rextremende recovery.")
            if rext_index < 0 or rext_index >= len(state.gy):
                raise IllegalActionError("GY index out of range for Fiendsmith's Rextremende.")
            if state.gy[rext_index].cid != FIENDSMITH_REXTREMENDE_CID:
                raise SimModelError("Selected GY card is not Fiendsmith's Rextremende.")

            if target_zone == "gy":
                if target_index < 0 or target_index >= len(state.gy):
                    raise IllegalActionError("Target GY index out of range for Fiendsmith's Rextremende.")
                target = state.gy[target_index]
            else:
                if target_index < 0 or target_index >= len(state.banished):
                    raise IllegalActionError(
                        "Target banished index out of range for Fiendsmith's Rextremende."
                    )
                target = state.banished[target_index]
            if target.cid not in REXTREMENDE_RECOVER_ALLOWLIST:
                raise IllegalActionError("Selected target is not a Fiendsmith card.")

            new_state = state.clone()
            if target_zone == "gy":
                recovered = new_state.gy.pop(target_index)
            else:
                recovered = new_state.banished.pop(target_index)
            new_state.hand.append(recovered)
            new_state.opt_used[f"{FIENDSMITH_REXTREMENDE_CID}:e2"] = True
            new_state.last_moved_to_gy = []
            return new_state

        raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")


class FiendsmithInParadiseEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        if OPP_TURN_EVENT in state.events and not state.opt_used.get(
            f"{FIENDSMITH_IN_PARADISE_CID}:e2"
        ):
            for gy_index, card in enumerate(state.gy):
                if card.cid != FIENDSMITH_IN_PARADISE_CID:
                    continue
                for deck_index, deck_card in enumerate(state.deck):
                    if deck_card.cid not in PARADISE_SEND_ALLOWLIST:
                        continue
                    actions.append(
                        EffectAction(
                            cid=FIENDSMITH_IN_PARADISE_CID,
                            name=card.name,
                            effect_id="paradise_gy_banish_send_fiendsmith",
                            params={
                                "gy_index": gy_index,
                                "send_source": "deck",
                                "send_index": deck_index,
                            },
                            sort_key=(
                                FIENDSMITH_IN_PARADISE_CID,
                                "paradise_gy_banish_send_fiendsmith",
                                gy_index,
                                "deck",
                                deck_index,
                            ),
                        )
                    )
                for extra_index, extra_card in enumerate(state.extra):
                    if extra_card.cid not in PARADISE_SEND_ALLOWLIST:
                        continue
                    actions.append(
                        EffectAction(
                            cid=FIENDSMITH_IN_PARADISE_CID,
                            name=card.name,
                            effect_id="paradise_gy_banish_send_fiendsmith",
                            params={
                                "gy_index": gy_index,
                                "send_source": "extra",
                                "send_index": extra_index,
                            },
                            sort_key=(
                                FIENDSMITH_IN_PARADISE_CID,
                                "paradise_gy_banish_send_fiendsmith",
                                gy_index,
                                "extra",
                                extra_index,
                            ),
                        )
                    )

        if not state.opt_used.get(f"{FIENDSMITH_PARADISE_CID}:e1"):
            if OPP_SPECIAL_SUMMON_EVENT in state.events:
                desirae_indices = [
                    idx for idx, card in enumerate(state.extra) if card.cid == FIENDSMITH_DESIRAE_CID
                ]
                if desirae_indices:
                    for gy_index, card in enumerate(state.gy):
                        if card.cid != FIENDSMITH_PARADISE_CID:
                            continue
                        for extra_index in desirae_indices:
                            actions.append(
                                EffectAction(
                                    cid=FIENDSMITH_PARADISE_CID,
                                    name=card.name,
                                    effect_id="gy_banish_send_desirae",
                                    params={"gy_index": gy_index, "extra_index": extra_index},
                                    sort_key=(
                                        FIENDSMITH_PARADISE_CID,
                                        "gy_banish_send_desirae",
                                        gy_index,
                                        extra_index,
                                    ),
                                )
                            )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "paradise_gy_banish_send_fiendsmith":
            if OPP_TURN_EVENT not in state.events:
                raise IllegalActionError("Fiendsmith in Paradise requires opponent turn.")
            if state.opt_used.get(f"{FIENDSMITH_IN_PARADISE_CID}:e2"):
                raise IllegalActionError("Fiendsmith in Paradise effect already used.")

            gy_index = action.params.get("gy_index")
            send_source = action.params.get("send_source")
            send_index = action.params.get("send_index")
            if None in (gy_index, send_source, send_index):
                raise SimModelError("Missing params for Fiendsmith in Paradise effect.")
            if not isinstance(gy_index, int) or not isinstance(send_index, int):
                raise SimModelError("Invalid index types for Fiendsmith in Paradise effect.")
            if send_source not in {"deck", "extra"}:
                raise SimModelError("Invalid send source for Fiendsmith in Paradise effect.")
            if gy_index < 0 or gy_index >= len(state.gy):
                raise IllegalActionError("GY index out of range for Fiendsmith in Paradise.")
            if state.gy[gy_index].cid != FIENDSMITH_IN_PARADISE_CID:
                raise SimModelError("Selected GY card is not Fiendsmith in Paradise.")

            if send_source == "deck":
                if send_index < 0 or send_index >= len(state.deck):
                    raise IllegalActionError("Deck index out of range for Fiendsmith in Paradise.")
                if state.deck[send_index].cid not in PARADISE_SEND_ALLOWLIST:
                    raise IllegalActionError("Selected deck card is not a Fiendsmith monster.")
            else:
                if send_index < 0 or send_index >= len(state.extra):
                    raise IllegalActionError("Extra index out of range for Fiendsmith in Paradise.")
                if state.extra[send_index].cid not in PARADISE_SEND_ALLOWLIST:
                    raise IllegalActionError("Selected Extra Deck card is not a Fiendsmith monster.")

            new_state = state.clone()
            paradise = new_state.gy.pop(gy_index)
            new_state.banished.append(paradise)
            if send_source == "deck":
                sent = new_state.deck.pop(send_index)
            else:
                sent = new_state.extra.pop(send_index)
                sent.metadata["from_extra"] = True
            new_state.gy.append(sent)
            new_state.last_moved_to_gy = [sent.cid]
            new_state.opt_used[f"{FIENDSMITH_IN_PARADISE_CID}:e2"] = True
            return new_state

        if action.effect_id == "gy_banish_send_desirae":
            if state.opt_used.get(f"{FIENDSMITH_PARADISE_CID}:e1"):
                raise IllegalActionError("Fiendsmith in Paradise effect already used.")
            if OPP_SPECIAL_SUMMON_EVENT not in state.events:
                raise IllegalActionError("Fiendsmith in Paradise requires opponent Special Summon.")

            gy_index = action.params.get("gy_index")
            extra_index = action.params.get("extra_index")
            if gy_index is None or extra_index is None:
                raise SimModelError("Missing params for Fiendsmith in Paradise effect.")
            if gy_index < 0 or gy_index >= len(state.gy):
                raise IllegalActionError("GY index out of range for Fiendsmith in Paradise.")
            if extra_index < 0 or extra_index >= len(state.extra):
                raise IllegalActionError("Extra index out of range for Fiendsmith in Paradise.")

            if state.gy[gy_index].cid != FIENDSMITH_PARADISE_CID:
                raise SimModelError("Selected GY card is not Fiendsmith in Paradise.")
            if state.extra[extra_index].cid != FIENDSMITH_DESIRAE_CID:
                raise IllegalActionError("Selected Extra Deck card is not Fiendsmith's Desirae.")

            new_state = state.clone()
            paradise = new_state.gy.pop(gy_index)
            new_state.banished.append(paradise)

            desirae = new_state.extra.pop(extra_index)
            new_state.gy.append(desirae)
            new_state.opt_used[f"{FIENDSMITH_PARADISE_CID}:e1"] = True
            new_state.last_moved_to_gy = [FIENDSMITH_DESIRAE_CID]
            if OPP_SPECIAL_SUMMON_EVENT in new_state.events:
                new_state.events = [
                    evt for evt in new_state.events if evt != OPP_SPECIAL_SUMMON_EVENT
                ]
            return new_state

        raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")


class FiendsmithKyrieEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        if OPP_TURN_EVENT in state.events:
            return []
        if not str(state.phase).lower().startswith("main"):
            return []
        if state.opt_used.get(f"{FIENDSMITH_KYRIE_CID}:e2"):
            return []

        kyrie_indices = [
            idx for idx, card in enumerate(state.gy) if card.cid == FIENDSMITH_KYRIE_CID
        ]
        if not kyrie_indices:
            return []

        # Find ANY Fiendsmith Fusion monster in Extra Deck
        fusion_indices = [
            idx for idx, card in enumerate(state.extra) if card.cid in FIENDSMITH_FUSION_CIDS
        ]
        open_mz = state.open_mz_indices()
        if not fusion_indices or not open_mz:
            return []

        material_pool: list[dict] = []
        for mz_index, card in enumerate(state.field.mz):
            if card:
                material_pool.append({"source": "mz", "index": mz_index})
        for emz_index, card in enumerate(state.field.emz):
            if card:
                material_pool.append({"source": "emz", "index": emz_index})
        for mz_index, card in enumerate(state.field.mz):
            if not card:
                continue
            for equip_index, _equip in enumerate(card.equipped):
                material_pool.append(
                    {
                        "source": "equip",
                        "host_zone": "mz",
                        "host_index": mz_index,
                        "equip_index": equip_index,
                    }
                )
        for emz_index, card in enumerate(state.field.emz):
            if not card:
                continue
            for equip_index, _equip in enumerate(card.equipped):
                material_pool.append(
                    {
                        "source": "equip",
                        "host_zone": "emz",
                        "host_index": emz_index,
                        "equip_index": equip_index,
                    }
                )

        actions: list[EffectAction] = []
        for gy_index in kyrie_indices:
            for extra_index in fusion_indices:
                for mz_index in open_mz:
                    for first_pos in range(len(material_pool)):
                        for second_pos in range(first_pos + 1, len(material_pool)):
                            materials = [
                                material_pool[first_pos],
                                material_pool[second_pos],
                            ]
                            cards = []
                            for material in materials:
                                source = material["source"]
                                if source == "mz":
                                    card = state.field.mz[material["index"]]
                                elif source == "emz":
                                    card = state.field.emz[material["index"]]
                                else:
                                    host_zone = material["host_zone"]
                                    host_index = material["host_index"]
                                    equip_index = material["equip_index"]
                                    host = (
                                        state.field.mz[host_index]
                                        if host_zone == "mz"
                                        else state.field.emz[host_index]
                                    )
                                    if host is None or equip_index >= len(host.equipped):
                                        card = None
                                    else:
                                        card = host.equipped[equip_index]
                                cards.append(card)
                            if any(card is None for card in cards):
                                continue
                            # Cannot use the target fusion as material
                            target_fusion_cid = state.extra[extra_index].cid
                            if any(card.cid == target_fusion_cid for card in cards):
                                continue
                            # Materials must be LIGHT Fiend (to satisfy Fusion material requirements)
                            if not all(is_light_fiend_card(card) for card in cards):
                                continue
                            # Rextremende requires Desirae as one of the materials
                            if target_fusion_cid == FIENDSMITH_REXTREMENDE_CID:
                                if not any(card.cid == FIENDSMITH_DESIRAE_CID for card in cards):
                                    continue
                            actions.append(
                                EffectAction(
                                    cid=FIENDSMITH_KYRIE_CID,
                                    name=state.gy[gy_index].name,
                                    effect_id="kyrie_gy_banish_fuse",
                                    params={
                                        "gy_index": gy_index,
                                        "extra_index": extra_index,
                                        "mz_index": mz_index,
                                        "materials": materials,
                                    },
                                    sort_key=(
                                        FIENDSMITH_KYRIE_CID,
                                        "kyrie_gy_banish_fuse",
                                        gy_index,
                                        extra_index,
                                        mz_index,
                                        tuple(
                                            (
                                                material.get("source"),
                                                material.get("host_zone"),
                                                material.get("host_index"),
                                                material.get("index"),
                                                material.get("equip_index"),
                                            )
                                            for material in materials
                                        ),
                                    ),
                                )
                            )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id != "kyrie_gy_banish_fuse":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if OPP_TURN_EVENT in state.events:
            raise IllegalActionError("Fiendsmith Kyrie cannot be used on opponent turn.")
        if not str(state.phase).lower().startswith("main"):
            raise IllegalActionError("Fiendsmith Kyrie requires Main Phase.")
        if state.opt_used.get(f"{FIENDSMITH_KYRIE_CID}:e2"):
            raise IllegalActionError("Fiendsmith Kyrie effect already used.")

        gy_index = action.params.get("gy_index")
        extra_index = action.params.get("extra_index")
        mz_index = action.params.get("mz_index")
        materials = action.params.get("materials")
        if None in (gy_index, extra_index, mz_index, materials):
            raise SimModelError("Missing params for Fiendsmith Kyrie effect.")
        if not isinstance(gy_index, int) or not isinstance(extra_index, int) or not isinstance(mz_index, int):
            raise SimModelError("Invalid index types for Fiendsmith Kyrie effect.")
        if not isinstance(materials, list) or len(materials) != 2:
            raise SimModelError("Invalid materials for Fiendsmith Kyrie effect.")
        if gy_index < 0 or gy_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for Fiendsmith Kyrie.")
        if state.gy[gy_index].cid != FIENDSMITH_KYRIE_CID:
            raise SimModelError("Selected GY card is not Fiendsmith Kyrie.")
        if extra_index < 0 or extra_index >= len(state.extra):
            raise IllegalActionError("Extra index out of range for Fiendsmith Kyrie.")
        if state.extra[extra_index].cid not in FIENDSMITH_FUSION_CIDS:
            raise IllegalActionError("Selected Extra Deck card is not a Fiendsmith Fusion monster.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Fiendsmith Kyrie.")

        material_cards = []
        for material in materials:
            if not isinstance(material, dict):
                raise SimModelError("Invalid material format for Fiendsmith Kyrie.")
            source = material.get("source")
            if source == "mz":
                index = material.get("index")
                if not isinstance(index, int) or index < 0 or index >= len(state.field.mz):
                    raise IllegalActionError("Material MZ index out of range for Fiendsmith Kyrie.")
                card = state.field.mz[index]
            elif source == "emz":
                index = material.get("index")
                if not isinstance(index, int) or index < 0 or index >= len(state.field.emz):
                    raise IllegalActionError("Material EMZ index out of range for Fiendsmith Kyrie.")
                card = state.field.emz[index]
            elif source == "equip":
                host_zone = material.get("host_zone")
                host_index = material.get("host_index")
                equip_index = material.get("equip_index")
                if host_zone not in {"mz", "emz"}:
                    raise SimModelError("Invalid equip host zone for Fiendsmith Kyrie.")
                if not isinstance(host_index, int) or not isinstance(equip_index, int):
                    raise SimModelError("Invalid equip indices for Fiendsmith Kyrie.")
                host = (
                    state.field.mz[host_index]
                    if host_zone == "mz"
                    else state.field.emz[host_index]
                )
                if host is None or equip_index < 0 or equip_index >= len(host.equipped):
                    raise IllegalActionError("Equip material index out of range for Fiendsmith Kyrie.")
                card = host.equipped[equip_index]
            else:
                raise SimModelError("Invalid material source for Fiendsmith Kyrie.")

            if card is None:
                raise IllegalActionError("Missing material for Fiendsmith Kyrie.")
            material_cards.append(card)

        # Cannot use the target fusion as material
        target_fusion_cid = state.extra[extra_index].cid
        if any(card.cid == target_fusion_cid for card in material_cards):
            raise IllegalActionError("Fiendsmith Kyrie cannot use the target Fusion as material.")
        # Materials must be LIGHT Fiend (to satisfy Fusion material requirements)
        if not all(is_light_fiend_card(card) for card in material_cards):
            raise IllegalActionError("Fiendsmith Kyrie requires LIGHT Fiend materials.")
        # Rextremende requires Desirae as one of the materials
        if target_fusion_cid == FIENDSMITH_REXTREMENDE_CID:
            if not any(card.cid == FIENDSMITH_DESIRAE_CID for card in material_cards):
                raise IllegalActionError("Rextremende requires Desirae as material.")

        new_state = state.clone()
        kyrie = new_state.gy.pop(gy_index)
        new_state.banished.append(kyrie)

        fusion = new_state.extra.pop(extra_index)
        fusion.properly_summoned = True
        fusion.metadata["from_extra"] = True
        new_state.field.mz[mz_index] = fusion

        removed_materials: list[CardInstance] = []
        for material in materials:
            source = material["source"]
            if source == "mz":
                index = material["index"]
                card = new_state.field.mz[index]
                if card is None:
                    raise IllegalActionError("Material missing from MZ for Fiendsmith Kyrie.")
                new_state.field.mz[index] = None
                removed_materials.append(card)
            elif source == "emz":
                index = material["index"]
                card = new_state.field.emz[index]
                if card is None:
                    raise IllegalActionError("Material missing from EMZ for Fiendsmith Kyrie.")
                new_state.field.emz[index] = None
                removed_materials.append(card)
            else:
                host_zone = material["host_zone"]
                host_index = material["host_index"]
                equip_index = material["equip_index"]
                host = (
                    new_state.field.mz[host_index]
                    if host_zone == "mz"
                    else new_state.field.emz[host_index]
                )
                if host is None or equip_index >= len(host.equipped):
                    raise IllegalActionError("Equip material missing for Fiendsmith Kyrie.")
                removed_materials.append(host.equipped.pop(equip_index))

        for card in removed_materials:
            new_state.gy.append(card)
        new_state.last_moved_to_gy = [card.cid for card in removed_materials]
        new_state.opt_used[f"{FIENDSMITH_KYRIE_CID}:e2"] = True
        return new_state
        if state.opt_used.get(f"{FIENDSMITH_PARADISE_CID}:e1"):
            raise IllegalActionError("Fiendsmith in Paradise effect already used.")
        if OPP_SPECIAL_SUMMON_EVENT not in state.events:
            raise IllegalActionError("Fiendsmith in Paradise requires opponent Special Summon.")

        gy_index = action.params.get("gy_index")
        extra_index = action.params.get("extra_index")
        if gy_index is None or extra_index is None:
            raise SimModelError("Missing params for Fiendsmith in Paradise effect.")
        if gy_index < 0 or gy_index >= len(state.gy):
            raise IllegalActionError("GY index out of range for Fiendsmith in Paradise.")
        if extra_index < 0 or extra_index >= len(state.extra):
            raise IllegalActionError("Extra index out of range for Fiendsmith in Paradise.")

        if state.gy[gy_index].cid != FIENDSMITH_PARADISE_CID:
            raise SimModelError("Selected GY card is not Fiendsmith in Paradise.")
        if state.extra[extra_index].cid != FIENDSMITH_DESIRAE_CID:
            raise IllegalActionError("Selected Extra Deck card is not Fiendsmith's Desirae.")

        new_state = state.clone()
        paradise = new_state.gy.pop(gy_index)
        new_state.banished.append(paradise)

        desirae = new_state.extra.pop(extra_index)
        new_state.gy.append(desirae)
        new_state.opt_used[f"{FIENDSMITH_PARADISE_CID}:e1"] = True
        new_state.last_moved_to_gy = [FIENDSMITH_DESIRAE_CID]
        if OPP_SPECIAL_SUMMON_EVENT in new_state.events:
            new_state.events = [evt for evt in new_state.events if evt != OPP_SPECIAL_SUMMON_EVENT]
        return new_state


class FiendsmithLacrimaEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []

        if not state.opt_used.get(f"{FIENDSMITH_LACRIMA_CID}:e1"):
            open_mz = state.open_mz_indices()
            prefer_ss = bool(open_mz)
            mz_index = open_mz[0] if open_mz else None

            field_entries: list[tuple[str, int, CardInstance]] = []
            for index, card in enumerate(state.field.mz):
                if card and card.cid == FIENDSMITH_LACRIMA_CID:
                    field_entries.append(("mz", index, card))
            for index, card in enumerate(state.field.emz):
                if card and card.cid == FIENDSMITH_LACRIMA_CID:
                    field_entries.append(("emz", index, card))

            targets: list[tuple[str, int, CardInstance]] = []
            for index, card in enumerate(state.gy):
                if is_light_fiend_card(card):
                    targets.append(("gy", index, card))
            for index, card in enumerate(state.banished):
                if is_light_fiend_card(card):
                    targets.append(("banished", index, card))

            if field_entries and targets:
                for zone, field_index, card in field_entries:
                    if not card.properly_summoned:
                        continue
                    if str(card.metadata.get("summon_type", "")).lower() != "fusion":
                        continue
                    for target_zone, target_index, target in targets:
                        if prefer_ss:
                            if not can_revive_from_gy(target):
                                continue
                            actions.append(
                                EffectAction(
                                    cid=FIENDSMITH_LACRIMA_CID,
                                    name=card.name,
                                    effect_id="lacrima_fusion_recover_light_fiend",
                                    params={
                                        "field_zone": zone,
                                        "field_index": field_index,
                                        "source_zone": target_zone,
                                        "source_index": target_index,
                                        "mode": "ss",
                                        "mz_index": mz_index,
                                    },
                                    sort_key=(
                                        FIENDSMITH_LACRIMA_CID,
                                        "lacrima_fusion_recover_light_fiend",
                                        zone,
                                        field_index,
                                        "ss",
                                        target_zone,
                                        target_index,
                                        mz_index,
                                    ),
                                )
                            )
                        else:
                            if is_extra_deck_monster(target):
                                continue
                            actions.append(
                                EffectAction(
                                    cid=FIENDSMITH_LACRIMA_CID,
                                    name=card.name,
                                    effect_id="lacrima_fusion_recover_light_fiend",
                                    params={
                                        "field_zone": zone,
                                        "field_index": field_index,
                                        "source_zone": target_zone,
                                        "source_index": target_index,
                                        "mode": "hand",
                                    },
                                    sort_key=(
                                        FIENDSMITH_LACRIMA_CID,
                                        "lacrima_fusion_recover_light_fiend",
                                        zone,
                                        field_index,
                                        "hand",
                                        target_zone,
                                        target_index,
                                    ),
                                )
                            )

        if state.opt_used.get(f"{FIENDSMITH_LACRIMA_CID}:e2"):
            return actions
        if FIENDSMITH_LACRIMA_CID not in state.last_moved_to_gy:
            return actions

        lacrima_indices = [
            idx for idx, card in enumerate(state.gy) if card.cid == FIENDSMITH_LACRIMA_CID
        ]
        if not lacrima_indices:
            return actions

        target_indices = [
            idx
            for idx, card in enumerate(state.gy)
            if card.cid != FIENDSMITH_LACRIMA_CID and is_light_fiend_card(card)
        ]
        if not target_indices:
            return actions

        for lacrima_index in lacrima_indices:
            for target_index in target_indices:
                actions.append(
                    EffectAction(
                        cid=FIENDSMITH_LACRIMA_CID,
                        name=state.gy[lacrima_index].name,
                        effect_id="lacrima_gy_shuffle_light_fiend",
                        params={
                            "lacrima_gy_index": lacrima_index,
                            "target_gy_index": target_index,
                        },
                        sort_key=(
                            FIENDSMITH_LACRIMA_CID,
                            "lacrima_gy_shuffle_light_fiend",
                            lacrima_index,
                            target_index,
                        ),
                    )
                )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "lacrima_fusion_recover_light_fiend":
            if state.opt_used.get(f"{FIENDSMITH_LACRIMA_CID}:e1"):
                raise IllegalActionError("Fiendsmith's Lacrima effect already used.")

            field_zone = action.params.get("field_zone")
            field_index = action.params.get("field_index")
            source_zone = action.params.get("source_zone")
            source_index = action.params.get("source_index")
            mode = action.params.get("mode")
            mz_index = action.params.get("mz_index")
            if None in (field_zone, field_index, source_zone, source_index, mode):
                raise SimModelError("Missing params for Fiendsmith's Lacrima effect.")
            if field_zone not in {"mz", "emz"}:
                raise SimModelError("Invalid field zone for Fiendsmith's Lacrima effect.")
            if source_zone not in {"gy", "banished"}:
                raise SimModelError("Invalid source zone for Fiendsmith's Lacrima effect.")
            if mode not in {"ss", "hand"}:
                raise SimModelError("Invalid mode for Fiendsmith's Lacrima effect.")
            if not isinstance(field_index, int) or not isinstance(source_index, int):
                raise SimModelError("Invalid index types for Fiendsmith's Lacrima effect.")
            if field_index < 0:
                raise IllegalActionError("Field index out of range for Fiendsmith's Lacrima.")
            if source_index < 0:
                raise IllegalActionError("Source index out of range for Fiendsmith's Lacrima.")

            if field_zone == "mz":
                if field_index >= len(state.field.mz):
                    raise IllegalActionError("Field index out of range for Fiendsmith's Lacrima.")
                lacrima = state.field.mz[field_index]
            else:
                if field_index >= len(state.field.emz):
                    raise IllegalActionError("Field index out of range for Fiendsmith's Lacrima.")
                lacrima = state.field.emz[field_index]
            if not lacrima or lacrima.cid != FIENDSMITH_LACRIMA_CID:
                raise SimModelError("Selected field card is not Fiendsmith's Lacrima.")
            if not lacrima.properly_summoned:
                raise IllegalActionError("Fiendsmith's Lacrima was not properly Fusion Summoned.")
            if str(lacrima.metadata.get("summon_type", "")).lower() != "fusion":
                raise IllegalActionError("Fiendsmith's Lacrima is not a Fusion monster.")

            if source_zone == "gy":
                if source_index >= len(state.gy):
                    raise IllegalActionError("GY index out of range for Fiendsmith's Lacrima.")
                target = state.gy[source_index]
            else:
                if source_index >= len(state.banished):
                    raise IllegalActionError("Banished index out of range for Fiendsmith's Lacrima.")
                target = state.banished[source_index]

            if not is_light_fiend_card(target):
                raise IllegalActionError("Target is not a LIGHT Fiend monster.")
            if mode == "ss":
                if mz_index is None or mz_index not in state.open_mz_indices():
                    raise IllegalActionError("No open Main Monster Zone for Fiendsmith's Lacrima.")
                if not can_revive_from_gy(target):
                    raise IllegalActionError("Target was not properly summoned.")
            else:
                if is_extra_deck_monster(target):
                    raise IllegalActionError("Cannot add Extra Deck monster to hand.")

            new_state = state.clone()
            if source_zone == "gy":
                recovered = new_state.gy.pop(source_index)
            else:
                recovered = new_state.banished.pop(source_index)
            if mode == "ss":
                new_state.field.mz[mz_index] = recovered
            else:
                new_state.hand.append(recovered)
            new_state.opt_used[f"{FIENDSMITH_LACRIMA_CID}:e1"] = True
            return new_state

        if action.effect_id == "lacrima_gy_shuffle_light_fiend":
            if state.opt_used.get(f"{FIENDSMITH_LACRIMA_CID}:e2"):
                raise IllegalActionError("Fiendsmith's Lacrima GY effect already used.")
            if FIENDSMITH_LACRIMA_CID not in state.last_moved_to_gy:
                raise IllegalActionError("Fiendsmith's Lacrima was not just sent to GY.")

            lacrima_index = action.params.get("lacrima_gy_index")
            target_index = action.params.get("target_gy_index")
            if lacrima_index is None or target_index is None:
                raise SimModelError("Missing params for Fiendsmith's Lacrima GY effect.")
            if not isinstance(lacrima_index, int) or not isinstance(target_index, int):
                raise SimModelError("Invalid index types for Fiendsmith's Lacrima GY effect.")
            if lacrima_index < 0 or lacrima_index >= len(state.gy):
                raise IllegalActionError("Lacrima GY index out of range.")
            if target_index < 0 or target_index >= len(state.gy):
                raise IllegalActionError("Target GY index out of range.")
            if lacrima_index == target_index:
                raise IllegalActionError("Target must be another LIGHT Fiend monster.")
            if state.gy[lacrima_index].cid != FIENDSMITH_LACRIMA_CID:
                raise SimModelError("Selected GY card is not Fiendsmith's Lacrima.")
            if not is_light_fiend_card(state.gy[target_index]):
                raise IllegalActionError("Target is not a LIGHT Fiend monster.")
            if state.gy[target_index].cid == FIENDSMITH_LACRIMA_CID:
                raise IllegalActionError("Target must be another LIGHT Fiend monster.")

            new_state = state.clone()
            target = new_state.gy.pop(target_index)
            if is_extra_deck_monster(target):
                target.metadata["from_extra"] = True
                new_state.extra.append(target)
            else:
                new_state.deck.append(target)
            new_state.opt_used[f"{FIENDSMITH_LACRIMA_CID}:e2"] = True
            new_state.last_moved_to_gy = []
            return new_state

        raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")


class FiendsmithDesiraeEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        for mz_index, card in enumerate(state.field.mz):
            if not card or card.cid != FIENDSMITH_DESIRAE_CID:
                continue
            total = total_equipped_link_rating(card)
            used = int(state.opt_used.get(f"{FIENDSMITH_DESIRAE_CID}:negates_used", 0))
            if total > used:
                actions.append(
                    EffectAction(
                        cid=FIENDSMITH_DESIRAE_CID,
                        name=card.name,
                        effect_id="desirae_negate",
                        params={"mz_index": mz_index},
                        sort_key=(
                            FIENDSMITH_DESIRAE_CID,
                            "desirae_negate",
                            mz_index,
                            used,
                        ),
                    )
                )

        if state.opt_used.get(f"{FIENDSMITH_DESIRAE_CID}:e1"):
            return actions
        if FIENDSMITH_DESIRAE_CID not in state.last_moved_to_gy:
            return actions

        desirae_indices = [idx for idx, card in enumerate(state.gy) if card.cid == FIENDSMITH_DESIRAE_CID]
        if not desirae_indices:
            return actions

        light_fiend_indices = [
            idx
            for idx, card in enumerate(state.gy)
            if card.cid != FIENDSMITH_DESIRAE_CID and is_light_fiend_card(card)
        ]
        if not light_fiend_indices:
            return actions

        field_targets: list[tuple[str, int, CardInstance]] = []
        for idx, card in enumerate(state.field.mz):
            if card:
                field_targets.append(("mz", idx, card))
        for idx, card in enumerate(state.field.emz):
            if card:
                field_targets.append(("emz", idx, card))
        for idx, card in enumerate(state.field.stz):
            if card:
                field_targets.append(("stz", idx, card))
        for idx, card in enumerate(state.field.fz):
            if card:
                field_targets.append(("fz", idx, card))
        if not field_targets:
            return actions

        for desirae_index in desirae_indices:
            for cost_index in light_fiend_indices:
                for zone, target_index, target_card in field_targets:
                    actions.append(
                        EffectAction(
                            cid=FIENDSMITH_DESIRAE_CID,
                            name=target_card.name,
                            effect_id="gy_desirae_send_field",
                            params={
                                "desirae_gy_index": desirae_index,
                                "cost_gy_index": cost_index,
                                "target_zone": zone,
                                "target_index": target_index,
                            },
                            sort_key=(
                                FIENDSMITH_DESIRAE_CID,
                                "gy_desirae_send_field",
                                desirae_index,
                                cost_index,
                                zone,
                                target_index,
                            ),
                        )
                    )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "desirae_negate":
            return self._apply_negate(state, action)
        if action.effect_id != "gy_desirae_send_field":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{FIENDSMITH_DESIRAE_CID}:e1"):
            raise IllegalActionError("Fiendsmith's Desirae effect already used.")
        if FIENDSMITH_DESIRAE_CID not in state.last_moved_to_gy:
            raise IllegalActionError("Fiendsmith's Desirae was not just sent to GY.")

        desirae_index = action.params.get("desirae_gy_index")
        cost_index = action.params.get("cost_gy_index")
        target_zone = action.params.get("target_zone")
        target_index = action.params.get("target_index")
        if None in (desirae_index, cost_index, target_zone, target_index):
            raise SimModelError("Missing params for Fiendsmith's Desirae effect.")

        if desirae_index < 0 or desirae_index >= len(state.gy):
            raise IllegalActionError("Desirae GY index out of range.")
        if cost_index < 0 or cost_index >= len(state.gy):
            raise IllegalActionError("Cost GY index out of range.")

        if state.gy[desirae_index].cid != FIENDSMITH_DESIRAE_CID:
            raise SimModelError("Selected GY card is not Fiendsmith's Desirae.")
        if state.gy[cost_index].cid == FIENDSMITH_DESIRAE_CID:
            raise IllegalActionError("Cost must be another LIGHT Fiend monster.")
        if not is_light_fiend_card(state.gy[cost_index]):
            raise IllegalActionError("Cost must be another LIGHT Fiend monster.")

        new_state = state.clone()
        cost_card = new_state.gy.pop(cost_index)
        new_state.deck.append(cost_card)

        target_card: CardInstance | None
        if target_zone == "mz":
            if target_index < 0 or target_index >= len(new_state.field.mz):
                raise IllegalActionError("Target index out of range for MZ.")
            target_card = new_state.field.mz[target_index]
            new_state.field.mz[target_index] = None
        elif target_zone == "emz":
            if target_index < 0 or target_index >= len(new_state.field.emz):
                raise IllegalActionError("Target index out of range for EMZ.")
            target_card = new_state.field.emz[target_index]
            new_state.field.emz[target_index] = None
        elif target_zone == "stz":
            if target_index < 0 or target_index >= len(new_state.field.stz):
                raise IllegalActionError("Target index out of range for STZ.")
            target_card = new_state.field.stz[target_index]
            new_state.field.stz[target_index] = None
        elif target_zone == "fz":
            if target_index < 0 or target_index >= len(new_state.field.fz):
                raise IllegalActionError("Target index out of range for FZ.")
            target_card = new_state.field.fz[target_index]
            new_state.field.fz[target_index] = None
        else:
            raise SimModelError("Invalid target zone for Fiendsmith's Desirae effect.")

        if target_card is None:
            raise IllegalActionError("Target card missing from field.")
        new_state.gy.append(target_card)

        new_state.opt_used[f"{FIENDSMITH_DESIRAE_CID}:e1"] = True
        new_state.last_moved_to_gy = []
        return new_state

    def _apply_negate(self, state: GameState, action: EffectAction) -> GameState:
        mz_index = action.params.get("mz_index")
        if mz_index is None:
            raise SimModelError("Missing params for Fiendsmith's Desirae negate.")
        if not isinstance(mz_index, int):
            raise SimModelError("Invalid index type for Fiendsmith's Desirae negate.")
        if mz_index < 0 or mz_index >= len(state.field.mz):
            raise IllegalActionError("MZ index out of range for Fiendsmith's Desirae negate.")
        desirae = state.field.mz[mz_index]
        if not desirae or desirae.cid != FIENDSMITH_DESIRAE_CID:
            raise IllegalActionError("Fiendsmith's Desirae not found for negate.")

        total = total_equipped_link_rating(desirae)
        used = int(state.opt_used.get(f"{FIENDSMITH_DESIRAE_CID}:negates_used", 0))
        if total <= used:
            raise IllegalActionError("No remaining Desirae negates available.")

        new_state = state.clone()
        new_state.opt_used[f"{FIENDSMITH_DESIRAE_CID}:negates_used"] = used + 1
        return new_state


class FiendsmithSanctEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        if not controls_only_light_fiends(state):
            return []

        open_mz = state.open_mz_indices()
        if not open_mz:
            return []

        actions: list[EffectAction] = []
        for hand_index, card in enumerate(state.hand):
            if card.cid != FIENDSMITH_SANCT_CID:
                continue
            for mz_index in open_mz:
                actions.append(
                    EffectAction(
                        cid=FIENDSMITH_SANCT_CID,
                        name=card.name,
                        effect_id="activate_sanct_token",
                        params={"hand_index": hand_index, "mz_index": mz_index},
                        sort_key=(
                            FIENDSMITH_SANCT_CID,
                            "activate_sanct_token",
                            hand_index,
                            mz_index,
                        ),
                    )
                )
        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id != "activate_sanct_token":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")

        hand_index = action.params.get("hand_index")
        mz_index = action.params.get("mz_index")
        if hand_index is None or mz_index is None:
            raise SimModelError("Missing params for Fiendsmith's Sanct effect.")
        if hand_index < 0 or hand_index >= len(state.hand):
            raise IllegalActionError("Hand index out of range for Fiendsmith's Sanct.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Fiendsmith's Sanct.")
        if not controls_only_light_fiends(state):
            raise IllegalActionError("Fiendsmith's Sanct requires only LIGHT Fiend monsters.")
        if state.hand[hand_index].cid != FIENDSMITH_SANCT_CID:
            raise SimModelError("Action does not match Fiendsmith's Sanct card.")

        new_state = state.clone()
        sanct = new_state.hand.pop(hand_index)
        new_state.gy.append(sanct)
        new_state.field.mz[mz_index] = make_fiendsmith_token()
        return new_state


class FiendsmithRequiemEffect(EffectImpl):
    def enumerate_actions(self, state: GameState) -> list[EffectAction]:
        actions: list[EffectAction] = []
        open_mz = state.open_mz_indices()

        field_entries = []
        for index, card in enumerate(state.field.mz):
            if card and card.cid == FIENDSMITH_REQUIEM_CID:
                field_entries.append(("mz", index, card))
        for index, card in enumerate(state.field.emz):
            if card and card.cid == FIENDSMITH_REQUIEM_CID:
                field_entries.append(("emz", index, card))

        if field_entries and "Main Phase" in state.phase and not state.opt_used.get(f"{FIENDSMITH_REQUIEM_CID}:e1"):
            for zone, field_index, card in field_entries:
                for source_index, source_card in enumerate(state.hand):
                    if source_card.cid not in REQUIEM_QUICK_TARGET_CIDS:
                        continue
                    for mz_index in open_mz:
                        actions.append(
                            EffectAction(
                                cid=FIENDSMITH_REQUIEM_CID,
                                name=card.name,
                                effect_id="tribute_self_ss_fiendsmith",
                                params={
                                    "zone": zone,
                                    "field_index": field_index,
                                    "source": "hand",
                                    "source_index": source_index,
                                    "mz_index": mz_index,
                                },
                                sort_key=(
                                    FIENDSMITH_REQUIEM_CID,
                                    "tribute_self_ss_fiendsmith",
                                    zone,
                                    field_index,
                                    "hand",
                                    source_index,
                                    mz_index,
                                ),
                            )
                        )
                for source_index, source_card in enumerate(state.deck):
                    if source_card.cid not in REQUIEM_QUICK_TARGET_CIDS:
                        continue
                    for mz_index in open_mz:
                        actions.append(
                            EffectAction(
                                cid=FIENDSMITH_REQUIEM_CID,
                                name=card.name,
                                effect_id="tribute_self_ss_fiendsmith",
                                params={
                                    "zone": zone,
                                    "field_index": field_index,
                                    "source": "deck",
                                    "source_index": source_index,
                                    "mz_index": mz_index,
                                },
                                sort_key=(
                                    FIENDSMITH_REQUIEM_CID,
                                    "tribute_self_ss_fiendsmith",
                                    zone,
                                    field_index,
                                    "deck",
                                    source_index,
                                    mz_index,
                                ),
                            )
                        )

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
            for gy_index, card in enumerate(state.gy):
                if card.cid != FIENDSMITH_REQUIEM_CID:
                    continue
                for mz_index, target in targets:
                    actions.append(
                        EffectAction(
                            cid=FIENDSMITH_REQUIEM_CID,
                            name=card.name,
                            effect_id="equip_requiem_to_fiend",
                            params={
                                "source": "gy",
                                "source_index": gy_index,
                                "target_mz_index": mz_index,
                            },
                            sort_key=(
                                FIENDSMITH_REQUIEM_CID,
                                "equip_requiem_to_fiend",
                                "gy",
                                gy_index,
                                mz_index,
                            ),
                        )
                    )
            for zone, field_index, card in field_entries:
                for mz_index, target in targets:
                    actions.append(
                        EffectAction(
                            cid=FIENDSMITH_REQUIEM_CID,
                            name=card.name,
                            effect_id="equip_requiem_to_fiend",
                            params={
                                "source": zone,
                                "source_index": field_index,
                                "target_mz_index": mz_index,
                            },
                            sort_key=(
                                FIENDSMITH_REQUIEM_CID,
                                "equip_requiem_to_fiend",
                                zone,
                                field_index,
                                mz_index,
                            ),
                        )
                    )

        return actions

    def apply(self, state: GameState, action: EffectAction) -> GameState:
        if action.effect_id == "equip_requiem_to_fiend":
            return self._apply_equip(state, action)
        if action.effect_id != "tribute_self_ss_fiendsmith":
            raise SimModelError(f"Unmodeled effect_id: {action.effect_id}")
        if state.opt_used.get(f"{FIENDSMITH_REQUIEM_CID}:e1"):
            raise IllegalActionError("Fiendsmith's Requiem effect already used.")

        zone = action.params.get("zone")
        field_index = action.params.get("field_index")
        source = action.params.get("source")
        source_index = action.params.get("source_index")
        mz_index = action.params.get("mz_index")
        if None in (zone, field_index, source, source_index, mz_index):
            raise SimModelError("Missing params for Fiendsmith's Requiem effect.")

        if zone not in {"mz", "emz"}:
            raise SimModelError("Invalid zone for Fiendsmith's Requiem effect.")
        if not isinstance(field_index, int) or not isinstance(source_index, int) or not isinstance(mz_index, int):
            raise SimModelError("Invalid index types for Fiendsmith's Requiem effect.")
        if mz_index not in state.open_mz_indices():
            raise IllegalActionError("No open Main Monster Zone for Fiendsmith's Requiem.")

        if zone == "mz":
            if field_index < 0 or field_index >= len(state.field.mz):
                raise IllegalActionError("Field index out of range for Requiem.")
            requiem = state.field.mz[field_index]
        else:
            if field_index < 0 or field_index >= len(state.field.emz):
                raise IllegalActionError("Field index out of range for Requiem.")
            requiem = state.field.emz[field_index]
        if not requiem or requiem.cid != FIENDSMITH_REQUIEM_CID:
            raise SimModelError("Selected field card is not Fiendsmith's Requiem.")

        if source == "hand":
            if source_index < 0 or source_index >= len(state.hand):
                raise IllegalActionError("Source index out of range for Requiem.")
            target = state.hand[source_index]
        elif source == "deck":
            if source_index < 0 or source_index >= len(state.deck):
                raise IllegalActionError("Source index out of range for Requiem.")
            target = state.deck[source_index]
        else:
            raise SimModelError("Invalid source for Fiendsmith's Requiem effect.")

        if target.cid not in REQUIEM_QUICK_TARGET_CIDS:
            raise IllegalActionError("Selected target is not an allowed Fiendsmith monster.")

        new_state = state.clone()
        if zone == "mz":
            requiem_card = new_state.field.mz[field_index]
            new_state.field.mz[field_index] = None
        else:
            requiem_card = new_state.field.emz[field_index]
            new_state.field.emz[field_index] = None
        new_state.gy.append(requiem_card)

        if source == "hand":
            summoned = new_state.hand.pop(source_index)
        else:
            summoned = new_state.deck.pop(source_index)

        new_state.field.mz[mz_index] = summoned
        new_state.opt_used[f"{FIENDSMITH_REQUIEM_CID}:e1"] = True
        return new_state

    def _apply_equip(self, state: GameState, action: EffectAction) -> GameState:
        source = action.params.get("source")
        source_index = action.params.get("source_index")
        target_index = action.params.get("target_mz_index")
        if None in (source, source_index, target_index):
            raise SimModelError("Missing params for Fiendsmith's Requiem equip effect.")
        if not isinstance(source_index, int) or not isinstance(target_index, int):
            raise SimModelError("Invalid index types for Fiendsmith's Requiem equip effect.")
        if target_index < 0 or target_index >= len(state.field.mz):
            raise IllegalActionError("Target index out of range for Fiendsmith's Requiem equip.")

        target = state.field.mz[target_index]
        if not target or not is_light_fiend_card(target) or is_link_monster(target):
            raise IllegalActionError("Target is not a LIGHT non-Link Fiend monster.")

        if source == "gy":
            if source_index < 0 or source_index >= len(state.gy):
                raise IllegalActionError("Source index out of range for Fiendsmith's Requiem equip.")
            requiem = state.gy[source_index]
            if requiem.cid != FIENDSMITH_REQUIEM_CID:
                raise SimModelError("Selected GY card is not Fiendsmith's Requiem.")
        elif source == "mz":
            if source_index < 0 or source_index >= len(state.field.mz):
                raise IllegalActionError("Source index out of range for Fiendsmith's Requiem equip.")
            requiem = state.field.mz[source_index]
            if not requiem or requiem.cid != FIENDSMITH_REQUIEM_CID:
                raise SimModelError("Selected field card is not Fiendsmith's Requiem.")
        elif source == "emz":
            if source_index < 0 or source_index >= len(state.field.emz):
                raise IllegalActionError("Source index out of range for Fiendsmith's Requiem equip.")
            requiem = state.field.emz[source_index]
            if not requiem or requiem.cid != FIENDSMITH_REQUIEM_CID:
                raise SimModelError("Selected field card is not Fiendsmith's Requiem.")
        else:
            raise SimModelError("Invalid source for Fiendsmith's Requiem equip.")

        new_state = state.clone()
        if source == "gy":
            requiem_card = new_state.gy.pop(source_index)
        elif source == "mz":
            requiem_card = new_state.field.mz[source_index]
            new_state.field.mz[source_index] = None
        else:
            requiem_card = new_state.field.emz[source_index]
            new_state.field.emz[source_index] = None

        if requiem_card is None:
            raise IllegalActionError("Fiendsmith's Requiem missing for equip.")
        if "link_rating" not in requiem_card.metadata:
            requiem_card.metadata["link_rating"] = LINK_RATING_BY_CID.get(requiem_card.cid, 1)

        new_state.equip_card(requiem_card, new_state.field.mz[target_index])
        return new_state
