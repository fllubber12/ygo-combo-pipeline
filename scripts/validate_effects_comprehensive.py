#!/usr/bin/env python3
"""
Comprehensive effect validation framework.

For EVERY effect in verified_effects.json, generate and run tests for:
1. LEGAL activation - correct setup, should succeed
2. WRONG LOCATION - card in wrong zone, should fail
3. MISSING COST - cost not payable, should fail
4. INVALID TARGET - no valid targets, should fail
5. OPT VIOLATION - already used this turn, should fail
6. CONDITION NOT MET - activation condition not satisfied, should fail
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from sim.effects.registry import apply_effect_action, enumerate_effect_actions  # noqa: E402
from sim.errors import IllegalActionError, SimModelError  # noqa: E402
from sim.state import GameState  # noqa: E402

# CID constants for card-specific setups
FIENDSMITH_ENGRAVER_CID = "20196"
FIENDSMITH_TRACT_CID = "20240"
FIENDSMITH_SANCT_CID = "20241"
FIENDSMITH_IN_PARADISE_CID = "20251"
FIENDSMITH_KYRIE_CID = "20816"
FIENDSMITH_LACRIMA_CID = "20214"
FIENDSMITH_DESIRAE_CID = "20215"
FIENDSMITH_REQUIEM_CID = "20225"
FIENDSMITH_SEQUENCE_CID = "20238"
FIENDSMITH_SEQUENCE_ALT_CID = "20226"
FIENDSMITH_AGNUMDAY_CID = "20521"
FIENDSMITH_REXTREMENDE_CID = "20774"
LACRIMA_CRIMSON_TEARS_CID = "20490"
EVILSWARM_EXCITON_KNIGHT_CID = "10942"
DDD_WAVE_HIGH_KING_CAESAR_CID = "13081"
CROSS_SHEEP_CID = "14856"
MUCKRAKER_CID = "17806"
SP_LITTLE_KNIGHT_CID = "19188"
DUKE_OF_DEMISE_CID = "20389"
NECROQUIP_PRINCESS_CID = "20423"
AERIAL_EATER_CID = "20427"
SNAKE_EYES_DOOMED_DRAGON_CID = "20772"
A_BAO_A_QU_CID = "20786"
BUIO_DAWNS_LIGHT_CID = "21624"
LUCE_DUSKS_DARK_CID = "21625"
MUTINY_IN_THE_SKY_CID = "21626"

# Fiendsmith S/T CIDs (search targets for Engraver e1)
FIENDSMITH_ST_CIDS = {FIENDSMITH_TRACT_CID, FIENDSMITH_SANCT_CID, FIENDSMITH_IN_PARADISE_CID, FIENDSMITH_KYRIE_CID}

# Light Fiend monster CIDs
LIGHT_FIEND_MONSTER_CIDS = {
    FIENDSMITH_ENGRAVER_CID, FIENDSMITH_LACRIMA_CID, FIENDSMITH_DESIRAE_CID,
    FIENDSMITH_REQUIEM_CID, FIENDSMITH_SEQUENCE_CID, FIENDSMITH_SEQUENCE_ALT_CID,
    FIENDSMITH_AGNUMDAY_CID, FIENDSMITH_REXTREMENDE_CID, LACRIMA_CRIMSON_TEARS_CID,
}

# Fiendsmith Link CIDs (for Lacrima CT e2)
FIENDSMITH_LINK_CIDS = {FIENDSMITH_REQUIEM_CID, FIENDSMITH_SEQUENCE_CID, FIENDSMITH_SEQUENCE_ALT_CID, FIENDSMITH_AGNUMDAY_CID}

# Fiendsmith Fusion CIDs
FIENDSMITH_FUSION_CIDS = {FIENDSMITH_LACRIMA_CID, FIENDSMITH_DESIRAE_CID, FIENDSMITH_REXTREMENDE_CID}

# Fiendsmith Equip CIDs (Link monsters that can equip)
FIENDSMITH_EQUIP_CIDS = {FIENDSMITH_REQUIEM_CID, FIENDSMITH_SEQUENCE_CID, FIENDSMITH_SEQUENCE_ALT_CID, FIENDSMITH_AGNUMDAY_CID}

# ============================================================================
# Effect ID mapping: verified_effects.json effect_id -> implementation effect_id
# Maps (cid, verified_id) -> list of implementation effect_ids
# ============================================================================
EFFECT_ID_MAPPING: dict[tuple[str, str], list[str]] = {
    # Fiendsmith Engraver (20196)
    (FIENDSMITH_ENGRAVER_CID, "e1"): ["discard_search_fiendsmith_st"],
    (FIENDSMITH_ENGRAVER_CID, "e2"): ["send_equip_and_monster_to_gy"],
    (FIENDSMITH_ENGRAVER_CID, "e3"): ["gy_shuffle_light_fiend_then_ss_self"],
    # Evilswarm Exciton Knight (10942)
    (EVILSWARM_EXCITON_KNIGHT_CID, "e1"): ["exciton_knight_wipe"],
    # D/D/D Wave High King Caesar (13081)
    (DDD_WAVE_HIGH_KING_CAESAR_CID, "e1"): ["caesar_negate_send"],
    (DDD_WAVE_HIGH_KING_CAESAR_CID, "e2"): ["caesar_gy_search_dark_contract"],
    # Cross-Sheep (14856)
    (CROSS_SHEEP_CID, "e1"): ["cross_sheep_revive", "cross_sheep_ritual_draw_discard", "cross_sheep_synchro_boost", "cross_sheep_xyz_debuff"],
    # Muckraker (17806)
    (MUCKRAKER_CID, "e0"): ["muckraker_no_link_material"],
    (MUCKRAKER_CID, "e1"): ["muckraker_replace_destruction"],
    (MUCKRAKER_CID, "e2"): ["muckraker_discard_revive"],
    # S:P Little Knight (19188)
    (SP_LITTLE_KNIGHT_CID, "e1"): ["sp_little_knight_banish"],
    (SP_LITTLE_KNIGHT_CID, "e2"): ["sp_little_knight_banish_pair"],
    # Fiendsmith's Lacrima (20214)
    (FIENDSMITH_LACRIMA_CID, "e1"): ["lacrima_atk_reduction"],
    (FIENDSMITH_LACRIMA_CID, "e2"): ["lacrima_fusion_recover_light_fiend"],
    (FIENDSMITH_LACRIMA_CID, "e3"): ["lacrima_gy_burn"],
    # Fiendsmith's Desirae (20215)
    (FIENDSMITH_DESIRAE_CID, "e1"): ["desirae_negate"],
    (FIENDSMITH_DESIRAE_CID, "e2"): ["gy_desirae_send_field"],
    # Fiendsmith's Requiem (20225)
    (FIENDSMITH_REQUIEM_CID, "e0"): [],  # Restriction effect, not activatable
    (FIENDSMITH_REQUIEM_CID, "e1"): ["tribute_self_ss_fiendsmith"],
    (FIENDSMITH_REQUIEM_CID, "e2"): ["equip_requiem_to_fiend"],
    # Fiendsmith's Sequence (20238)
    (FIENDSMITH_SEQUENCE_CID, "e1"): ["sequence_shuffle_fuse_fiend", "sequence_shuffle_fuse_rextremende", "sequence_shuffle_fuse_lacrima"],
    (FIENDSMITH_SEQUENCE_CID, "e2"): ["equip_sequence_to_fiend"],
    # Fiendsmith's Sequence alt (20226)
    (FIENDSMITH_SEQUENCE_ALT_CID, "e1"): ["sequence_20226_shuffle_fuse"],
    (FIENDSMITH_SEQUENCE_ALT_CID, "e2"): ["sequence_20226_equip"],
    # Fiendsmith's Tract (20240)
    (FIENDSMITH_TRACT_CID, "e1"): ["search_light_fiend_then_discard"],
    (FIENDSMITH_TRACT_CID, "e2"): ["gy_banish_fuse_fiendsmith"],
    # Fiendsmith's Sanct (20241)
    (FIENDSMITH_SANCT_CID, "e1"): ["activate_sanct_token"],
    (FIENDSMITH_SANCT_CID, "e2"): ["sanct_set_from_gy"],
    # Fiendsmith in Paradise (20251)
    (FIENDSMITH_IN_PARADISE_CID, "e1"): ["paradise_field_wipe"],
    (FIENDSMITH_IN_PARADISE_CID, "e2"): ["paradise_gy_banish_send_fiendsmith"],
    # Duke of Demise (20389)
    (DUKE_OF_DEMISE_CID, "e0"): ["duke_standby_pay", "duke_standby_destroy"],
    (DUKE_OF_DEMISE_CID, "e1"): ["duke_battle_indestructible"],
    (DUKE_OF_DEMISE_CID, "e2"): ["duke_extra_normal_summon"],
    (DUKE_OF_DEMISE_CID, "e3"): ["duke_demise_banish_recover"],
    # Necroquip Princess (20423)
    (NECROQUIP_PRINCESS_CID, "summon"): ["necroquip_contact_fusion"],
    (NECROQUIP_PRINCESS_CID, "e0"): [],  # Restriction effect
    (NECROQUIP_PRINCESS_CID, "e1"): ["necroquip_draw", "necroquip_equip"],
    # Aerial Eater (20427)
    (AERIAL_EATER_CID, "e1"): ["aerial_eater_send"],
    (AERIAL_EATER_CID, "e2"): ["aerial_eater_gy_revive"],
    # Lacrima the Crimson Tears (20490)
    (LACRIMA_CRIMSON_TEARS_CID, "e1"): ["send_fiendsmith_from_deck"],
    (LACRIMA_CRIMSON_TEARS_CID, "e2"): ["gy_shuffle_ss_fiendsmith_link"],
    # Fiendsmith's Agnumday (20521)
    (FIENDSMITH_AGNUMDAY_CID, "e1"): ["agnumday_revive_equip"],
    # Snake-Eyes Doomed Dragon (20772)
    (SNAKE_EYES_DOOMED_DRAGON_CID, "e0"): ["doomed_dragon_contact_summon"],
    (SNAKE_EYES_DOOMED_DRAGON_CID, "e1"): ["doomed_dragon_move_to_stz"],
    # Fiendsmith's Rextremende (20774)
    (FIENDSMITH_REXTREMENDE_CID, "e1"): ["rextremende_immunity"],
    (FIENDSMITH_REXTREMENDE_CID, "e2"): ["rextremende_discard_send_light_fiend"],
    (FIENDSMITH_REXTREMENDE_CID, "e3"): ["gy_rextremende_recover_fiendsmith"],
    # A Bao A Qu (20786)
    (A_BAO_A_QU_CID, "e1"): ["abao_discard_destroy", "abao_discard_banish_revive"],
    (A_BAO_A_QU_CID, "e2"): ["abao_standby_draw_cycle"],
    # Fiendsmith Kyrie (20816)
    (FIENDSMITH_KYRIE_CID, "e1"): ["kyrie_activate_battle_shield"],
    (FIENDSMITH_KYRIE_CID, "e2"): ["kyrie_gy_banish_fuse"],
    # Buio the Dawn's Light (21624)
    (BUIO_DAWNS_LIGHT_CID, "e1"): ["buio_lr_protect"],
    (BUIO_DAWNS_LIGHT_CID, "e2"): ["buio_hand_ss"],
    (BUIO_DAWNS_LIGHT_CID, "e3"): ["buio_gy_search_mutiny"],
    # Luce the Dusk's Dark (21625)
    (LUCE_DUSKS_DARK_CID, "e1"): ["luce_lr_protect"],
    (LUCE_DUSKS_DARK_CID, "e2"): ["luce_send_and_destroy"],
    (LUCE_DUSKS_DARK_CID, "e3"): ["luce_destroy_card"],
    # Mutiny in the Sky (21626)
    (MUTINY_IN_THE_SKY_CID, "e1"): ["mutiny_fusion_summon"],
    (MUTINY_IN_THE_SKY_CID, "e2"): ["mutiny_gy_add"],
}


def get_impl_effect_ids(cid: str, verified_id: str) -> list[str]:
    """Get the implementation effect_ids for a given card and verified effect id."""
    return EFFECT_ID_MAPPING.get((cid, verified_id), [])


# ============================================================================
# OPT key mapping: (cid, verified_id) -> implementation opt_used key
# Some effects use different opt keys in implementation vs verified_effects.json
# ============================================================================
OPT_KEY_MAPPING: dict[tuple[str, str], str] = {
    # Fiendsmith's Lacrima: e3 (GY burn) uses opt key "e2" in implementation
    (FIENDSMITH_LACRIMA_CID, "e3"): f"{FIENDSMITH_LACRIMA_CID}:e2",
    # Fiendsmith's Desirae: e2 (GY send) uses opt key "e1" in implementation
    (FIENDSMITH_DESIRAE_CID, "e2"): f"{FIENDSMITH_DESIRAE_CID}:e1",
}


def get_opt_key(cid: str, verified_id: str) -> str:
    """Get the implementation opt_used key for a given card and verified effect id."""
    return OPT_KEY_MAPPING.get((cid, verified_id), f"{cid}:{verified_id}")


def load_verified_effects() -> dict[str, Any]:
    path = repo_root / "config" / "verified_effects.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ============================================================================
# Helper functions for creating card entries with proper metadata
# ============================================================================

def make_light_fiend_monster(name: str = "Generic LIGHT Fiend", cid: str = "DUMMY_LIGHT_FIEND") -> dict[str, Any]:
    """Create a LIGHT Fiend monster card entry."""
    return {
        "cid": cid,
        "name": name,
        "metadata": {"attribute": "LIGHT", "race": "FIEND", "card_type": "monster", "level": 4},
    }


def make_fiendsmith_st(name: str = "Fiendsmith Tract", cid: str = FIENDSMITH_TRACT_CID) -> dict[str, Any]:
    """Create a Fiendsmith Spell/Trap card entry."""
    return {"cid": cid, "name": name, "metadata": {"card_type": "spell"}}


def make_fiendsmith_monster(name: str = "Fiendsmith Engraver", cid: str = FIENDSMITH_ENGRAVER_CID) -> dict[str, Any]:
    """Create a Fiendsmith monster card entry."""
    return {
        "cid": cid,
        "name": name,
        "metadata": {"attribute": "LIGHT", "race": "FIEND", "card_type": "monster", "level": 6},
    }


def make_fiendsmith_link(name: str = "Fiendsmith Requiem", cid: str = FIENDSMITH_REQUIEM_CID) -> dict[str, Any]:
    """Create a Fiendsmith Link monster card entry."""
    return {
        "cid": cid,
        "name": name,
        "metadata": {"attribute": "LIGHT", "race": "FIEND", "card_type": "monster", "summon_type": "link", "link_rating": 1},
        "properly_summoned": True,
    }


def make_fiendsmith_fusion(name: str = "Fiendsmith's Lacrima", cid: str = FIENDSMITH_LACRIMA_CID) -> dict[str, Any]:
    """Create a Fiendsmith Fusion monster card entry."""
    return {
        "cid": cid,
        "name": name,
        "metadata": {"attribute": "LIGHT", "race": "FIEND", "card_type": "monster", "summon_type": "fusion", "level": 6},
        "properly_summoned": True,
    }


def make_xyz_monster(name: str = "Evilswarm Exciton Knight", cid: str = EVILSWARM_EXCITON_KNIGHT_CID, materials: int = 2) -> dict[str, Any]:
    """Create an Xyz monster card entry with materials."""
    return {
        "cid": cid,
        "name": name,
        "metadata": {"attribute": "LIGHT", "race": "FIEND", "card_type": "monster", "summon_type": "xyz", "rank": 4},
        "properly_summoned": True,
        "xyz_materials": [{"cid": f"MAT_{i}", "name": f"Material {i}"} for i in range(materials)],
    }


def make_fiend_monster(name: str = "Generic Fiend", cid: str = "DUMMY_FIEND", level: int = 4) -> dict[str, Any]:
    """Create a generic Fiend monster (not necessarily LIGHT)."""
    return {
        "cid": cid,
        "name": name,
        "metadata": {"attribute": "DARK", "race": "FIEND", "card_type": "monster", "level": level},
    }


def make_dark_contract(name: str = "Dark Contract", cid: str = "DARK_CONTRACT") -> dict[str, Any]:
    """Create a Dark Contract spell card."""
    return {"cid": cid, "name": name, "metadata": {"card_type": "spell"}}


def make_level4_monster(name: str = "Level 4 Monster", cid: str = "LV4_MONSTER") -> dict[str, Any]:
    """Create a generic Level 4 monster."""
    return {
        "cid": cid,
        "name": name,
        "metadata": {"card_type": "monster", "level": 4},
    }


def make_mutiny_spell(name: str = "Mutiny in the Sky", cid: str = MUTINY_IN_THE_SKY_CID) -> dict[str, Any]:
    """Create Mutiny in the Sky spell card."""
    return {"cid": cid, "name": name, "metadata": {"card_type": "spell"}}


def make_fairy_monster(name: str = "Fairy Monster", cid: str = "FAIRY_MONSTER") -> dict[str, Any]:
    """Create a LIGHT Fairy monster."""
    return {
        "cid": cid,
        "name": name,
        "metadata": {"attribute": "LIGHT", "race": "FAIRY", "card_type": "monster", "level": 4},
    }


def make_fiend_effect_monster(name: str = "Fiend Effect Monster", cid: str = "FIEND_EFFECT") -> dict[str, Any]:
    """Create a Fiend Effect monster."""
    return {
        "cid": cid,
        "name": name,
        "metadata": {"attribute": "DARK", "race": "FIEND", "card_type": "monster", "level": 4, "monster_type": "effect"},
    }


def _blank_snapshot() -> dict[str, Any]:
    """Create a blank game state snapshot."""
    return {
        "zones": {
            "hand": [],
            "deck": [],
            "gy": [],
            "banished": [],
            "extra": [],
            "field_zones": {
                "mz": [None, None, None, None, None],
                "emz": [None, None],
                "stz": [None, None, None, None, None],
                "fz": [None],
            },
        },
        "phase": "Main Phase 1",
        "events": [],
        "opt_used": {},
        "pending_triggers": [],
        "last_moved_to_gy": [],
    }


# ============================================================================
# Card-specific setup functions
# ============================================================================

def get_card_specific_setup(cid: str, effect_id: str, card_name: str, card_type: str) -> dict[str, Any] | None:
    """
    Return a complete game state setup for a specific card effect.
    Returns None if no specific setup is needed (use generic setup).
    """
    snapshot = _blank_snapshot()

    # Fiendsmith Engraver (20196)
    if cid == FIENDSMITH_ENGRAVER_CID:
        if effect_id == "e1":
            # Hand effect: discard to search Fiendsmith S/T from deck
            snapshot["zones"]["hand"].append(make_fiendsmith_monster("Fiendsmith Engraver", cid))
            snapshot["zones"]["deck"].append(make_fiendsmith_st("Fiendsmith Tract", FIENDSMITH_TRACT_CID))
            return snapshot
        elif effect_id == "e2":
            # Field effect: send equip + monster to GY
            # Need Engraver on field + a monster with Fiendsmith Equip equipped
            engraver = make_fiendsmith_monster("Fiendsmith Engraver", cid)
            snapshot["zones"]["field_zones"]["mz"][0] = engraver
            # Another monster with Fiendsmith Equip equipped
            host = make_light_fiend_monster("Host Monster", "HOST_MONSTER")
            equip = make_fiendsmith_link("Fiendsmith Requiem", FIENDSMITH_REQUIEM_CID)
            host["equipped"] = [equip]
            snapshot["zones"]["field_zones"]["mz"][1] = host
            return snapshot
        elif effect_id == "e3":
            # GY effect: shuffle OTHER LIGHT Fiend to SS self
            snapshot["zones"]["gy"].append(make_fiendsmith_monster("Fiendsmith Engraver", cid))
            snapshot["zones"]["gy"].append(make_light_fiend_monster("Shuffle Target", "SHUFFLE_TARGET"))
            return snapshot

    # Evilswarm Exciton Knight (10942)
    if cid == EVILSWARM_EXCITON_KNIGHT_CID:
        if effect_id == "e1":
            # Field quick effect: detach to destroy all cards
            # Requires: COND_EXCITON_ONLINE event (opponent has more cards)
            exciton = make_xyz_monster("Evilswarm Exciton Knight", cid, 2)
            snapshot["zones"]["field_zones"]["mz"][0] = exciton
            # Add another card on field as target
            snapshot["zones"]["field_zones"]["mz"][1] = make_level4_monster("Destroy Target", "DESTROY_TARGET")
            # Must have the exact event the implementation checks for
            snapshot["events"].append("COND_EXCITON_ONLINE")
            return snapshot

    # D/D/D Wave High King Caesar (13081)
    if cid == DDD_WAVE_HIGH_KING_CAESAR_CID:
        if effect_id == "e1":
            # Quick effect on field: negate summon effect
            # Requires: OPP_ACTIVATED_EFFECT or OPP_SPECIAL_SUMMON_EFFECT event
            caesar = make_xyz_monster("D/D/D Wave High King Caesar", cid, 2)
            caesar["metadata"]["attribute"] = "DARK"
            caesar["metadata"]["race"] = "FIEND"
            snapshot["zones"]["field_zones"]["mz"][0] = caesar
            # Add a target for the negate
            snapshot["zones"]["field_zones"]["mz"][1] = make_level4_monster("Negate Target", "NEGATE_TARGET")
            snapshot["events"].append("OPP_ACTIVATED_EFFECT")
            return snapshot
        elif effect_id == "e2":
            # GY trigger: sent from field to GY
            caesar_card = {"cid": cid, "name": "D/D/D Wave High King Caesar", "metadata": {"attribute": "DARK", "race": "FIEND", "card_type": "monster", "summon_type": "xyz", "rank": 7}}
            snapshot["zones"]["gy"].append(caesar_card)
            snapshot["last_moved_to_gy"] = [cid]
            # Need Dark Contract in deck
            snapshot["zones"]["deck"].append(make_dark_contract("Dark Contract with the Gate", "DARK_CONTRACT"))
            # Implementation bug: requires OPP_ACTIVATED_EFFECT to not return early
            snapshot["events"].append("OPP_ACTIVATED_EFFECT")
            return snapshot

    # Cross-Sheep (14856)
    if cid == CROSS_SHEEP_CID:
        if effect_id == "e1":
            # Trigger: monster SS to zone this points to (Fusion effect = revive)
            cross_sheep = {"cid": cid, "name": "Cross-Sheep", "metadata": {"card_type": "monster", "summon_type": "link", "link_rating": 2}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["emz"][0] = cross_sheep
            # Need the specific trigger event and a target in GY
            snapshot["events"].append("CROSS_SHEEP_TRIGGER")
            snapshot["zones"]["gy"].append(make_level4_monster("GY Target", "GY_TARGET"))
            return snapshot

    # Muckraker From the Underworld (17806)
    if cid == MUCKRAKER_CID:
        if effect_id == "e0":
            # Continuous: cannot be Link material if Link Summoned this turn
            muckraker = {"cid": cid, "name": "Muckraker From the Underworld", "metadata": {"card_type": "monster", "summon_type": "link", "link_rating": 2, "race": "FIEND"}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = muckraker
            return snapshot
        elif effect_id == "e1":
            # Continuous: tribute Fiend to protect monster from destruction
            # Requires: MUCKRAKER_REPLACE_TRIGGER event, Fiend to tribute
            muckraker = {"cid": cid, "name": "Muckraker From the Underworld", "metadata": {"card_type": "monster", "summon_type": "link", "link_rating": 2, "race": "FIEND"}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = muckraker
            snapshot["zones"]["field_zones"]["mz"][1] = make_fiend_monster("Tribute Fodder", "TRIBUTE_FODDER")
            snapshot["events"].append("MUCKRAKER_REPLACE_TRIGGER")
            return snapshot
        elif effect_id == "e2":
            # Ignition: discard to SS Fiend from GY
            muckraker = {"cid": cid, "name": "Muckraker From the Underworld", "metadata": {"card_type": "monster", "summon_type": "link", "link_rating": 2, "race": "FIEND"}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = muckraker
            snapshot["zones"]["hand"].append({"cid": "DISCARD_FODDER", "name": "Discard Fodder"})
            snapshot["zones"]["gy"].append(make_fiend_monster("Revival Target", "REVIVAL_TARGET"))
            return snapshot

    # S:P Little Knight (19188)
    if cid == SP_LITTLE_KNIGHT_CID:
        if effect_id == "e1":
            # Trigger: if Link Summoned using Fusion/Synchro/Xyz/Link material
            sp = {"cid": cid, "name": "S:P Little Knight", "metadata": {"card_type": "monster", "summon_type": "link", "link_rating": 2}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = sp
            # Required event for trigger
            snapshot["events"].append("SP_LITTLE_KNIGHT_TRIGGER")
            # Target: any card on field or GY
            snapshot["zones"]["field_zones"]["mz"][1] = make_level4_monster("Banish Target", "BANISH_TARGET")
            return snapshot
        elif effect_id == "e2":
            # Quick: banish 2 face-up monsters (at least 1 you control)
            sp = {"cid": cid, "name": "S:P Little Knight", "metadata": {"card_type": "monster", "summon_type": "link", "link_rating": 2}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = sp
            snapshot["zones"]["field_zones"]["mz"][1] = make_level4_monster("Your Monster", "YOUR_MONSTER")
            # Required event for quick effect
            snapshot["events"].append("SP_LITTLE_KNIGHT_QUICK")
            return snapshot

    # Fiendsmith's Lacrima (20214) - Fusion
    if cid == FIENDSMITH_LACRIMA_CID:
        if effect_id == "e1":
            # Continuous: opponent's monsters lose 600 ATK
            lacrima = make_fiendsmith_fusion("Fiendsmith's Lacrima", cid)
            snapshot["zones"]["field_zones"]["mz"][0] = lacrima
            return snapshot
        elif effect_id == "e2":
            # Trigger: if Fusion Summoned, add/SS LIGHT Fiend from GY/banished
            lacrima = make_fiendsmith_fusion("Fiendsmith's Lacrima", cid)
            snapshot["zones"]["field_zones"]["mz"][0] = lacrima
            snapshot["pending_triggers"].append(f"SUMMON:{cid}")
            snapshot["zones"]["gy"].append(make_light_fiend_monster("GY Target", "GY_LIGHT_FIEND"))
            return snapshot
        elif effect_id == "e3":
            # GY trigger: if sent to GY, shuffle LIGHT Fiend for damage
            snapshot["zones"]["gy"].append(make_fiendsmith_fusion("Fiendsmith's Lacrima", cid))
            snapshot["zones"]["gy"].append(make_light_fiend_monster("Shuffle Target", "SHUFFLE_TARGET"))
            snapshot["pending_triggers"].append(f"SENT_TO_GY:{cid}")
            snapshot["last_moved_to_gy"] = [cid]
            return snapshot

    # Fiendsmith's Desirae (20215) - Fusion
    if cid == FIENDSMITH_DESIRAE_CID:
        if effect_id == "e1":
            # Quick: negate based on equipped Link Rating
            desirae = make_fiendsmith_fusion("Fiendsmith's Desirae", cid)
            # Need equipped cards with Link Rating
            equip = make_fiendsmith_link("Fiendsmith Requiem", FIENDSMITH_REQUIEM_CID)
            desirae["equipped"] = [equip]
            snapshot["zones"]["field_zones"]["mz"][0] = desirae
            # Need target to negate
            snapshot["zones"]["field_zones"]["mz"][1] = make_level4_monster("Negate Target", "NEGATE_TARGET")
            return snapshot
        elif effect_id == "e2":
            # GY trigger: sent to GY, shuffle LIGHT Fiend to send card to GY
            snapshot["zones"]["gy"].append(make_fiendsmith_fusion("Fiendsmith's Desirae", cid))
            snapshot["zones"]["gy"].append(make_light_fiend_monster("Shuffle Target", "SHUFFLE_TARGET"))
            snapshot["pending_triggers"].append(f"SENT_TO_GY:{cid}")
            snapshot["last_moved_to_gy"] = [cid]
            # Target on field
            snapshot["zones"]["field_zones"]["mz"][0] = make_level4_monster("Send Target", "SEND_TARGET")
            return snapshot

    # Fiendsmith's Requiem (20225) - Link-1
    if cid == FIENDSMITH_REQUIEM_CID:
        if effect_id == "e0":
            # Restriction effect (continuous) - this is a passive effect, not an activated one
            # The restriction just exists when Requiem is on field - test e1 instead
            # For now, return setup that allows e1 to work
            requiem = {"cid": cid, "name": "Fiendsmith's Requiem", "metadata": {"attribute": "LIGHT", "race": "FIEND", "card_type": "monster", "summon_type": "link", "link_rating": 1}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = requiem
            snapshot["zones"]["deck"].append(make_fiendsmith_monster("Fiendsmith Engraver", FIENDSMITH_ENGRAVER_CID))
            return snapshot
        elif effect_id == "e1":
            # Quick: tribute self to SS Fiendsmith from hand/deck
            requiem = make_fiendsmith_link("Fiendsmith's Requiem", cid)
            snapshot["zones"]["field_zones"]["mz"][0] = requiem
            # Deck needs Fiendsmith monster target
            snapshot["zones"]["deck"].append(make_fiendsmith_monster("Fiendsmith Engraver", FIENDSMITH_ENGRAVER_CID))
            return snapshot
        elif effect_id == "e2":
            # Field/GY ignition: equip to non-Link LIGHT Fiend
            # Test from field location
            requiem = make_fiendsmith_link("Fiendsmith's Requiem", cid)
            snapshot["zones"]["field_zones"]["mz"][0] = requiem
            # Need non-Link LIGHT Fiend to equip to
            target = make_fiendsmith_fusion("Fiendsmith's Lacrima", FIENDSMITH_LACRIMA_CID)
            snapshot["zones"]["field_zones"]["mz"][1] = target
            return snapshot

    # Fiendsmith's Sequence (20238) - Link-2
    if cid == FIENDSMITH_SEQUENCE_CID:
        if effect_id == "e1":
            # Ignition: Fusion Summon using GY materials
            sequence = make_fiendsmith_link("Fiendsmith's Sequence", cid)
            sequence["metadata"]["link_rating"] = 2
            snapshot["zones"]["field_zones"]["mz"][0] = sequence
            # GY needs fusion materials
            snapshot["zones"]["gy"].append(make_light_fiend_monster("Material 1", "MAT_1"))
            snapshot["zones"]["gy"].append(make_light_fiend_monster("Material 2", "MAT_2"))
            # Extra deck needs fusion target
            snapshot["zones"]["extra"].append(make_fiendsmith_fusion("Fiendsmith's Lacrima", FIENDSMITH_LACRIMA_CID))
            return snapshot
        elif effect_id == "e2":
            # Field/GY ignition: equip to non-Link LIGHT Fiend
            sequence = make_fiendsmith_link("Fiendsmith's Sequence", cid)
            snapshot["zones"]["field_zones"]["mz"][0] = sequence
            target = make_fiendsmith_fusion("Fiendsmith's Lacrima", FIENDSMITH_LACRIMA_CID)
            snapshot["zones"]["field_zones"]["mz"][1] = target
            return snapshot

    # Fiendsmith's Sequence alt CID (20226)
    if cid == FIENDSMITH_SEQUENCE_ALT_CID:
        if effect_id == "e1":
            sequence = make_fiendsmith_link("Fiendsmith's Sequence", cid)
            sequence["metadata"]["link_rating"] = 2
            snapshot["zones"]["field_zones"]["mz"][0] = sequence
            snapshot["zones"]["gy"].append(make_light_fiend_monster("Material 1", "MAT_1"))
            snapshot["zones"]["gy"].append(make_light_fiend_monster("Material 2", "MAT_2"))
            snapshot["zones"]["extra"].append(make_fiendsmith_fusion("Fiendsmith's Lacrima", FIENDSMITH_LACRIMA_CID))
            return snapshot
        elif effect_id == "e2":
            sequence = make_fiendsmith_link("Fiendsmith's Sequence", cid)
            snapshot["zones"]["field_zones"]["mz"][0] = sequence
            target = make_fiendsmith_fusion("Fiendsmith's Lacrima", FIENDSMITH_LACRIMA_CID)
            snapshot["zones"]["field_zones"]["mz"][1] = target
            return snapshot

    # Fiendsmith's Tract (20240) - Spell
    if cid == FIENDSMITH_TRACT_CID:
        if effect_id == "e1":
            # Spell activation: search LIGHT Fiend then discard
            snapshot["zones"]["hand"].append(make_fiendsmith_st("Fiendsmith's Tract", cid))
            snapshot["zones"]["hand"].append({"cid": "DISCARD_FODDER", "name": "Discard Fodder"})
            snapshot["zones"]["deck"].append(make_light_fiend_monster("Search Target", "SEARCH_TARGET"))
            return snapshot
        elif effect_id == "e2":
            # GY ignition: banish to Fusion Summon
            snapshot["zones"]["gy"].append(make_fiendsmith_st("Fiendsmith's Tract", cid))
            # Materials on field/hand
            snapshot["zones"]["field_zones"]["mz"][0] = make_light_fiend_monster("Material 1", "MAT_1")
            snapshot["zones"]["field_zones"]["mz"][1] = make_light_fiend_monster("Material 2", "MAT_2")
            snapshot["zones"]["extra"].append(make_fiendsmith_fusion("Fiendsmith's Lacrima", FIENDSMITH_LACRIMA_CID))
            return snapshot

    # Fiendsmith's Sanct (20241) - Spell
    if cid == FIENDSMITH_SANCT_CID:
        if effect_id == "e1":
            # Spell activation: SS Fiendsmith Token if control no/only LIGHT Fiend monsters
            snapshot["zones"]["hand"].append(make_fiendsmith_st("Fiendsmith's Sanct", cid))
            return snapshot
        elif effect_id == "e2":
            # GY trigger: if Fiendsmith destroyed by opponent
            snapshot["zones"]["gy"].append(make_fiendsmith_st("Fiendsmith's Sanct", cid))
            snapshot["pending_triggers"].append("FIENDSMITH_DESTROYED_BY_OPP")
            snapshot["events"].append("FIENDSMITH_DESTROYED_BY_OPP")
            return snapshot

    # Fiendsmith in Paradise (20251) - Trap
    # NOTE: Trap activation requires set trap in stz, but registry only checks mz/emz/hand/gy
    # This effect may not be testable without registry updates
    if cid == FIENDSMITH_IN_PARADISE_CID:
        if effect_id == "e1":
            # Trap activation - not currently enumerable via standard registry
            # The registry doesn't iterate over stz for effect enumeration
            return None  # Fall back to generic setup
        elif effect_id == "e2":
            # GY trigger: opponent SS, banish to send Fiendsmith from deck/Extra to GY
            snapshot["zones"]["gy"].append({"cid": cid, "name": "Fiendsmith in Paradise", "metadata": {"card_type": "trap"}})
            snapshot["events"].append("OPP_SPECIAL_SUMMON")
            snapshot["pending_triggers"].append("OPPONENT_SS")
            snapshot["zones"]["deck"].append(make_fiendsmith_monster())
            return snapshot

    # Duke of Demise (20389)
    if cid == DUKE_OF_DEMISE_CID:
        if effect_id == "e0":
            # Continuous: during Standby, pay 500 LP or destroy
            # This is a maintenance effect, not an activated effect
            duke = make_fiend_monster("Duke of Demise", cid, level=6)
            snapshot["zones"]["field_zones"]["mz"][0] = duke
            snapshot["phase"] = "Standby Phase"
            return snapshot
        elif effect_id == "e1":
            # Continuous: cannot be destroyed by battle
            # Passive effect, not activatable
            duke = make_fiend_monster("Duke of Demise", cid, level=6)
            snapshot["zones"]["field_zones"]["mz"][0] = duke
            return snapshot
        elif effect_id == "e2":
            # Ignition: Normal Summon
            duke = make_fiend_monster("Duke of Demise", cid, level=6)
            snapshot["zones"]["field_zones"]["mz"][0] = duke
            snapshot["zones"]["hand"].append(make_level4_monster("NS Target", "NS_TARGET"))
            return snapshot
        elif effect_id == "e3":
            # GY ignition: banish to add Level 4+ Fiend/Zombie from GY
            # Requires DUKE_DEMISE_GY_TRIGGER event
            snapshot["zones"]["gy"].append(make_fiend_monster("Duke of Demise", cid, level=6))
            target = make_fiend_monster("Recovery Target", "RECOVERY_TARGET")
            target["metadata"]["level"] = 4
            snapshot["zones"]["gy"].append(target)
            snapshot["events"].append("DUKE_DEMISE_GY_TRIGGER")
            return snapshot

    # Necroquip Princess (20423)
    if cid == NECROQUIP_PRINCESS_CID:
        if effect_id == "summon":
            # Contact Fusion: special summon procedure - not an activated effect
            # This is a summoning procedure, not testable as effect activation
            return None  # Fall back to generic setup
        elif effect_id == "e0":
            # Restriction: can only control 1 - passive, not activated
            return None  # Fall back to generic setup
        elif effect_id == "e1":
            # Trigger: when monster sent from hand to GY as cost
            necro = {"cid": cid, "name": "Necroquip Princess", "metadata": {"card_type": "monster", "summon_type": "fusion"}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = necro
            # Requires NECROQUIP_TRIGGER event
            snapshot["events"].append("NECROQUIP_TRIGGER")
            return snapshot

    # Aerial Eater (20427)
    if cid == AERIAL_EATER_CID:
        if effect_id == "e1":
            # Trigger: if Fusion Summoned, send Fiend from deck to GY
            # Requires AERIAL_EATER_TRIGGER event
            aerial = {"cid": cid, "name": "Aerial Eater", "metadata": {"card_type": "monster", "summon_type": "fusion", "attribute": "DARK", "race": "FIEND", "level": 9}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = aerial
            snapshot["events"].append("AERIAL_EATER_TRIGGER")
            snapshot["zones"]["deck"].append(make_fiend_monster("Send Target", "SEND_TARGET"))
            return snapshot
        elif effect_id == "e2":
            # GY ignition: revive self from GY
            # Requires: Main Phase, Aerial Eater in GY with properly_summoned=True, open MZ
            snapshot["zones"]["gy"].append({"cid": cid, "name": "Aerial Eater", "metadata": {"card_type": "monster", "summon_type": "fusion", "attribute": "DARK", "race": "FIEND", "level": 9}, "properly_summoned": True})
            return snapshot

    # Lacrima the Crimson Tears (20490)
    if cid == LACRIMA_CRIMSON_TEARS_CID:
        if effect_id == "e1":
            # Trigger: if NS/SS, send Fiendsmith from deck to GY
            lacrima_ct = make_light_fiend_monster("Lacrima the Crimson Tears", cid)
            snapshot["zones"]["field_zones"]["mz"][0] = lacrima_ct
            snapshot["pending_triggers"].append(f"SUMMON:{cid}")
            snapshot["zones"]["deck"].append(make_fiendsmith_st("Fiendsmith Tract", FIENDSMITH_TRACT_CID))
            return snapshot
        elif effect_id == "e2":
            # GY quick: during opp turn, shuffle self to SS Fiendsmith Link from GY
            snapshot["zones"]["gy"].append(make_light_fiend_monster("Lacrima the Crimson Tears", cid))
            snapshot["zones"]["gy"].append(make_fiendsmith_link("Fiendsmith Requiem", FIENDSMITH_REQUIEM_CID))
            snapshot["events"].append("OPP_TURN")
            return snapshot

    # Fiendsmith's Agnumday (20521) - Link-3
    if cid == FIENDSMITH_AGNUMDAY_CID:
        if effect_id == "e1":
            # Quick: target LIGHT non-Link Fiend in GY, SS and equip self
            agnumday = make_fiendsmith_link("Fiendsmith's Agnumday", cid)
            agnumday["metadata"]["link_rating"] = 3
            snapshot["zones"]["field_zones"]["mz"][0] = agnumday
            # Non-Link LIGHT Fiend in GY
            target = make_light_fiend_monster("Revival Target", "REVIVAL_TARGET")
            target["metadata"]["level"] = 4  # Not a Link
            snapshot["zones"]["gy"].append(target)
            return snapshot

    # Snake-Eyes Doomed Dragon (20772)
    if cid == SNAKE_EYES_DOOMED_DRAGON_CID:
        if effect_id == "e0":
            # SS procedure: not an activated effect, it's a summoning procedure
            return None  # Fall back to generic setup
        elif effect_id == "e1":
            # Trigger: if SS, move monster to S/T zone as Continuous Spell
            # Requires DOOMED_DRAGON_TRIGGER event
            dragon = {"cid": cid, "name": "Snake-Eyes Doomed Dragon", "metadata": {"card_type": "monster", "level": 8}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = dragon
            snapshot["events"].append("DOOMED_DRAGON_TRIGGER")
            # Target on field
            snapshot["zones"]["field_zones"]["mz"][1] = make_level4_monster("Move Target", "MOVE_TARGET")
            return snapshot

    # Fiendsmith's Rextremende (20774) - Fusion
    if cid == FIENDSMITH_REXTREMENDE_CID:
        if effect_id == "e1":
            # Continuous: unaffected if equipped with Fiendsmith Equip
            rex = make_fiendsmith_fusion("Fiendsmith's Rextremende", cid)
            equip = make_fiendsmith_link("Fiendsmith Sequence", FIENDSMITH_SEQUENCE_CID)
            rex["equipped"] = [equip]
            snapshot["zones"]["field_zones"]["mz"][0] = rex
            return snapshot
        elif effect_id == "e2":
            # Trigger: if Fusion Summoned, discard to send LIGHT Fiend from deck/Extra to GY
            rex = make_fiendsmith_fusion("Fiendsmith's Rextremende", cid)
            snapshot["zones"]["field_zones"]["mz"][0] = rex
            snapshot["pending_triggers"].append(f"SUMMON:{cid}")
            snapshot["zones"]["hand"].append({"cid": "DISCARD", "name": "Discard Fodder"})
            snapshot["zones"]["deck"].append(make_light_fiend_monster("Send Target", "SEND_TARGET"))
            return snapshot
        elif effect_id == "e3":
            # GY trigger: if sent to GY, add other Fiendsmith from GY/banished
            snapshot["zones"]["gy"].append(make_fiendsmith_fusion("Fiendsmith's Rextremende", cid))
            snapshot["zones"]["gy"].append(make_fiendsmith_st("Fiendsmith Tract", FIENDSMITH_TRACT_CID))
            snapshot["pending_triggers"].append(f"SENT_TO_GY:{cid}")
            snapshot["last_moved_to_gy"] = [cid]
            return snapshot

    # A Bao A Qu, the Lightless Shadow (20786)
    # Implementation requires summon_type="link" for e1
    if cid == A_BAO_A_QU_CID:
        if effect_id == "e1":
            # Quick: discard to destroy or banish self + SS from GY
            # Implementation requires: Main Phase, Link monster, hand for discard, target
            abao = {"cid": cid, "name": "A Bao A Qu", "metadata": {"attribute": "DARK", "race": "FIEND", "card_type": "monster", "summon_type": "link", "link_rating": 4}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = abao
            snapshot["zones"]["hand"].append({"cid": "DISCARD", "name": "Discard Fodder"})
            # For the destroy option, need a target
            snapshot["zones"]["field_zones"]["mz"][1] = make_level4_monster("Destroy Target", "DESTROY_TARGET")
            return snapshot
        elif effect_id == "e2":
            # Trigger: during Standby, draw = Monster Types in GY
            # Requires: Standby Phase, monster types in GY, enough deck/hand
            abao = {"cid": cid, "name": "A Bao A Qu", "metadata": {"attribute": "DARK", "race": "FIEND", "card_type": "monster", "summon_type": "link", "link_rating": 4}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = abao
            snapshot["phase"] = "Standby Phase"
            # GY with different monster types for draw count
            snapshot["zones"]["gy"].append(make_fiend_monster("Fiend", "FIEND_GY"))
            snapshot["zones"]["gy"].append(make_fairy_monster("Fairy", "FAIRY_GY"))
            # Need enough deck cards to draw and hand cards to put back
            snapshot["zones"]["deck"].extend([{"cid": f"DECK_{i}", "name": f"Deck Card {i}"} for i in range(5)])
            snapshot["zones"]["hand"].append({"cid": "HAND_1", "name": "Hand Card 1"})
            snapshot["zones"]["hand"].append({"cid": "HAND_2", "name": "Hand Card 2"})
            return snapshot

    # Fiendsmith Kyrie (20816) - Trap
    # NOTE: Trap activation requires set trap in stz, but registry only checks mz/emz/hand/gy
    if cid == FIENDSMITH_KYRIE_CID:
        if effect_id == "e1":
            # Trap activation - not enumerable via standard registry (stz not checked)
            return None  # Fall back to generic setup
        elif effect_id == "e2":
            # GY quick: banish to Fusion Summon using field/equipped monsters
            snapshot["zones"]["gy"].append({"cid": cid, "name": "Fiendsmith Kyrie", "metadata": {"card_type": "trap"}})
            # Materials: field monsters or equipped to Fiendsmith
            snapshot["zones"]["field_zones"]["mz"][0] = make_light_fiend_monster("Material 1", "MAT_1")
            snapshot["zones"]["field_zones"]["mz"][1] = make_light_fiend_monster("Material 2", "MAT_2")
            snapshot["zones"]["extra"].append(make_fiendsmith_fusion("Fiendsmith's Lacrima", FIENDSMITH_LACRIMA_CID))
            return snapshot

    # Buio the Dawn's Light (21624)
    if cid == BUIO_DAWNS_LIGHT_CID:
        if effect_id == "e1":
            # Continuous: monsters in leftmost/rightmost MZ can't be destroyed by effects
            buio = make_light_fiend_monster("Buio the Dawn's Light", cid)
            snapshot["zones"]["field_zones"]["mz"][0] = buio
            return snapshot
        elif effect_id == "e2":
            # Hand ignition: target Fiend Effect Monster, negate its effects and SS self
            snapshot["zones"]["hand"].append(make_light_fiend_monster("Buio the Dawn's Light", cid))
            snapshot["zones"]["field_zones"]["mz"][0] = make_fiend_effect_monster("Fiend Effect", "FIEND_EFFECT")
            return snapshot
        elif effect_id == "e3":
            # GY trigger: if sent to GY, add Mutiny from deck
            snapshot["zones"]["gy"].append(make_light_fiend_monster("Buio the Dawn's Light", cid))
            snapshot["pending_triggers"].append(f"SENT_TO_GY:{cid}")
            snapshot["last_moved_to_gy"] = [cid]
            snapshot["zones"]["deck"].append(make_mutiny_spell())
            return snapshot

    # Luce the Dusk's Dark (21625)
    if cid == LUCE_DUSKS_DARK_CID:
        if effect_id == "e1":
            # Continuous: lr_protect - just needs Luce on field
            luce = {"cid": cid, "name": "Luce the Dusk's Dark", "metadata": {"attribute": "DARK", "race": "FIEND", "card_type": "monster", "summon_type": "fusion", "level": 8}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = luce
            return snapshot
        elif effect_id == "e2":
            # Ignition: target field card, send Fiend/Fairy from deck to GY to destroy
            # Requires: Main Phase, Luce (fusion, properly_summoned), Fiend/Fairy in deck, target on field
            luce = {"cid": cid, "name": "Luce the Dusk's Dark", "metadata": {"attribute": "DARK", "race": "FIEND", "card_type": "monster", "summon_type": "fusion", "level": 8}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = luce
            # Target on field
            snapshot["zones"]["field_zones"]["mz"][1] = make_level4_monster("Destroy Target", "DESTROY_TARGET")
            # Fiend or Fairy in deck
            snapshot["zones"]["deck"].append(make_fiend_monster("Send Target", "SEND_TARGET"))
            return snapshot
        elif effect_id == "e3":
            # Trigger: if your card destroyed by effect, target and destroy
            # Requires: LUCE_DESTROY_TRIGGER event, Luce (fusion, properly_summoned), target on field
            luce = {"cid": cid, "name": "Luce the Dusk's Dark", "metadata": {"attribute": "DARK", "race": "FIEND", "card_type": "monster", "summon_type": "fusion", "level": 8}, "properly_summoned": True}
            snapshot["zones"]["field_zones"]["mz"][0] = luce
            snapshot["events"].append("LUCE_DESTROY_TRIGGER")
            snapshot["zones"]["field_zones"]["mz"][1] = make_level4_monster("Destroy Target", "DESTROY_TARGET")
            return snapshot

    # Mutiny in the Sky (21626) - Spell
    if cid == MUTINY_IN_THE_SKY_CID:
        if effect_id == "e1":
            # Spell activation: Fusion Summon Fiend/Fairy using GY materials
            snapshot["zones"]["hand"].append(make_mutiny_spell())
            # GY materials
            snapshot["zones"]["gy"].append(make_fiend_monster("Fiend 1", "FIEND_1"))
            snapshot["zones"]["gy"].append(make_fairy_monster("Fairy 1", "FAIRY_1"))
            # Extra deck target (need a Fiend or Fairy Fusion)
            fusion = {"cid": "FIEND_FUSION", "name": "Fiend Fusion Monster", "metadata": {"card_type": "monster", "summon_type": "fusion", "race": "FIEND"}}
            snapshot["zones"]["extra"].append(fusion)
            return snapshot
        elif effect_id == "e2":
            # GY ignition: send Fiend/Fairy from hand/field to add this to hand
            snapshot["zones"]["gy"].append(make_mutiny_spell())
            snapshot["zones"]["hand"].append(make_fiend_monster("Send Target", "SEND_TARGET"))
            return snapshot

    return None


def parse_cost(cost_text: str) -> dict[str, Any]:
    requirements: dict[str, Any] = {}
    cost_lower = cost_text.lower()
    if "discard" in cost_lower:
        requirements["discard"] = True
        if "this card" in cost_lower:
            requirements["discard_self"] = True
    if "shuffle" in cost_lower:
        requirements["shuffle"] = True
        if "other" in cost_lower:
            requirements["shuffle_other"] = True
    if "banish" in cost_lower:
        requirements["banish"] = True
        if "this card" in cost_lower:
            requirements["banish_self"] = True
    if "tribute" in cost_lower:
        requirements["tribute"] = True
    if "light fiend" in cost_lower:
        requirements["light_fiend"] = True
    return requirements


def parse_action_targets(action_text: str) -> dict[str, bool]:
    targets = {}
    text = action_text.lower()
    if "from your deck" in text:
        targets["deck"] = True
    if "from your extra deck" in text:
        targets["extra"] = True
    if "from your gy" in text or "from the gy" in text:
        targets["gy"] = True
    if "from banishment" in text or "banished" in text:
        targets["banished"] = True
    if "on the field" in text or "on field" in text:
        targets["field"] = True
    return targets


def _card_entry(cid: str, name: str | None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = {"cid": cid, "name": name or cid}
    if metadata:
        entry["metadata"] = metadata
    return entry


def _place_card(snapshot: dict[str, Any], cid: str, name: str, location: str, card_type: str) -> None:
    zones = snapshot["zones"]
    card = _card_entry(cid, name, {})
    if location == "hand":
        zones["hand"].append(card)
    elif location == "gy":
        zones["gy"].append(card)
    elif location == "banished":
        zones["banished"].append(card)
    elif location == "deck":
        zones["deck"].append(card)
    elif location == "extra":
        zones["extra"].append(card)
    elif location == "field":
        if card_type == "monster":
            zones["field_zones"]["mz"][0] = card
        else:
            zones["field_zones"]["stz"][0] = card
    else:
        zones["hand"].append(card)


def _legal_location(effect_location: str, card_type: str) -> str:
    if effect_location in {"hand", "gy", "banished", "deck", "extra"}:
        return effect_location
    if effect_location in {"field", "spell", "trap"}:
        return "field"
    if effect_location == "field/gy":
        return "field"
    return "hand"


def _wrong_location(effect_location: str) -> str:
    if effect_location == "hand":
        return "field"
    if effect_location in {"field", "spell", "trap"}:
        return "hand"
    if effect_location == "gy":
        return "field"
    if effect_location == "banished":
        return "field"
    if effect_location == "extra":
        return "field"
    return "hand"


def _apply_cost_requirements(snapshot: dict[str, Any], requirements: dict[str, Any], cid: str) -> None:
    zones = snapshot["zones"]
    if requirements.get("discard"):
        # Provide a generic discard card unless the cost is self-discard.
        if not requirements.get("discard_self"):
            zones["hand"].append(_card_entry("DUMMY_DISCARD", "Discard Fodder"))
    if requirements.get("shuffle") or requirements.get("light_fiend"):
        zones["gy"].append(
            _card_entry(
                "DUMMY_LIGHT_FIEND",
                "Generic LIGHT Fiend",
                {"attribute": "LIGHT", "race": "FIEND"},
            )
        )
        if not requirements.get("shuffle_other"):
            zones["gy"].append(_card_entry(cid, "Self"))
    if requirements.get("tribute"):
        zones["field_zones"]["mz"][1] = _card_entry("DUMMY_TRIBUTE", "Tribute Body")
    if requirements.get("banish") and not requirements.get("banish_self"):
        zones["gy"].append(_card_entry("DUMMY_BANISH", "Banish Target"))


def _apply_missing_cost(snapshot: dict[str, Any], requirements: dict[str, Any]) -> None:
    zones = snapshot["zones"]
    if requirements.get("discard") and not requirements.get("discard_self"):
        zones["hand"] = []
    if requirements.get("shuffle") or requirements.get("light_fiend"):
        zones["gy"] = []
    if requirements.get("tribute"):
        zones["field_zones"]["mz"][1] = None
    if requirements.get("banish") and not requirements.get("banish_self"):
        zones["gy"] = []


def _apply_target_requirements(snapshot: dict[str, Any], targets: dict[str, bool]) -> None:
    zones = snapshot["zones"]
    if targets.get("deck"):
        zones["deck"].append(_card_entry("DUMMY_DECK", "Deck Target"))
    if targets.get("extra"):
        zones["extra"].append(_card_entry("DUMMY_EXTRA", "Extra Target"))
    if targets.get("gy"):
        zones["gy"].append(_card_entry("DUMMY_GY", "GY Target"))
    if targets.get("banished"):
        zones["banished"].append(_card_entry("DUMMY_BAN", "Banished Target"))
    if targets.get("field"):
        zones["field_zones"]["mz"][2] = _card_entry("DUMMY_FIELD", "Field Target")


def _apply_invalid_targets(snapshot: dict[str, Any], targets: dict[str, bool]) -> None:
    zones = snapshot["zones"]
    if targets.get("deck"):
        zones["deck"] = []
    if targets.get("extra"):
        zones["extra"] = []
    if targets.get("gy"):
        zones["gy"] = []
    if targets.get("banished"):
        zones["banished"] = []
    if targets.get("field"):
        zones["field_zones"]["mz"][2] = None


def _apply_trigger(snapshot: dict[str, Any], cid: str, condition: str) -> None:
    cond = (condition or "").lower()
    if "sent to the gy" in cond or "sent to gy" in cond:
        snapshot["pending_triggers"].append(f"SENT_TO_GY:{cid}")
        snapshot["last_moved_to_gy"] = [cid]
    elif "summoned" in cond:
        snapshot["pending_triggers"].append(f"SUMMON:{cid}")
    elif "opponent" in cond and "special summon" in cond:
        snapshot["events"].append("OPP_SPECIAL_SUMMON")
    else:
        snapshot["pending_triggers"].append(f"SUMMON:{cid}")


def generate_test_cases(cid: str, card_data: dict[str, Any]) -> list[dict[str, Any]]:
    test_cases = []
    name = card_data.get("name", cid)
    card_type = card_data.get("card_type", "monster")

    for effect in card_data.get("effects", []):
        effect_id = effect["id"]
        location = effect.get("location", "field")
        cost = effect.get("cost", "")
        action = effect.get("action", "")
        opt = effect.get("opt", "none")
        effect_type = effect.get("effect_type", "")
        condition = effect.get("condition", "")

        cost_requirements = parse_cost(cost)
        target_requirements = parse_action_targets(action)

        def make_snapshot(base_location: str, use_specific: bool = False) -> dict[str, Any]:
            # First try card-specific setup for legal cases
            if use_specific:
                specific_setup = get_card_specific_setup(cid, effect_id, name, card_type)
                if specific_setup is not None:
                    return specific_setup

            # Fall back to generic setup
            snapshot = _blank_snapshot()
            _place_card(snapshot, cid, name, base_location, card_type)
            if "fusion" in condition.lower():
                zones = snapshot["zones"]
                if base_location == "field":
                    zones["field_zones"]["mz"][0]["metadata"] = {"summon_type": "fusion"}
                    zones["field_zones"]["mz"][0]["properly_summoned"] = True
            if effect_type == "trigger":
                _apply_trigger(snapshot, cid, condition)
            _apply_cost_requirements(snapshot, cost_requirements, cid)
            _apply_target_requirements(snapshot, target_requirements)
            return snapshot

        legal_location = _legal_location(location, card_type)
        wrong_location = _wrong_location(location)

        # For legal tests, try card-specific setup first
        legal_setup = get_card_specific_setup(cid, effect_id, name, card_type)
        if legal_setup is None:
            legal_setup = make_snapshot(legal_location, use_specific=False)

        test_cases.append(
            {
                "name": f"{cid}_{effect_id}_legal",
                "type": "legal",
                "effect_id": effect_id,
                "setup": legal_setup,
                "expected": "success",
            }
        )

        test_cases.append(
            {
                "name": f"{cid}_{effect_id}_wrong_location",
                "type": "wrong_location",
                "effect_id": effect_id,
                "setup": make_snapshot(wrong_location),
                "expected": "fail",
            }
        )

        if cost_requirements:
            snapshot = make_snapshot(legal_location)
            _apply_missing_cost(snapshot, cost_requirements)
            test_cases.append(
                {
                    "name": f"{cid}_{effect_id}_missing_cost",
                    "type": "missing_cost",
                    "effect_id": effect_id,
                    "setup": snapshot,
                    "expected": "fail",
                }
            )

        if target_requirements:
            snapshot = make_snapshot(legal_location)
            _apply_invalid_targets(snapshot, target_requirements)
            test_cases.append(
                {
                    "name": f"{cid}_{effect_id}_invalid_target",
                    "type": "invalid_target",
                    "effect_id": effect_id,
                    "setup": snapshot,
                    "expected": "fail",
                }
            )

        if opt != "none":
            snapshot = make_snapshot(legal_location)
            # Use the mapped opt key if available
            opt_key = get_opt_key(cid, effect_id)
            snapshot["opt_used"][opt_key] = True
            test_cases.append(
                {
                    "name": f"{cid}_{effect_id}_opt_violation",
                    "type": "opt_violation",
                    "effect_id": effect_id,
                    "setup": snapshot,
                    "expected": "fail",
                }
            )

        # Condition-not-met: remove trigger/event, or force off-main phase for ignition.
        snapshot = make_snapshot(legal_location)
        if effect_type == "trigger":
            snapshot["pending_triggers"] = []
            snapshot["events"] = []
            snapshot["last_moved_to_gy"] = []
        elif effect_type == "ignition":
            snapshot["phase"] = "Battle Phase"
        elif cost_requirements:
            _apply_missing_cost(snapshot, cost_requirements)
        test_cases.append(
            {
                "name": f"{cid}_{effect_id}_condition_not_met",
                "type": "condition_not_met",
                "effect_id": effect_id,
                "setup": snapshot,
                "expected": "fail",
            }
        )

    return test_cases


def run_single_test(test: dict[str, Any]) -> dict[str, Any]:
    state = GameState.from_snapshot(test["setup"])
    cid = test["name"].split("_")[0]
    verified_effect_id = test.get("effect_id")

    # Get the implementation effect_ids for this effect
    impl_effect_ids = get_impl_effect_ids(cid, verified_effect_id) if verified_effect_id else []

    # Filter actions by CID and (if mapped) implementation effect_id
    all_actions = enumerate_effect_actions(state)
    if impl_effect_ids:
        # Use strict filtering when we have a mapping
        actions = [a for a in all_actions if a.cid == cid and a.effect_id in impl_effect_ids]
    else:
        # Fall back to CID-only filtering for unmapped effects
        actions = [a for a in all_actions if a.cid == cid]

    if not actions:
        return {"success": False, "reason": "No actions enumerated"}
    try:
        apply_effect_action(state, actions[0])
        return {"success": True}
    except (IllegalActionError, SimModelError) as exc:
        return {"success": False, "reason": str(exc)}


def run_all_validations() -> dict[str, Any]:
    effects_data = load_verified_effects()
    results = {"passed": [], "failed": [], "errors": []}

    for cid, card_data in effects_data.items():
        if cid.startswith("_"):
            continue
        test_cases = generate_test_cases(cid, card_data)
        for test in test_cases:
            try:
                result = run_single_test(test)
                expected_success = test["expected"] == "success"
                if result["success"] == expected_success:
                    results["passed"].append(test["name"])
                else:
                    results["failed"].append(
                        {
                            "name": test["name"],
                            "expected": test["expected"],
                            "actual": "success" if result["success"] else "fail",
                            "reason": result.get("reason", ""),
                        }
                    )
            except Exception as exc:  # pragma: no cover - diagnostic surface
                results["errors"].append({"name": test["name"], "error": str(exc)})

    return results


def print_report(results: dict[str, Any]) -> None:
    print("=" * 60)
    print("COMPREHENSIVE EFFECT VALIDATION REPORT")
    print("=" * 60)

    print(f"\n✅ PASSED: {len(results['passed'])}")

    print(f"\n❌ FAILED: {len(results['failed'])}")
    for fail in results["failed"]:
        print(f"  - {fail['name']}")
        print(f"    Expected: {fail['expected']}, Got: {fail['actual']}")
        print(f"    Reason: {fail['reason']}")

    print(f"\n⚠️ ERRORS: {len(results['errors'])}")
    for err in results["errors"]:
        print(f"  - {err['name']}: {err['error']}")


if __name__ == "__main__":
    report = run_all_validations()
    print_report(report)
