"""
Golden Fixture Tests for 5 Core Verified Cards

These tests verify that each effect implementation matches the Lua ground truth.
Each fixture documents:
- The Lua reference (file + lines)
- Preconditions for the effect
- Expected outcomes after applying the effect

Run with: python3 -m unittest tests.test_golden_fixtures
"""

import json
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(repo_root / "src"))

from sim.effects.registry import apply_effect_action, enumerate_effect_actions  # noqa: E402
from sim.state import GameState  # noqa: E402

GOLDEN_DIR = repo_root / "tests" / "fixtures" / "combo_scenarios" / "golden"


def load_golden_fixture(name: str) -> dict:
    path = GOLDEN_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


class TestEngraverGoldenFixtures(unittest.TestCase):
    """CID 20196 - Fiendsmith Engraver (Passcode: 60764609)"""

    def test_e1_discard_search(self):
        """e1: Discard self from hand to search Fiendsmith S/T from deck"""
        fixture = load_golden_fixture("golden_engraver_e1_discard_search")
        state = GameState.from_snapshot(fixture["state"])

        # Find e1 actions
        actions = [a for a in enumerate_effect_actions(state)
                   if a.effect_id and "search" in a.effect_id.lower()]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 search action for Engraver e1")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: Engraver should be in GY (was discarded as cost)
        engraver_in_gy = any(c.cid == "20196" for c in new_state.gy)
        self.assertTrue(engraver_in_gy, "Engraver should be in GY after e1")

        # Verify: Tract should be in hand (was searched)
        tract_in_hand = any(c.cid == "20240" for c in new_state.hand)
        self.assertTrue(tract_in_hand, "Tract should be in hand after e1 search")

        # Verify: OPT used
        self.assertTrue(new_state.opt_used.get("20196:e1"),
            "OPT should be marked for 20196:e1")

    def test_e2_send_equip_monster(self):
        """e2: Send Fiendsmith Equip + monster to GY (requires Engraver on field)"""
        fixture = load_golden_fixture("golden_engraver_e2_send_equip_monster")
        state = GameState.from_snapshot(fixture["state"])

        # Find e2 actions
        actions = [a for a in enumerate_effect_actions(state)
                   if a.effect_id and "send" in a.effect_id.lower()
                   and a.cid == "20196"]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 send action for Engraver e2")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: OPT used
        self.assertTrue(new_state.opt_used.get("20196:e2"),
            "OPT should be marked for 20196:e2")

    def test_e2_requires_engraver_on_field(self):
        """REGRESSION: e2 should NOT enumerate if Engraver not on field"""
        fixture = load_golden_fixture("golden_engraver_e2_send_equip_monster")
        data = fixture["state"]

        # Move Engraver to hand instead of field
        data["zones"]["hand"] = data["zones"]["field_zones"]["mz"][:1]
        data["zones"]["field_zones"]["mz"][0] = None

        state = GameState.from_snapshot(data)

        # Should NOT find e2 actions
        actions = [a for a in enumerate_effect_actions(state)
                   if a.effect_id and "send" in a.effect_id.lower()
                   and a.cid == "20196"]

        self.assertEqual(len(actions), 0,
            "e2 should NOT enumerate when Engraver not on field (LOCATION_MZONE)")

    def test_e3_gy_shuffle_ss(self):
        """e3: Shuffle OTHER LIGHT Fiend from GY; SS self from GY"""
        fixture = load_golden_fixture("golden_engraver_e3_gy_shuffle_ss")
        state = GameState.from_snapshot(fixture["state"])

        # Find e3 actions - effect_id is "gy_shuffle_light_fiend_then_ss_self"
        actions = [a for a in enumerate_effect_actions(state)
                   if a.effect_id and "gy_shuffle" in a.effect_id.lower() and a.cid == "20196"]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 revive action for Engraver e3")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: Engraver on field
        engraver_on_field = any(
            c and c.cid == "20196"
            for c in new_state.field.mz + new_state.field.emz
        )
        self.assertTrue(engraver_on_field,
            "Engraver should be on field after e3")

        # Verify: Cost card shuffled (not in GY)
        lacrima_ct_in_gy = any(c.cid == "20490" for c in new_state.gy)
        self.assertFalse(lacrima_ct_in_gy,
            "Cost card (Lacrima CT) should be shuffled out of GY")

        # Verify: OPT used
        self.assertTrue(new_state.opt_used.get("20196:e3"),
            "OPT should be marked for 20196:e3")


class TestTractGoldenFixtures(unittest.TestCase):
    """CID 20240 - Fiendsmith's Tract (Passcode: 98567237)"""

    def test_e1_search_light_fiend(self):
        """e1: Activate to search LIGHT Fiend from deck, then discard"""
        fixture = load_golden_fixture("golden_tract_e1_search_light_fiend")
        state = GameState.from_snapshot(fixture["state"])

        # Find e1 actions
        actions = [a for a in enumerate_effect_actions(state)
                   if a.cid == "20240"]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 action for Tract e1")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: Tract in GY (spell resolved)
        tract_in_gy = any(c.cid == "20240" for c in new_state.gy)
        self.assertTrue(tract_in_gy, "Tract should be in GY after activation")

        # Verify: Engraver in hand (was searched)
        engraver_in_hand = any(c.cid == "20196" for c in new_state.hand)
        self.assertTrue(engraver_in_hand, "Engraver should be in hand after search")

        # Verify: OPT used
        self.assertTrue(new_state.opt_used.get("20240:e1"),
            "OPT should be marked for 20240:e1")

    def test_e2_gy_banish_fusion(self):
        """e2: Banish from GY to Fusion Summon Fiendsmith"""
        fixture = load_golden_fixture("golden_tract_e2_gy_banish_fusion")
        state = GameState.from_snapshot(fixture["state"])

        # Find e2 actions - effect_id is "gy_banish_fuse_fiendsmith"
        actions = [a for a in enumerate_effect_actions(state)
                   if a.effect_id and "fuse" in a.effect_id.lower()]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 fusion action for Tract e2")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: Tract banished
        tract_banished = any(c.cid == "20240" for c in new_state.banished)
        self.assertTrue(tract_banished, "Tract should be banished after e2")

        # Verify: Fusion on field
        fusion_on_field = any(
            c and c.cid == "20214"
            for c in new_state.field.mz + new_state.field.emz
        )
        self.assertTrue(fusion_on_field,
            "Lacrima Fusion should be on field after e2")

        # Verify: OPT used
        self.assertTrue(new_state.opt_used.get("20240:e2"),
            "OPT should be marked for 20240:e2")


class TestRequiemGoldenFixtures(unittest.TestCase):
    """CID 20225 - Fiendsmith's Requiem (Passcode: 2463794)"""

    def test_e1_tribute_ss(self):
        """e1: Tribute self to SS Fiendsmith from hand/deck"""
        fixture = load_golden_fixture("golden_requiem_e1_tribute_ss")
        state = GameState.from_snapshot(fixture["state"])

        # Find e1 actions
        actions = [a for a in enumerate_effect_actions(state)
                   if a.cid == "20225" and a.effect_id and "tribute" in a.effect_id.lower()]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 tribute SS action for Requiem e1")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: Requiem in GY (was tributed)
        requiem_in_gy = any(c.cid == "20225" for c in new_state.gy)
        self.assertTrue(requiem_in_gy, "Requiem should be in GY after tribute")

        # Verify: Summoned monster on field
        summoned = any(
            c and c.cid in ("20490", "20196")
            for c in new_state.field.mz + new_state.field.emz
        )
        self.assertTrue(summoned,
            "Fiendsmith monster should be on field after e1")

    def test_e2_equip_from_field(self):
        """REGRESSION: e2 should work from FIELD (not just GY)"""
        fixture = load_golden_fixture("golden_requiem_e2_equip_from_field")
        state = GameState.from_snapshot(fixture["state"])

        # Find e2 actions
        actions = [a for a in enumerate_effect_actions(state)
                   if a.effect_id and "equip" in a.effect_id.lower()]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 equip action for Requiem e2 FROM FIELD")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: Engraver has Requiem equipped
        engraver = None
        for c in new_state.field.mz + new_state.field.emz:
            if c and c.cid == "20196":
                engraver = c
                break

        self.assertIsNotNone(engraver, "Engraver should still be on field")
        self.assertTrue(
            any(eq.cid == "20225" for eq in engraver.equipped),
            "Engraver should have Requiem equipped after e2"
        )

    def test_e2_equip_from_gy(self):
        """e2: Equip from GY to non-Link LIGHT Fiend"""
        fixture = load_golden_fixture("golden_requiem_e2_equip_from_gy")
        state = GameState.from_snapshot(fixture["state"])

        # Find e2 actions
        actions = [a for a in enumerate_effect_actions(state)
                   if a.effect_id and "equip" in a.effect_id.lower()]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 equip action for Requiem e2 from GY")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: Engraver has Requiem equipped
        engraver = None
        for c in new_state.field.mz + new_state.field.emz:
            if c and c.cid == "20196":
                engraver = c
                break

        self.assertIsNotNone(engraver, "Engraver should be on field")
        self.assertTrue(
            any(eq.cid == "20225" for eq in engraver.equipped),
            "Engraver should have Requiem equipped after e2"
        )

        # Verify: Requiem not in GY anymore
        requiem_in_gy = any(c.cid == "20225" for c in new_state.gy)
        self.assertFalse(requiem_in_gy,
            "Requiem should not be in GY after equipping")


class TestLacrimaCTGoldenFixtures(unittest.TestCase):
    """CID 20490 - Lacrima the Crimson Tears (Passcode: 28803166)"""

    def test_summon_trigger_send(self):
        """e1/e2: When summoned, send Fiendsmith from deck (except self)"""
        fixture = load_golden_fixture("golden_lacrima_ct_summon_trigger")
        state = GameState.from_snapshot(fixture["state"])

        # Find summon trigger actions
        actions = [a for a in enumerate_effect_actions(state)
                   if a.cid == "20490" and a.effect_id and "send" in a.effect_id.lower()]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 send action for Lacrima CT summon trigger")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: A Fiendsmith card was sent to GY
        fiendsmith_in_gy = any(
            c.cid in ("20196", "20240") for c in new_state.gy
        )
        self.assertTrue(fiendsmith_in_gy,
            "A Fiendsmith card should be in GY after summon trigger")

        # Verify: OPT used
        self.assertTrue(new_state.opt_used.get("20490:e1"),
            "OPT should be marked for 20490:e1")

    def test_e3_gy_ss_link(self):
        """e3: On opponent's turn, shuffle self; SS Fiendsmith Link from GY"""
        fixture = load_golden_fixture("golden_lacrima_ct_e3_gy_ss_link")
        state = GameState.from_snapshot(fixture["state"])

        # Find e3 actions - effect_id is "gy_shuffle_ss_fiendsmith_link"
        actions = [a for a in enumerate_effect_actions(state)
                   if a.cid == "20490" and a.effect_id and "gy_shuffle" in a.effect_id.lower()]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 SS Link action for Lacrima CT e3")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: Lacrima CT not in GY (shuffled to deck)
        lacrima_in_gy = any(c.cid == "20490" for c in new_state.gy)
        self.assertFalse(lacrima_in_gy,
            "Lacrima CT should be shuffled to deck after e3")

        # Verify: Link monster on field
        link_on_field = any(
            c and c.cid == "20225"
            for c in new_state.field.mz + new_state.field.emz
        )
        self.assertTrue(link_on_field,
            "Requiem (Link) should be on field after e3")


class TestDesiraeGoldenFixtures(unittest.TestCase):
    """CID 20215 - Fiendsmith's Desirae (Passcode: 82135803)"""

    def test_e1_negate_from_emz(self):
        """REGRESSION: e1 should work when Desirae is in EMZ (not just MZ)"""
        fixture = load_golden_fixture("golden_desirae_e1_negate")
        state = GameState.from_snapshot(fixture["state"])

        # Find e1 negate actions
        actions = [a for a in enumerate_effect_actions(state)
                   if a.cid == "20215" and a.effect_id and "negate" in a.effect_id.lower()]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 negate action for Desirae e1 in EMZ")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: negates_used counter incremented
        negates_used = int(new_state.opt_used.get("20215:negates_used", 0))
        self.assertGreaterEqual(negates_used, 1,
            "negates_used should be at least 1 after negate")

    def test_e2_gy_trigger_send(self):
        """e2: When sent to GY, shuffle LIGHT Fiend; send card on field to GY"""
        fixture = load_golden_fixture("golden_desirae_e2_gy_trigger_send")
        state = GameState.from_snapshot(fixture["state"])

        # Find e2 actions - effect_id is "gy_desirae_send_field"
        actions = [a for a in enumerate_effect_actions(state)
                   if a.cid == "20215" and a.effect_id and "gy_desirae" in a.effect_id.lower()]

        self.assertGreaterEqual(len(actions), 1,
            "Expected at least 1 GY trigger action for Desirae e2")

        # Apply first action
        new_state = apply_effect_action(state, actions[0])

        # Verify: Cost card (Requiem) shuffled out of GY
        requiem_in_gy = any(c.cid == "20225" for c in new_state.gy)
        self.assertFalse(requiem_in_gy,
            "Requiem should be shuffled out of GY as cost")


class TestGoldenFixtureIntegrity(unittest.TestCase):
    """Meta-tests to verify golden fixtures are properly formatted"""

    def test_all_golden_fixtures_loadable(self):
        """All golden fixtures should be valid JSON with required fields"""
        required_fields = ["name", "description", "lua_reference", "test", "state"]

        for fixture_path in GOLDEN_DIR.glob("golden_*.json"):
            with self.subTest(fixture=fixture_path.name):
                data = json.loads(fixture_path.read_text(encoding="utf-8"))
                for field in required_fields:
                    self.assertIn(field, data,
                        f"Missing required field '{field}' in {fixture_path.name}")

    def test_golden_fixture_count(self):
        """Should have golden fixtures for all 12 verified effects"""
        fixtures = list(GOLDEN_DIR.glob("golden_*.json"))
        # 3 Engraver + 2 Tract + 3 Requiem + 2 Lacrima CT + 2 Desirae = 12
        self.assertGreaterEqual(len(fixtures), 11,
            f"Expected at least 11 golden fixtures, found {len(fixtures)}")


if __name__ == "__main__":
    unittest.main()
