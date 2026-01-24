from __future__ import annotations

import json
from pathlib import Path

from ..errors import IllegalActionError, SimModelError
from ..rules import ActivationContext, CardType, EffectLocation, EffectType, validate_activation
from ..state import GameState
from .demo_effects import DEMO_EXTENDER_CID, DemoExtenderEffect
from .extra_deck_effects import (
    DDD_WAVE_HIGH_KING_CAESAR_CID,
    EVILSWARM_EXCITON_KNIGHT_CID,
    DDDWaveHighKingCaesarEffect,
    EvilswarmExcitonKnightEffect,
)
from .library_effects import (
    AERIAL_EATER_CID,
    A_BAO_A_QU_CID,
    BUIO_DAWNS_LIGHT_CID,
    CROSS_SHEEP_CID,
    DUKE_OF_DEMISE_CID,
    FABLED_LURRIE_CID,
    FIENDSMITH_SEQUENCE_ALT_CID,
    LUCE_DUSKS_DARK_CID,
    MUCKRAKER_CID,
    MUTINY_IN_THE_SKY_CID,
    NECROQUIP_PRINCESS_CID,
    SP_LITTLE_KNIGHT_CID,
    SNAKE_EYES_DOOMED_DRAGON_CID,
    ABaoAQuEffect,
    AerialEaterEffect,
    BuioDawnsLightEffect,
    CrossSheepEffect,
    DukeOfDemiseEffect,
    FabledLurrieEffect,
    FiendsmithSequenceAltEffect,
    LuceDusksDarkEffect,
    MuckrakerEffect,
    MutinyInTheSkyEffect,
    NecroquipPrincessEffect,
    SPLittleKnightEffect,
    SnakeEyesDoomedDragonEffect,
)
from .inert_effects import INERT_EFFECT_CIDS, InertEffect
from .fiendsmith_effects import (
    FIENDSMITH_ENGRAVER_CID,
    FIENDSMITH_LACRIMA_CID,
    FIENDSMITH_LACRIMA_CRIMSON_CID,
    FIENDSMITH_AGNUMDAY_CID,
    FIENDSMITH_DESIRAE_CID,
    FIENDSMITH_IN_PARADISE_CID,
    FIENDSMITH_KYRIE_CID,
    FIENDSMITH_REXTREMENDE_CID,
    FIENDSMITH_REQUIEM_CID,
    FIENDSMITH_SEQUENCE_CID,
    FIENDSMITH_SANCT_CID,
    FIENDSMITH_TRACT_CID,
    FiendsmithDesiraeEffect,
    FiendsmithEngraverEffect,
    FiendsmithLacrimaEffect,
    FiendsmithLacrimaCrimsonEffect,
    FiendsmithAgnumdayEffect,
    FiendsmithSequenceEffect,
    FiendsmithInParadiseEffect,
    FiendsmithKyrieEffect,
    FiendsmithRextremendeEffect,
    FiendsmithRequiemEffect,
    FiendsmithSanctEffect,
    FiendsmithTractEffect,
)
from .types import EffectAction, EffectImpl

EFFECT_REGISTRY: dict[str, EffectImpl] = {}


def _load_verified_effects() -> dict:
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "config" / "verified_effects.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {cid: entry for cid, entry in data.items() if cid != "_meta"}


VERIFIED_EFFECTS = _load_verified_effects()


def _resolve_card_location(state: GameState, action: EffectAction) -> str | None:
    params = action.params or {}
    if "field_zone" in params:
        return str(params["field_zone"])
    if "zone" in params:
        return str(params["zone"])
    source = params.get("source")
    if source in {"hand", "gy", "banished", "deck", "extra", "mz", "emz", "stz", "fz"}:
        return str(source)
    mz_index = params.get("mz_index")
    if isinstance(mz_index, int) and 0 <= mz_index < len(state.field.mz):
        card = state.field.mz[mz_index]
        if card and card.cid == action.cid:
            return "mz"
    emz_index = params.get("emz_index")
    if isinstance(emz_index, int) and 0 <= emz_index < len(state.field.emz):
        card = state.field.emz[emz_index]
        if card and card.cid == action.cid:
            return "emz"
    stz_index = params.get("stz_index")
    if isinstance(stz_index, int) and 0 <= stz_index < len(state.field.stz):
        card = state.field.stz[stz_index]
        if card and card.cid == action.cid:
            return "stz"
    fz_index = params.get("fz_index")
    if isinstance(fz_index, int) and 0 <= fz_index < len(state.field.fz):
        card = state.field.fz[fz_index]
        if card and card.cid == action.cid:
            return "fz"
    gy_index = params.get("gy_index")
    if isinstance(gy_index, int) and 0 <= gy_index < len(state.gy):
        if state.gy[gy_index].cid == action.cid:
            return "gy"
    hand_index = params.get("hand_index")
    if isinstance(hand_index, int) and 0 <= hand_index < len(state.hand):
        if state.hand[hand_index].cid == action.cid:
            return "hand"
    banished_index = params.get("banished_index")
    if isinstance(banished_index, int) and 0 <= banished_index < len(state.banished):
        if state.banished[banished_index].cid == action.cid:
            return "banished"
    # Fallback: find the first matching cid in state zones.
    if any(card.cid == action.cid for card in state.hand):
        return "hand"
    if any(card.cid == action.cid for card in state.gy):
        return "gy"
    if any(card.cid == action.cid for card in state.banished):
        return "banished"
    if any(card.cid == action.cid for card in state.deck):
        return "deck"
    if any(card.cid == action.cid for card in state.extra):
        return "extra"
    if any(card and card.cid == action.cid for card in state.field.mz):
        return "mz"
    if any(card and card.cid == action.cid for card in state.field.emz):
        return "emz"
    if any(card and card.cid == action.cid for card in state.field.stz):
        return "stz"
    if any(card and card.cid == action.cid for card in state.field.fz):
        return "fz"
    return None


def _map_effect_location(location: str | None, current: str | None) -> EffectLocation | None:
    if location == "hand":
        return EffectLocation.HAND
    if location == "gy":
        return EffectLocation.GY
    if location == "banished":
        return EffectLocation.BANISHED
    if location == "extra":
        return EffectLocation.EXTRA
    if location == "field":
        return EffectLocation.FIELD
    if location == "spell":
        # Spells can activate from hand or field; default to current if known.
        if current == "hand":
            return EffectLocation.HAND
        return EffectLocation.FIELD
    if location == "trap":
        return EffectLocation.FIELD
    if location == "field/gy":
        if current == "gy":
            return EffectLocation.GY
        return EffectLocation.FIELD
    return None


def _map_effect_type(effect_type: str | None) -> EffectType:
    if effect_type == "quick":
        return EffectType.QUICK
    if effect_type == "trigger":
        return EffectType.TRIGGER
    if effect_type == "continuous":
        return EffectType.CONTINUOUS
    return EffectType.IGNITION


def _trigger_event_occurred(state: GameState, action: EffectAction) -> bool:
    pending = list(getattr(state, "pending_triggers", []))
    if pending:
        cid = action.cid
        if f"SUMMON:{cid}" in pending or f"SENT_TO_GY:{cid}" in pending:
            return True
        if "OPP_SPECIAL_SUMMON" in pending or "OPPONENT_SS" in pending:
            return True
        return bool(state.events)
    return bool(state.events)


def _validate_effect_activation(state: GameState, action: EffectAction) -> tuple[bool, str]:
    entry = VERIFIED_EFFECTS.get(action.cid)
    if not entry:
        return False, f"Missing verified effect metadata for CID {action.cid}"

    card_type_raw = entry.get("card_type", "monster")
    card_type = CardType(card_type_raw)
    current_location = _resolve_card_location(state, action)
    effects = entry.get("effects", [])
    selected = effects[0] if effects else {}
    if current_location:
        for eff in effects:
            loc = eff.get("location")
            if loc == "field/gy" and current_location in {"gy", "mz", "emz", "stz", "fz"}:
                selected = eff
                break
            if loc == "field" and current_location in {"mz", "emz", "stz", "fz"}:
                selected = eff
                break
            if loc == current_location:
                selected = eff
                break
            if loc == "spell" and current_location in {"hand", "stz", "fz"}:
                selected = eff
                break
            if loc == "trap" and current_location in {"stz", "fz"}:
                selected = eff
                break

    effect_location = _map_effect_location(selected.get("location"), current_location)
    effect_type = _map_effect_type(selected.get("effect_type"))
    if not effect_location or not current_location:
        return False, "Unable to resolve effect activation location"

    is_your_turn = "OPP_TURN" not in state.events
    is_main_phase = "Main Phase" in state.phase
    is_set = current_location in {"stz", "fz"}
    turns_since_set = 1 if is_set else 0
    trigger_event_occurred = _trigger_event_occurred(state, action)

    ctx = ActivationContext(
        card_type=card_type,
        effect_location=effect_location,
        effect_type=effect_type,
        current_location=current_location,
        is_set=is_set,
        turns_since_set=turns_since_set,
        trigger_event_occurred=trigger_event_occurred,
        is_your_turn=is_your_turn,
        is_main_phase=is_main_phase,
    )
    return validate_activation(ctx)


def register_effect(cid: str, effect: EffectImpl) -> None:
    EFFECT_REGISTRY[cid] = effect


def enumerate_effect_actions(state: GameState) -> list[EffectAction]:
    cids = set()
    for card in state.hand:
        cids.add(card.cid)
    for card in state.field.mz:
        if card:
            cids.add(card.cid)
    for card in state.field.emz:
        if card:
            cids.add(card.cid)
    for card in state.gy:
        cids.add(card.cid)

    actions: list[EffectAction] = []
    for cid in sorted(cids):
        effect = EFFECT_REGISTRY.get(cid)
        if not effect:
            continue
        effect_actions = effect.enumerate_actions(state)
        for action in effect_actions:
            if action.cid not in EFFECT_REGISTRY:
                raise SimModelError(f"Unregistered CID in action: {action.cid}")
            actions.append(action)

    actions.sort(key=lambda action: action.sort_key)
    return actions


def apply_effect_action(state: GameState, action: EffectAction) -> GameState:
    is_ok, reason = _validate_effect_activation(state, action)
    if not is_ok:
        raise IllegalActionError(reason)
    effect = EFFECT_REGISTRY.get(action.cid)
    if not effect:
        raise SimModelError(f"No effect registered for CID {action.cid}")
    return effect.apply(state, action)


register_effect(DEMO_EXTENDER_CID, DemoExtenderEffect())
register_effect(EVILSWARM_EXCITON_KNIGHT_CID, EvilswarmExcitonKnightEffect())
register_effect(DDD_WAVE_HIGH_KING_CAESAR_CID, DDDWaveHighKingCaesarEffect())
register_effect(CROSS_SHEEP_CID, CrossSheepEffect())
register_effect(MUCKRAKER_CID, MuckrakerEffect())
register_effect(SP_LITTLE_KNIGHT_CID, SPLittleKnightEffect())
register_effect(FIENDSMITH_SEQUENCE_ALT_CID, FiendsmithSequenceAltEffect())
register_effect(DUKE_OF_DEMISE_CID, DukeOfDemiseEffect())
register_effect(NECROQUIP_PRINCESS_CID, NecroquipPrincessEffect())
register_effect(AERIAL_EATER_CID, AerialEaterEffect())
register_effect(SNAKE_EYES_DOOMED_DRAGON_CID, SnakeEyesDoomedDragonEffect())
register_effect(A_BAO_A_QU_CID, ABaoAQuEffect())
register_effect(BUIO_DAWNS_LIGHT_CID, BuioDawnsLightEffect())
register_effect(LUCE_DUSKS_DARK_CID, LuceDusksDarkEffect())
register_effect(MUTINY_IN_THE_SKY_CID, MutinyInTheSkyEffect())
register_effect(FABLED_LURRIE_CID, FabledLurrieEffect())
for cid in sorted(INERT_EFFECT_CIDS.keys()):
    register_effect(cid, InertEffect())
register_effect(FIENDSMITH_ENGRAVER_CID, FiendsmithEngraverEffect())
register_effect(FIENDSMITH_LACRIMA_CID, FiendsmithLacrimaEffect())
register_effect(FIENDSMITH_TRACT_CID, FiendsmithTractEffect())
register_effect(FIENDSMITH_SANCT_CID, FiendsmithSanctEffect())
register_effect(FIENDSMITH_REQUIEM_CID, FiendsmithRequiemEffect())
register_effect(FIENDSMITH_LACRIMA_CRIMSON_CID, FiendsmithLacrimaCrimsonEffect())
register_effect(FIENDSMITH_AGNUMDAY_CID, FiendsmithAgnumdayEffect())
register_effect(FIENDSMITH_IN_PARADISE_CID, FiendsmithInParadiseEffect())
register_effect(FIENDSMITH_KYRIE_CID, FiendsmithKyrieEffect())
register_effect(FIENDSMITH_DESIRAE_CID, FiendsmithDesiraeEffect())
register_effect(FIENDSMITH_SEQUENCE_CID, FiendsmithSequenceEffect())
register_effect(FIENDSMITH_REXTREMENDE_CID, FiendsmithRextremendeEffect())
