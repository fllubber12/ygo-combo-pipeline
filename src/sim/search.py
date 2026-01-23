from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass
from typing import Any

from combos.endboard_evaluator import evaluate_endboard

from .actions import Action, apply_action, generate_actions
from .convert import game_state_to_endboard_snapshot
from .errors import IllegalActionError
from .effects.registry import apply_effect_action, enumerate_effect_actions
from .effects.types import EffectAction
from .effects.fiendsmith_effects import (
    FIENDSMITH_DESIRAE_CID as DESIRAE_CID,
    FIENDSMITH_REQUIEM_CID,
    is_light_fiend_card,
    is_link_monster,
)
from .effects.library_effects import (
    A_BAO_A_QU_CID,
    AERIAL_EATER_CID,
    BUIO_DAWNS_LIGHT_CID,
    FABLED_LURRIE_CID,
    FIENDSMITH_SEQUENCE_ALT_CID,
    LUCE_DUSKS_DARK_CID,
    MUTINY_IN_THE_SKY_CID,
)
from .state import GameState

EQUIP_EFFECT_IDS = {
    "equip_sequence_to_fiend",
    "equip_requiem_to_fiend",
    "sequence_20226_equip",
}


@dataclass
class SearchResult:
    actions: list[Action | EffectAction]
    final_state: GameState
    evaluation: dict[str, Any]


def score_key(evaluation: dict[str, Any]) -> tuple[int, int, int]:
    has_s, has_a, count_b = evaluation["rank_key"]
    return (int(has_s), int(has_a), int(count_b))


def _setup_width_for_beam(beam_width: int) -> int:
    # Reserve some beam slots for “setup” states (non-A) so we don’t prune staging lines.
    if beam_width <= 1:
        return 0
    return min(max(2, beam_width // 4), beam_width - 1)


def _select_diversified_beam(
    candidates: list[tuple["GameState", list["Action | EffectAction"], dict[str, Any]]],
    beam_width: int,
    setup_width: int,
) -> list[tuple["GameState", list["Action | EffectAction"]]]:
    # candidates MUST already be sorted best→worst using (score_key, state_hash) desc.
    if beam_width <= 0:
        return []
    if setup_width <= 0:
        return [(st, acts) for st, acts, _ev in candidates[:beam_width]]

    a_target = max(0, beam_width - setup_width)
    selected_a: list[tuple["GameState", list["Action | EffectAction"]]] = []
    selected_setup: list[tuple["GameState", list["Action | EffectAction"]]] = []

    for st, acts, ev in candidates:
        _count_s, count_a, _count_b = ev["rank_key"]
        if count_a > 0 and len(selected_a) < a_target:
            selected_a.append((st, acts))
        elif count_a == 0 and len(selected_setup) < setup_width:
            selected_setup.append((st, acts))
        if len(selected_a) + len(selected_setup) >= beam_width:
            break

    # Fill any remainder (rare) from the best remaining candidates, skipping duplicates.
    if len(selected_a) + len(selected_setup) < beam_width:
        seen = {state_hash(st) for st, _ in (selected_a + selected_setup)}
        for st, acts, _ev in candidates:
            key = state_hash(st)
            if key in seen:
                continue
            selected_a.append((st, acts))
            seen.add(key)
            if len(selected_a) + len(selected_setup) >= beam_width:
                break

    return selected_a + selected_setup


def state_hash(state: GameState) -> tuple:
    def from_extra_flag(card) -> bool:
        if card.metadata.get("from_extra"):
            return True
        try:
            return int(card.metadata.get("link_rating", 0)) > 0
        except (TypeError, ValueError):
            return False

    def zone_names(cards):
        return tuple(
            (card.cid, card.properly_summoned, from_extra_flag(card))
            for card in cards
        )

    def freeze(value):
        if isinstance(value, dict):
            return tuple(sorted((key, freeze(val)) for key, val in value.items()))
        if isinstance(value, list):
            return tuple(freeze(item) for item in value)
        if isinstance(value, set):
            return tuple(sorted(freeze(item) for item in value))
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    field_mz = tuple(
        (
            card.cid,
            card.properly_summoned,
            from_extra_flag(card),
            tuple(sorted(eq.cid for eq in card.equipped)),
        )
        if card
        else ("", False, False, ())
        for card in state.field.mz
    )
    field_emz = tuple(
        (
            card.cid,
            card.properly_summoned,
            from_extra_flag(card),
            tuple(sorted(eq.cid for eq in card.equipped)),
        )
        if card
        else ("", False, False, ())
        for card in state.field.emz
    )

    return (
        zone_names(state.deck),
        zone_names(state.hand),
        zone_names(state.gy),
        zone_names(state.banished),
        zone_names(state.extra),
        field_mz,
        field_emz,
        state.turn_number,
        state.phase,
        state.normal_summon_set_used,
        freeze(state.opt_used),
        freeze(state.restrictions),
        freeze(state.events),
        freeze(state.last_moved_to_gy),
    )


def core_action_sort_key(action: Action) -> tuple:
    items = []
    for key in sorted(action.params):
        value = action.params[key]
        if isinstance(value, list):
            value = tuple(value)
        items.append((key, value))
    return (action.action_type, tuple(items))


def _is_main_phase(state: GameState) -> bool:
    return str(state.phase).lower().startswith("main")


def _is_fiend_card(card) -> bool:
    race = str(card.metadata.get("race", "")).upper()
    if "FIEND" in race:
        return True
    return is_light_fiend_card(card)


def _derive_last_moved_to_gy(prev_state: GameState, new_state: GameState) -> list[str]:
    prev_counts = Counter(card.cid for card in prev_state.gy)
    new_counts = Counter(card.cid for card in new_state.gy)
    added: list[str] = []
    for cid in sorted(set(prev_counts) | set(new_counts)):
        diff = new_counts[cid] - prev_counts[cid]
        if diff > 0:
            added.extend([cid] * diff)
    return added


def _add_derived_events(state: GameState) -> GameState:
    derived: list[str] = []
    events = list(state.events)

    if (
        "MUTINY_FUSION_TRIGGER" not in events
        and not state.opt_used.get(f"{MUTINY_IN_THE_SKY_CID}:e1")
        and _is_main_phase(state)
    ):
        if any(card.cid == MUTINY_IN_THE_SKY_CID for card in state.hand):
            if state.open_mz_indices():
                if any(card.cid == LUCE_DUSKS_DARK_CID for card in state.extra):
                    if any(card.cid == AERIAL_EATER_CID for card in state.gy) and any(
                        card.cid == BUIO_DAWNS_LIGHT_CID for card in state.gy
                    ):
                        derived.append("MUTINY_FUSION_TRIGGER")

    if (
        "BUIO_TRIGGER" not in events
        and not state.opt_used.get(f"{BUIO_DAWNS_LIGHT_CID}:e1")
        and _is_main_phase(state)
    ):
        if any(card.cid == BUIO_DAWNS_LIGHT_CID for card in state.hand):
            if state.open_mz_indices() and any(_is_fiend_card(card) for card in state.field.mz if card):
                derived.append("BUIO_TRIGGER")

    if (
        "LUCE_TRIGGER" not in events
        and not state.opt_used.get(f"{LUCE_DUSKS_DARK_CID}:e1")
        and _is_main_phase(state)
    ):
        luce_entries = [
            (zone, idx, card)
            for zone, idx, card in state.field_cards()
            if card.cid == LUCE_DUSKS_DARK_CID
            and card.properly_summoned
            and str(card.metadata.get("summon_type", "")).lower() == "fusion"
        ]
        if luce_entries and any(_is_fiend_card(card) or "FAIRY" in str(card.metadata.get("race", "")).upper() for card in state.deck):
            other_field = False
            for zone, idx, card in state.field_cards():
                if card.cid != LUCE_DUSKS_DARK_CID:
                    other_field = True
                    break
            if not other_field:
                for zone_list in (state.field.stz, state.field.fz):
                    if any(zone_list):
                        other_field = True
                        break
            if other_field:
                derived.append("LUCE_TRIGGER")

    # High-value missing derived trigger: ABAO_TRIGGER.
    # This unlocks A Bao A Qu's discard/banish/revive line in batch search without manual event injection.
    if (
        "ABAO_TRIGGER" not in events
        and not state.opt_used.get(f"{A_BAO_A_QU_CID}:e1")
        and _is_main_phase(state)
    ):
        abao_on_field = any(
            card.cid == A_BAO_A_QU_CID
            and card.properly_summoned
            and str(card.metadata.get("summon_type", "")).lower() == "link"
            for _zone, _idx, card in state.field_cards()
        )
        has_ld_in_gy = any(
            str(card.metadata.get("attribute", "")).upper() in {"LIGHT", "DARK"}
            for card in state.gy
        )
        if abao_on_field and state.hand and state.open_mz_indices() and has_ld_in_gy:
            derived.append("ABAO_TRIGGER")

    if (
        "SEQUENCE_20226_EQUIP" not in events
        and not state.opt_used.get(f"{FIENDSMITH_SEQUENCE_ALT_CID}:e1")
    ):
        has_sequence = any(
            card.cid == FIENDSMITH_SEQUENCE_ALT_CID for _zone, _idx, card in state.field_cards()
        )
        if has_sequence:
            for card in state.field.mz:
                if not card:
                    continue
                if not is_light_fiend_card(card):
                    continue
                if is_link_monster(card):
                    continue
                derived.append("SEQUENCE_20226_EQUIP")
                break

    if (
        "BUIO_GY_TRIGGER" not in events
        and not state.opt_used.get(f"{BUIO_DAWNS_LIGHT_CID}:e2")
        and BUIO_DAWNS_LIGHT_CID in state.last_moved_to_gy
    ):
        if any(card.cid == BUIO_DAWNS_LIGHT_CID for card in state.gy):
            derived.append("BUIO_GY_TRIGGER")

    if (
        "MUTINY_GY_TRIGGER" not in events
        and not state.opt_used.get(f"{MUTINY_IN_THE_SKY_CID}:e2")
        and MUTINY_IN_THE_SKY_CID in state.last_moved_to_gy
    ):
        if any(card.cid == MUTINY_IN_THE_SKY_CID for card in state.gy):
            derived.append("MUTINY_GY_TRIGGER")

    # Fabled Lurrie: If discarded to GY, SS itself (NOT OPT)
    # Trigger when Lurrie is in last_moved_to_gy (indicating it was just sent to GY)
    if (
        "LURRIE_DISCARD_TRIGGER" not in events
        and FABLED_LURRIE_CID in state.last_moved_to_gy
    ):
        if any(card.cid == FABLED_LURRIE_CID for card in state.gy):
            if state.open_mz_indices():
                derived.append("LURRIE_DISCARD_TRIGGER")

    if not derived:
        return state

    new_state = state.clone()
    for evt in sorted(derived):
        if evt not in events:
            events.append(evt)
    new_state.events = events
    return new_state


def _enumerate_equip_source_link_summons(state: GameState) -> list[Action]:
    # Only Link summon Requiem/Sequence, and avoid consuming Desirae as material.
    equip_source_cids = {FIENDSMITH_REQUIEM_CID, FIENDSMITH_SEQUENCE_ALT_CID}

    # Need an open EMZ for Link summons.
    if not state.open_emz_indices():
        return []

    material_pool = [
        (zone, idx, card)
        for zone, idx, card in state.field_cards()
        if card.cid != DESIRAE_CID
    ]
    if not material_pool:
        return []

    actions: list[Action] = []
    for extra_index, card in enumerate(state.extra):
        if card.cid not in equip_source_cids:
            continue
        summon_type = str(card.metadata.get("summon_type", "")).lower()
        if summon_type != "link":
            continue
        try:
            link_rating = int(card.metadata.get("link_rating"))
        except (TypeError, ValueError):
            continue
        try:
            min_materials = int(card.metadata.get("min_materials"))
        except (TypeError, ValueError):
            min_materials = 1 if link_rating == 1 else 2
        if len(material_pool) < min_materials:
            continue

        # Explore small combos deterministically (min_materials and min_materials+1 only).
        max_count = min(len(material_pool), min_materials + 1)
        for count in range(min_materials, max_count + 1):
            for combo in itertools.combinations(material_pool, count):
                materials = [(zone, idx) for zone, idx, _ in combo]
                actions.append(
                    Action(
                        "extra_deck_summon",
                        {
                            "extra_index": extra_index,
                            "summon_type": "link",
                            "materials": materials,
                            "min_materials": min_materials,
                            "link_rating": link_rating,
                        },
                    )
                )

    # Deterministic order: by cid then materials tuple
    actions.sort(key=lambda a: (state.extra[a.params["extra_index"]].cid, tuple(a.params["materials"])))
    return actions


def _enumerate_xyz_summons(state: GameState) -> list[Action]:
    """Enumerate Xyz summons for S-tier targets like Caesar, avoiding Desirae as material."""
    from .actions import xyz_materials_valid

    # Need an open MZ for Xyz summons
    open_mz = state.open_mz_indices()
    if not open_mz:
        return []

    # Collect field monsters that can be Xyz material (exclude Desirae, exclude Links)
    material_pool = []
    for zone, idx, card in state.field_cards():
        if card.cid == DESIRAE_CID:
            continue
        if is_link_monster(card):
            continue  # Links have no Level
        level = card.metadata.get("level")
        if level is None:
            continue
        material_pool.append((zone, idx, card, int(level)))

    if len(material_pool) < 2:
        return []

    actions: list[Action] = []
    for extra_index, extra_card in enumerate(state.extra):
        summon_type = str(extra_card.metadata.get("summon_type", "")).lower()
        if summon_type != "xyz":
            continue
        xyz_rank = extra_card.metadata.get("rank")
        if xyz_rank is None:
            continue
        xyz_rank = int(xyz_rank)
        min_materials = int(extra_card.metadata.get("min_materials", 2))

        # Find materials with matching Level
        matching_materials = [
            (zone, idx, card) for zone, idx, card, level in material_pool if level == xyz_rank
        ]
        if len(matching_materials) < min_materials:
            continue

        # Generate combinations of exactly min_materials
        for combo in itertools.combinations(matching_materials, min_materials):
            materials = [(zone, idx) for zone, idx, _ in combo]
            material_cards = [card for _, _, card in combo]
            if not xyz_materials_valid(material_cards, xyz_rank):
                continue
            actions.append(
                Action(
                    "extra_deck_summon",
                    {
                        "extra_index": extra_index,
                        "summon_type": "xyz",
                        "materials": materials,
                        "min_materials": min_materials,
                        "rank": xyz_rank,
                    },
                )
            )

    actions.sort(key=lambda a: (state.extra[a.params["extra_index"]].cid, tuple(a.params["materials"])))
    return actions


def _count_non_desirae_field_monsters(state: GameState) -> int:
    count = 0
    for _zone, _idx, card in state.field_cards():
        if not card:
            continue
        if card.cid == DESIRAE_CID:
            continue
        count += 1
    return count


def _desirae_present_and_eligible(state: GameState) -> bool:
    for _zone, _idx, card in state.field_cards():
        if card.cid != DESIRAE_CID:
            continue
        if not is_light_fiend_card(card):
            return False
        if is_link_monster(card):
            return False
        return True
    return False


def _enumerate_body_maker_effect_actions(
    state: GameState,
    max_candidates: int = 30,
) -> list[EffectAction]:
    """
    Deterministically select EFFECT actions that add a non-Desirae monster to the field.
    This is intentionally narrow: we only keep actions whose application increases the
    count of non-Desirae field monsters while preserving Desirae eligibility.
    """
    base_count = _count_non_desirae_field_monsters(state)

    effect_actions = enumerate_effect_actions(state)
    effect_actions = sorted(effect_actions, key=lambda ea: ea.sort_key)

    out: list[EffectAction] = []
    for ea in effect_actions[:max_candidates]:
        if ea.effect_id in EQUIP_EFFECT_IDS:
            continue
        try:
            new_state = apply_effect_action(state, ea)
        except IllegalActionError:
            continue

        if not _desirae_present_and_eligible(new_state):
            continue

        new_count = _count_non_desirae_field_monsters(new_state)
        if new_count > base_count:
            out.append(ea)

        if len(out) >= 10:
            break

    return out


def _equip_source_closure_pass(
    state: GameState,
    actions: list[Action | EffectAction],
    evaluation: dict[str, Any],
    prefer_longest: bool,
    depth: int = 3,
    beam_width: int = 20,
) -> SearchResult:
    count_s, count_a, _count_b = evaluation["rank_key"]
    if count_a == 0 and count_s == 0:
        return SearchResult(actions=actions, final_state=state, evaluation=evaluation)

    best_result = SearchResult(actions=actions, final_state=state, evaluation=evaluation)
    seen = {state_hash(state)}
    beam = [(state, actions)]

    for _depth in range(depth):
        candidates = []
        for current_state, current_actions in beam:
            current_state = _add_derived_events(current_state)

            # 1) Equip actions (if already possible)
            equip_effects = [
                ea for ea in enumerate_effect_actions(current_state)
                if ea.effect_id in EQUIP_EFFECT_IDS
            ]
            equip_effects = sorted(equip_effects, key=lambda ea: ea.sort_key)

            # 2) Targeted equip-source Link summons (Requiem/Sequence) avoiding Desirae mats
            link_summons = _enumerate_equip_source_link_summons(current_state)

            # 2.5) Xyz summons for S-tier targets like Caesar
            xyz_summons = _enumerate_xyz_summons(current_state)

            # 2.6) Body-maker EFFECT actions (revive/special) to create the second non-Desirae material
            body_maker_effects = _enumerate_body_maker_effect_actions(current_state)

            # 3) Minimal “body maker”: summon a FIEND from hand into the first open MZ
            summon_actions: list[Action] = []
            open_mz = current_state.open_mz_indices()
            if open_mz and current_state.hand:
                mz_index = open_mz[0]

                # deterministic: by (name, index)
                hand_entries = [
                    (i, c) for i, c in enumerate(current_state.hand) if _is_fiend_card(c)
                ]
                hand_entries.sort(key=lambda x: (x[1].name.lower(), x[0]))
                for hand_index, card in hand_entries[:3]:
                    # RULES: Special Summons require card effects - cannot do generic special_summon
                    # Only Normal Summon is a built-in mechanic (respecting tribute requirements)
                    level = int(card.metadata.get("level", 4))
                    tributes_needed = 0 if level <= 4 else (1 if level <= 6 else 2)
                    field_monsters = [i for i, c in enumerate(current_state.field.mz) if c is not None]
                    if tributes_needed == 0:
                        summon_actions.append(Action("normal_summon", {"hand_index": hand_index, "mz_index": mz_index, "tribute_indices": []}))

            combined_actions: list[Action | EffectAction] = []
            # Prefer: equip now > stage equip source > xyz for S-tier > add body
            combined_actions.extend(equip_effects)
            combined_actions.extend(link_summons)
            combined_actions.extend(xyz_summons)
            combined_actions.extend(body_maker_effects)
            combined_actions.extend(summon_actions)

            for action in combined_actions:
                try:
                    if isinstance(action, Action):
                        new_state = apply_action(current_state, action)
                    else:
                        new_state = apply_effect_action(current_state, action)
                except IllegalActionError:
                    continue

                new_state.last_moved_to_gy = _derive_last_moved_to_gy(current_state, new_state)
                new_state = _add_derived_events(new_state)

                key = state_hash(new_state)
                if key in seen:
                    continue
                seen.add(key)

                snapshot = game_state_to_endboard_snapshot(new_state)
                new_eval = evaluate_endboard(snapshot)
                candidates.append((new_state, current_actions + [action], new_eval))

        if not candidates:
            break

        candidates.sort(
            key=lambda item: (score_key(item[2]), state_hash(item[0])),
            reverse=True,
        )
        setup_width = _setup_width_for_beam(beam_width)
        beam = _select_diversified_beam(candidates, beam_width=beam_width, setup_width=setup_width)

        best_candidate = candidates[0]
        if prefer_longest:
            if len(best_candidate[1]) >= len(best_result.actions):
                best_result = SearchResult(best_candidate[1], best_candidate[0], best_candidate[2])
        else:
            if score_key(best_candidate[2]) >= score_key(best_result.evaluation):
                best_result = SearchResult(best_candidate[1], best_candidate[0], best_candidate[2])

        # Note: No early exit - continue searching for higher S counts (S=2 > S=1)

    return best_result


def _equip_closure_pass(
    state: GameState,
    actions: list[Action | EffectAction],
    evaluation: dict[str, Any],
    prefer_longest: bool,
    depth: int = 2,
    beam_width: int = 10,
) -> SearchResult:
    best_result = SearchResult(actions=actions, final_state=state, evaluation=evaluation)
    seen = {state_hash(state)}
    beam = [(state, actions)]

    for _depth in range(depth):
        candidates = []
        for current_state, current_actions in beam:
            current_state = _add_derived_events(current_state)
            effect_actions = [
                action
                for action in enumerate_effect_actions(current_state)
                if action.effect_id in EQUIP_EFFECT_IDS
            ]
            effect_actions = sorted(effect_actions, key=lambda action: action.sort_key)
            for action in effect_actions:
                try:
                    new_state = apply_effect_action(current_state, action)
                except IllegalActionError:
                    continue
                new_state.last_moved_to_gy = _derive_last_moved_to_gy(current_state, new_state)
                new_state = _add_derived_events(new_state)
                key = state_hash(new_state)
                if key in seen:
                    continue
                seen.add(key)
                snapshot = game_state_to_endboard_snapshot(new_state)
                evaluation = evaluate_endboard(snapshot)
                candidates.append((new_state, current_actions + [action], evaluation))

        if not candidates:
            break

        candidates.sort(
            key=lambda item: (score_key(item[2]), state_hash(item[0])),
            reverse=True,
        )
        setup_width = _setup_width_for_beam(beam_width)
        beam = _select_diversified_beam(candidates, beam_width=beam_width, setup_width=setup_width)

        best_candidate = candidates[0]
        if prefer_longest:
            if len(best_candidate[1]) >= len(best_result.actions):
                best_result = SearchResult(
                    actions=best_candidate[1],
                    final_state=best_candidate[0],
                    evaluation=best_candidate[2],
                )
        else:
            if score_key(best_candidate[2]) >= score_key(best_result.evaluation):
                best_result = SearchResult(
                    actions=best_candidate[1],
                    final_state=best_candidate[0],
                    evaluation=best_candidate[2],
                )

    return best_result


def search_best_line(
    state: GameState,
    max_depth: int = 2,
    beam_width: int = 10,
    allowed_actions: list[str] | None = None,
    prefer_longest: bool = False,
) -> SearchResult:
    if allowed_actions is None:
        # Note: special_summon removed - in Yu-Gi-Oh, special summons require
        # specific card effects, not a generic action from hand
        allowed_actions = ["normal_summon", "extra_deck_summon"]

    state = _add_derived_events(state)
    initial_snapshot = game_state_to_endboard_snapshot(state)
    best_eval = evaluate_endboard(initial_snapshot)
    best_result = SearchResult(actions=[], final_state=state, evaluation=best_eval)

    seen = {state_hash(state)}
    beam = [(state, [])]

    for _depth in range(max_depth):
        candidates = []
        for current_state, actions in beam:
            current_state = _add_derived_events(current_state)
            core_actions = sorted(
                generate_actions(current_state, allowed_actions),
                key=core_action_sort_key,
            )
            effect_actions = enumerate_effect_actions(current_state)
            combined_actions: list[Action | EffectAction] = core_actions + effect_actions
            for action in combined_actions:
                try:
                    if isinstance(action, Action):
                        new_state = apply_action(current_state, action)
                    else:
                        new_state = apply_effect_action(current_state, action)
                except IllegalActionError:
                    continue
                new_state.last_moved_to_gy = _derive_last_moved_to_gy(current_state, new_state)
                new_state = _add_derived_events(new_state)
                key = state_hash(new_state)
                if key in seen:
                    continue
                seen.add(key)
                snapshot = game_state_to_endboard_snapshot(new_state)
                evaluation = evaluate_endboard(snapshot)
                candidates.append((new_state, actions + [action], evaluation))

        if not candidates:
            break

        candidates.sort(
            key=lambda item: (score_key(item[2]), state_hash(item[0])),
            reverse=True,
        )
        setup_width = _setup_width_for_beam(beam_width)
        beam = _select_diversified_beam(candidates, beam_width=beam_width, setup_width=setup_width)

        best_candidate = candidates[0]
        if prefer_longest:
            if len(best_candidate[1]) >= len(best_result.actions):
                best_result = SearchResult(
                    actions=best_candidate[1],
                    final_state=best_candidate[0],
                    evaluation=best_candidate[2],
                )
        else:
            if score_key(best_candidate[2]) >= score_key(best_result.evaluation):
                best_result = SearchResult(
                    actions=best_candidate[1],
                    final_state=best_candidate[0],
                    evaluation=best_candidate[2],
                )

    best_result = _equip_source_closure_pass(
        best_result.final_state,
        best_result.actions,
        best_result.evaluation,
        prefer_longest,
        depth=3,
        beam_width=20,
    )
    best_result = _equip_closure_pass(
        best_result.final_state,
        best_result.actions,
        best_result.evaluation,
        prefer_longest,
    )
    return best_result
