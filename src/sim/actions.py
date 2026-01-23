from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any

from .errors import IllegalActionError
from .state import CardInstance, GameState


@dataclass(frozen=True)
class Action:
    action_type: str
    params: dict[str, Any]

    def describe(self) -> str:
        return f"{self.action_type}: {self.params}"


def move_card_to_gy(state: GameState, zone: str, index: int) -> None:
    if zone == "mz":
        card = state.field.mz[index]
        state.field.mz[index] = None
    elif zone == "emz":
        card = state.field.emz[index]
        state.field.emz[index] = None
    else:
        raise IllegalActionError(f"Unsupported zone for material removal: {zone}")
    if card is None:
        raise IllegalActionError("Material missing from field.")
    state.gy.append(card)


def tributes_required(level: int) -> int:
    """Return number of tributes required to Normal Summon a monster of given level."""
    if level <= 4:
        return 0
    if level <= 6:
        return 1
    return 2


def validate_normal_summon(state: GameState) -> None:
    if state.normal_summon_set_used:
        raise IllegalActionError("Normal Summon/Set already used this turn.")


def apply_normal_summon(
    state: GameState,
    hand_index: int,
    mz_index: int,
    tribute_indices: list[int] | None = None,
) -> None:
    validate_normal_summon(state)
    if hand_index < 0 or hand_index >= len(state.hand):
        raise IllegalActionError("Hand index out of range.")

    card = state.hand[hand_index]
    level = int(card.metadata.get("level", 4))
    required = tributes_required(level)

    tribute_indices = tribute_indices or []
    if len(tribute_indices) < required:
        raise IllegalActionError(
            f"Level {level} monster requires {required} tribute(s), got {len(tribute_indices)}."
        )

    # Validate tribute indices
    for idx in tribute_indices:
        if idx < 0 or idx >= len(state.field.mz) or state.field.mz[idx] is None:
            raise IllegalActionError(f"Invalid tribute index: {idx}")

    if mz_index not in state.open_mz_indices() and mz_index not in tribute_indices:
        raise IllegalActionError("No open Main Monster Zone for Normal Summon.")

    # Send tributes to GY
    for idx in sorted(tribute_indices, reverse=True):
        move_card_to_gy(state, "mz", idx)

    # Place the summoned monster
    summoned = state.hand.pop(hand_index)
    # Use first tribute's zone if available, otherwise use specified mz_index
    target_zone = tribute_indices[0] if tribute_indices else mz_index
    state.field.mz[target_zone] = summoned
    state.normal_summon_set_used = True


def apply_special_summon(state: GameState, hand_index: int, mz_index: int) -> None:
    if mz_index not in state.open_mz_indices():
        raise IllegalActionError("No open Main Monster Zone for Special Summon.")
    if hand_index < 0 or hand_index >= len(state.hand):
        raise IllegalActionError("Hand index out of range.")
    card = state.hand.pop(hand_index)
    state.field.mz[mz_index] = card


def material_matches_requirements(
    card: CardInstance,
    material_attribute: str | None = None,
    material_race: str | None = None,
) -> bool:
    """Check if a single card satisfies material attribute/race requirements."""
    if material_attribute:
        card_attr = str(card.metadata.get("attribute", "")).upper()
        if card_attr != material_attribute.upper():
            return False
    if material_race:
        card_race = str(card.metadata.get("race", "")).upper()
        if card_race != material_race.upper():
            return False
    return True


def materials_satisfy_requirements(
    material_cards: list[CardInstance],
    extra_card: CardInstance,
) -> bool:
    """Check if all materials satisfy the Extra Deck monster's requirements."""
    material_attribute = extra_card.metadata.get("material_attribute")
    material_race = extra_card.metadata.get("material_race")

    # If no requirements specified, any materials are valid
    if not material_attribute and not material_race:
        return True

    # All materials must match the requirements
    for card in material_cards:
        if not material_matches_requirements(card, material_attribute, material_race):
            return False
    return True


def link_material_count_ok(materials: list[CardInstance], link_rating: int, min_materials: int) -> bool:
    if len(materials) < min_materials:
        return False
    possible = {0}
    for card in materials:
        rating = int(card.metadata.get("link_rating", 0))
        options = {1}
        if rating > 0:
            options.add(rating)
        next_possible = set()
        for total in possible:
            for value in options:
                next_possible.add(total + value)
        possible = next_possible
    return link_rating in possible


def xyz_materials_valid(materials: list[CardInstance], xyz_rank: int) -> bool:
    """Validate Xyz summon materials.

    Xyz summons require:
    1. All materials must have the SAME Level
    2. The material Level must equal the Xyz monster's Rank
    3. Link monsters (no Level) cannot be used as Xyz material
    """
    if not materials:
        return False

    # Get levels from all materials
    levels = []
    for card in materials:
        # Link monsters have no level - cannot be Xyz material
        if card.metadata.get("link_rating"):
            return False
        level = card.metadata.get("level")
        if level is None:
            return False
        levels.append(int(level))

    # All levels must be the same
    if len(set(levels)) != 1:
        return False

    # Material Level must match Xyz Rank
    return levels[0] == xyz_rank


def extra_deck_placement_zone(state: GameState, summon_type: str) -> tuple[str, int]:
    if summon_type in {"fusion", "synchro", "xyz"}:
        open_mz = state.open_mz_indices()
        if not open_mz:
            raise IllegalActionError("No open Main Monster Zone for Extra Deck summon.")
        return "mz", open_mz[0]
    if summon_type in {"link", "pendulum"}:
        open_emz = state.open_emz_indices()
        if not open_emz:
            raise IllegalActionError("No open Extra Monster Zone for Link/Pendulum summon.")
        return "emz", open_emz[0]
    raise IllegalActionError(f"Unsupported summon type: {summon_type}")


def apply_extra_deck_summon(
    state: GameState,
    extra_index: int,
    summon_type: str,
    materials: list[tuple[str, int]],
    link_rating: int | None = None,
    min_materials: int = 2,
) -> None:
    if extra_index < 0 or extra_index >= len(state.extra):
        raise IllegalActionError("Extra Deck index out of range.")
    if not materials:
        raise IllegalActionError("Extra Deck summon requires materials.")

    material_cards = []
    for zone, index in materials:
        if zone == "mz":
            card = state.field.mz[index]
        elif zone == "emz":
            card = state.field.emz[index]
        else:
            raise IllegalActionError("Invalid material zone.")
        if card is None:
            raise IllegalActionError("Material missing from field.")
        material_cards.append(card)

    extra_card = state.extra[extra_index]

    if summon_type == "link":
        if link_rating is None:
            raise IllegalActionError("Link summon requires link_rating.")
        if not link_material_count_ok(material_cards, link_rating, min_materials):
            raise IllegalActionError("Link material count does not satisfy link rating.")
    elif summon_type == "xyz":
        xyz_rank = extra_card.metadata.get("rank")
        if xyz_rank is None:
            raise IllegalActionError("Xyz monster missing rank metadata.")
        if not xyz_materials_valid(material_cards, int(xyz_rank)):
            raise IllegalActionError("Xyz materials must all have the same Level matching the Xyz Rank.")
    else:
        if len(material_cards) < min_materials:
            raise IllegalActionError("Not enough materials for Extra Deck summon.")

    # Validate material attribute/race requirements
    if not materials_satisfy_requirements(material_cards, extra_card):
        raise IllegalActionError("Materials do not satisfy attribute/race requirements.")

    zone, idx = extra_deck_placement_zone(state, summon_type)

    for zone_name, index in materials:
        move_card_to_gy(state, zone_name, index)

    summoned = state.extra.pop(extra_index)
    summoned.properly_summoned = True
    summoned.metadata["from_extra"] = True
    if zone == "mz":
        state.field.mz[idx] = summoned
    else:
        state.field.emz[idx] = summoned


def generate_actions(state: GameState, allowed: list[str]) -> list[Action]:
    actions: list[Action] = []

    if "normal_summon" in allowed:
        open_mz = state.open_mz_indices()
        # Get monsters on field that can be tributed
        field_monsters = [(i, c) for i, c in enumerate(state.field.mz) if c is not None]
        hand_entries = list(enumerate(state.hand))
        hand_entries.sort(key=lambda x: (x[1].name.lower(), x[0]))

        for hand_index, card in hand_entries:
            level = int(card.metadata.get("level", 4))
            required = tributes_required(level)

            if required == 0:
                # No tribute needed - can summon to any open zone
                for mz_idx in open_mz:
                    actions.append(
                        Action(
                            "normal_summon",
                            {"hand_index": hand_index, "mz_index": mz_idx, "tribute_indices": []},
                        )
                    )
            elif len(field_monsters) >= required:
                # Need tributes - generate combinations
                for tribute_combo in itertools.combinations(field_monsters, required):
                    tribute_indices = [idx for idx, _ in tribute_combo]
                    # Summoned monster goes to first tribute's zone
                    mz_idx = tribute_indices[0]
                    actions.append(
                        Action(
                            "normal_summon",
                            {"hand_index": hand_index, "mz_index": mz_idx, "tribute_indices": tribute_indices},
                        )
                    )

    if "special_summon" in allowed:
        open_mz = state.open_mz_indices()
        hand_entries = list(enumerate(state.hand))
        hand_entries.sort(key=lambda x: (x[1].name.lower(), x[0]))
        for hand_index, _card in hand_entries:
            for mz_idx in open_mz:
                actions.append(
                    Action(
                        "special_summon",
                        {"hand_index": hand_index, "mz_index": mz_idx},
                    )
                )

    if "extra_deck_summon" in allowed:
        materials_pool = state.field_cards()
        if materials_pool:
            materials_pool = sorted(materials_pool, key=lambda item: (item[2].name.lower(), item[1]))
        for extra_index, extra_card in enumerate(state.extra):
            summon_type = str(extra_card.metadata.get("summon_type", "")).lower()
            if not summon_type:
                continue
            # RULES: Fusion Summons REQUIRE a card effect (Polymerization, Tract, Sequence, etc.)
            # Only Link/Xyz/Synchro can be performed as "built-in" game mechanics.
            # Fusion summons are enumerated by effect implementations, not as core actions.
            if summon_type == "fusion":
                continue
            min_materials = int(extra_card.metadata.get("min_materials", 2))
            link_rating = extra_card.metadata.get("link_rating")
            xyz_rank = extra_card.metadata.get("rank")
            action_added = False
            for count in range(min_materials, len(materials_pool) + 1):
                for combo in itertools.combinations(materials_pool, count):
                    material_cards = [card for _, _, card in combo]
                    # Validate material requirements (attribute/race)
                    if not materials_satisfy_requirements(material_cards, extra_card):
                        continue
                    # Validate Xyz Level matching
                    if summon_type == "xyz":
                        if xyz_rank is None:
                            continue  # Xyz monster missing rank metadata
                        if not xyz_materials_valid(material_cards, int(xyz_rank)):
                            continue
                    materials = [(zone, idx) for zone, idx, _ in combo]
                    actions.append(
                        Action(
                            "extra_deck_summon",
                            {
                                "extra_index": extra_index,
                                "summon_type": summon_type,
                                "materials": materials,
                                "min_materials": min_materials,
                                "link_rating": link_rating,
                            },
                        )
                    )
                    action_added = True
                    break
                if action_added:
                    break

    return actions


def apply_action(state: GameState, action: Action) -> GameState:
    new_state = state.clone()

    if action.action_type == "normal_summon":
        apply_normal_summon(new_state, **action.params)
    elif action.action_type == "special_summon":
        apply_special_summon(new_state, **action.params)
    elif action.action_type == "extra_deck_summon":
        apply_extra_deck_summon(new_state, **action.params)
    else:
        raise IllegalActionError(f"Unsupported action type: {action.action_type}")

    return new_state
