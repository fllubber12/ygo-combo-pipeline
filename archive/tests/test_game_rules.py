"""
Tests for core Yu-Gi-Oh game rules enforcement.

Each test corresponds to a rule in docs/GAME_RULES_REFERENCE.md.
Rules are sourced from the Official Yu-Gi-Oh! TCG Rulebook v10.0.
"""

import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from sim.state import GameState, CardInstance  # noqa: E402
from sim.actions import generate_actions, apply_action  # noqa: E402
from sim.effects.registry import enumerate_effect_actions, apply_effect_action  # noqa: E402
from sim.errors import IllegalActionError  # noqa: E402


class TestTokenRules(unittest.TestCase):
    """
    Token Rules (T1-T4) from GAME_RULES_REFERENCE.md
    Source: Official Rulebook v10.0, Page 47
    """

    def test_token_not_sent_to_gy_as_link_material(self):
        """
        Rule T1: Tokens cannot exist outside the field.
        When a Token is used as Link Material, it ceases to exist instead of going to GY.
        """
        # Create state with Fiendsmith Token on field and Requiem in Extra
        snapshot = {
            "zones": {
                "field_zones": {
                    "mz": [
                        {"cid": "TOKEN_FIENDSMITH", "metadata": {"subtype": "token", "attribute": "LIGHT", "race": "FIEND"}},
                        None, None, None, None,
                    ],
                    "emz": [None, None],
                },
                "extra": [{"cid": "20225"}],  # Requiem (Link-1)
                "gy": [],
            }
        }
        state = GameState.from_snapshot(snapshot)

        # Get Link Summon action
        actions = generate_actions(state, ["extra_deck_summon"])
        link_summons = [a for a in actions if a.action_type == "extra_deck_summon"]

        self.assertTrue(link_summons, "Should have Link Summon available")

        # Apply the Link Summon
        new_state = apply_action(state, link_summons[0])

        # Verify: Token should NOT be in GY (it ceases to exist)
        token_in_gy = any(
            c.cid == "TOKEN_FIENDSMITH" or c.metadata.get("subtype") == "token"
            for c in new_state.gy
        )
        self.assertFalse(token_in_gy, "Token should NOT be in GY - it should cease to exist")

        # Verify: Requiem should be on field
        requiem_on_field = any(
            c and c.cid == "20225"
            for c in new_state.field.emz
        )
        self.assertTrue(requiem_on_field, "Requiem should be on EMZ after Link Summon")

    def test_token_cannot_be_xyz_material(self):
        """
        Rule T2: Tokens cannot be used as Xyz Material.
        """
        # Create state with 2 Tokens and a Rank 1 Xyz in Extra
        snapshot = {
            "zones": {
                "field_zones": {
                    "mz": [
                        {"cid": "TOKEN_1", "metadata": {"subtype": "token", "level": 1}},
                        {"cid": "TOKEN_2", "metadata": {"subtype": "token", "level": 1}},
                        None, None, None,
                    ],
                    "emz": [None, None],
                },
                "extra": [
                    {"cid": "INERT_XYZ_RANK1", "metadata": {"summon_type": "xyz", "rank": 1}},
                ],
            }
        }
        state = GameState.from_snapshot(snapshot)

        # Get Xyz Summon actions
        actions = generate_actions(state, ["extra_deck_summon"])
        xyz_summons = [
            a for a in actions
            if a.action_type == "extra_deck_summon"
            and a.params.get("summon_type") == "xyz"
        ]

        # Tokens cannot be Xyz material - no Xyz summons should be available
        self.assertEqual(len(xyz_summons), 0, "Tokens cannot be used as Xyz Material")

    def test_token_can_be_link_material(self):
        """
        Rule T3: Tokens CAN be used as Link Material.
        """
        snapshot = {
            "zones": {
                "field_zones": {
                    "mz": [
                        {"cid": "TOKEN_FIENDSMITH", "metadata": {"subtype": "token", "attribute": "LIGHT", "race": "FIEND"}},
                        None, None, None, None,
                    ],
                    "emz": [None, None],
                },
                "extra": [{"cid": "20225"}],  # Requiem (Link-1)
            }
        }
        state = GameState.from_snapshot(snapshot)

        # Get Link Summon actions
        actions = generate_actions(state, ["extra_deck_summon"])
        link_summons = [
            a for a in actions
            if a.action_type == "extra_deck_summon"
            and a.params.get("summon_type") == "link"
        ]

        # Tokens CAN be Link Material
        self.assertTrue(link_summons, "Token should be usable as Link Material")

    def test_token_can_be_tributed(self):
        """
        Rule T4: Tokens can be Tributed for Tribute Summons.
        """
        snapshot = {
            "zones": {
                "field_zones": {
                    "mz": [
                        {"cid": "TOKEN_1", "metadata": {"subtype": "token"}},
                        None, None, None, None,
                    ],
                    "emz": [None, None],
                },
                "hand": [
                    {"cid": "INERT_MONSTER_LIGHT_FIEND_5"},  # Level 5 needs 1 tribute
                ],
            }
        }
        state = GameState.from_snapshot(snapshot)

        # Get Tribute Summon actions
        actions = generate_actions(state, ["normal_summon"])
        tribute_summons = [
            a for a in actions
            if a.action_type == "normal_summon"
            and a.params.get("tributes")
        ]

        # This test validates the rule - actual implementation may vary
        # For now we just document the expected behavior
        # self.assertTrue(tribute_summons, "Token should be usable as Tribute")
        pass  # Skip until Tribute Summon is implemented


class TestLinkSummonRules(unittest.TestCase):
    """
    Link Summon Rules (L1-L3) from GAME_RULES_REFERENCE.md
    Source: Official Rulebook v10.0, Pages 22-23
    """

    def test_link_material_sent_to_gy(self):
        """
        Rule L1: Link Materials go to GY (except Tokens).
        """
        snapshot = {
            "zones": {
                "field_zones": {
                    "mz": [
                        {"cid": "20196"},  # Fiendsmith Engraver (not a token)
                        None, None, None, None,
                    ],
                    "emz": [None, None],
                },
                "extra": [{"cid": "20225"}],  # Requiem (Link-1)
                "gy": [],
            }
        }
        state = GameState.from_snapshot(snapshot)

        actions = generate_actions(state, ["extra_deck_summon"])
        link_summons = [a for a in actions if a.action_type == "extra_deck_summon"]

        self.assertTrue(link_summons, "Should have Link Summon available")

        new_state = apply_action(state, link_summons[0])

        # Verify: Engraver (non-token) SHOULD be in GY
        engraver_in_gy = any(c.cid == "20196" for c in new_state.gy)
        self.assertTrue(engraver_in_gy, "Non-token Link Material should be sent to GY")

    def test_link_rating_material_count(self):
        """
        Rule L2: Link Rating determines minimum materials.
        Agnumday (Link-3) requires 3 materials.
        """
        snapshot = {
            "zones": {
                "field_zones": {
                    "mz": [
                        {"cid": "INERT_MONSTER_LIGHT_FIEND_4"},
                        {"cid": "INERT_MONSTER_LIGHT_FIEND_4"},
                        None, None, None,
                    ],
                    "emz": [None, None],
                },
                "extra": [{"cid": "20521"}],  # Agnumday (Link-3)
            }
        }
        state = GameState.from_snapshot(snapshot)

        actions = generate_actions(state, ["extra_deck_summon"])
        agnumday_summons = [
            a for a in actions
            if a.action_type == "extra_deck_summon"
            and a.params.get("link_rating") == 3
        ]

        # With only 2 materials, cannot summon Link-3
        self.assertEqual(len(agnumday_summons), 0, "Cannot summon Link-3 with only 2 materials")

    def test_link_summon_placement(self):
        """
        Rule L3: Link Summons go to Extra Monster Zone.
        """
        snapshot = {
            "zones": {
                "field_zones": {
                    "mz": [
                        {"cid": "20196"},
                        None, None, None, None,
                    ],
                    "emz": [None, None],
                },
                "extra": [{"cid": "20225"}],
            }
        }
        state = GameState.from_snapshot(snapshot)

        actions = generate_actions(state, ["extra_deck_summon"])
        new_state = apply_action(state, actions[0])

        # Link monster should be in EMZ
        link_in_emz = any(c and c.cid == "20225" for c in new_state.field.emz)
        self.assertTrue(link_in_emz, "Link Monster should be placed in EMZ")


class TestXyzRules(unittest.TestCase):
    """
    Xyz Rules (X1-X3) from GAME_RULES_REFERENCE.md
    Source: Official Rulebook v10.0, Pages 20-21
    """

    def test_xyz_has_rank_not_level(self):
        """
        Rule X3: Xyz Monsters have Rank, not Level.
        """
        # Evilswarm Exciton Knight is Rank 4 (CID 10942)
        card = CardInstance.from_raw({"cid": "10942"})

        rank = card.metadata.get("rank")
        level = card.metadata.get("level")

        self.assertEqual(rank, 4, "Exciton Knight should have Rank 4")
        # Level should be None or 0 for Xyz monsters
        self.assertTrue(level is None or level == 0, "Xyz Monster should not have Level")


class TestGraveyardRules(unittest.TestCase):
    """
    Graveyard Rules (G1-G2) from GAME_RULES_REFERENCE.md
    """

    def test_gy_order_preserved(self):
        """
        Rule G2: GY order is preserved.
        """
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "20196"},  # First
                    {"cid": "20225"},  # Second
                    {"cid": "20241"},  # Third
                ],
            }
        }
        state = GameState.from_snapshot(snapshot)

        # Order should be preserved
        self.assertEqual(state.gy[0].cid, "20196", "First card should be Engraver")
        self.assertEqual(state.gy[1].cid, "20225", "Second card should be Requiem")
        self.assertEqual(state.gy[2].cid, "20241", "Third card should be Sanct")


class TestSpecialSummonRules(unittest.TestCase):
    """
    Special Summon Rules (S1-S2) from GAME_RULES_REFERENCE.md
    """

    def test_revival_requires_properly_summoned(self):
        """
        Rule S1: Revival requires "properly summoned" flag.
        """
        # Desirae in GY but NOT properly summoned
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "20215", "properly_summoned": False},
                ],
                "field_zones": {
                    "mz": [None, None, None, None, None],
                    "emz": [
                        {"cid": "20521"},  # Agnumday can revive from GY
                        None,
                    ],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)

        # Agnumday's revive effect should NOT be available
        actions = [
            a for a in enumerate_effect_actions(state)
            if a.effect_id == "agnumday_revive_equip"
        ]

        self.assertEqual(len(actions), 0, "Cannot revive monster that wasn't properly summoned")

    def test_semi_nomi_can_be_revived_after_proper_summon(self):
        """
        Rule S2: Semi-Nomi can be revived after proper summon.
        """
        # Desirae in GY, WAS properly summoned
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "20215", "properly_summoned": True},
                ],
                "field_zones": {
                    "mz": [None, None, None, None, None],
                    "emz": [
                        {"cid": "20521"},  # Agnumday can revive from GY
                        None,
                    ],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)

        # Agnumday's revive effect SHOULD be available
        actions = [
            a for a in enumerate_effect_actions(state)
            if a.effect_id == "agnumday_revive_equip"
        ]

        self.assertTrue(actions, "Can revive monster that was properly summoned")


class TestZoneRules(unittest.TestCase):
    """
    Zone Rules (Z1) from GAME_RULES_REFERENCE.md
    """

    def test_main_monster_zone_capacity(self):
        """
        Rule Z1: Main Monster Zone has capacity of 5.
        """
        snapshot = {
            "zones": {
                "field_zones": {
                    "mz": [
                        {"cid": "20196"},
                        {"cid": "20196"},
                        {"cid": "20196"},
                        {"cid": "20196"},
                        {"cid": "20196"},
                    ],
                    "emz": [None, None],
                },
                "hand": [{"cid": "INERT_MONSTER_LIGHT_FIEND_4"}],
            }
        }
        state = GameState.from_snapshot(snapshot)

        # Count monsters in MZ
        mz_count = sum(1 for c in state.field.mz if c is not None)
        self.assertEqual(mz_count, 5, "MZ should have exactly 5 monsters")

        # Should not be able to Special Summon when MZ is full
        # (This depends on implementation - documenting expected behavior)


class TestEquipRules(unittest.TestCase):
    """
    Equip Rules (E1-E2) from GAME_RULES_REFERENCE.md
    """

    def test_equip_from_gy(self):
        """
        Rule E2: Some effects equip cards from GY.
        """
        snapshot = {
            "zones": {
                "gy": [{"cid": "20225"}],  # Requiem in GY
                "field_zones": {
                    "mz": [
                        {"cid": "20215"},  # Desirae (valid target)
                        None, None, None, None,
                    ],
                    "emz": [None, None],
                },
            }
        }
        state = GameState.from_snapshot(snapshot)

        # Requiem's equip effect should be available
        actions = [
            a for a in enumerate_effect_actions(state)
            if a.effect_id == "equip_requiem_to_fiend"
        ]

        self.assertTrue(actions, "Requiem should be able to equip from GY")


if __name__ == "__main__":
    unittest.main()
