from __future__ import annotations

from ..errors import SimModelError
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
