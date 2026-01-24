import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from sim.effects.fiendsmith_effects import OPP_TURN_EVENT  # noqa: E402
from sim.effects.registry import enumerate_effect_actions  # noqa: E402
from sim.search import state_hash  # noqa: E402
from sim.state import CardInstance, GameState  # noqa: E402


class TestSearchHashAndRevivalGating(unittest.TestCase):
    def test_state_hash_distinguishes_properly_summoned(self):
        # Use real CID for Requiem (Link-1)
        base = {
            "zones": {
                "field_zones": {
                    "mz": [{"cid": "20225", "properly_summoned": True}, None, None, None, None],
                    "emz": [None, None],
                }
            }
        }
        state_a = GameState.from_snapshot(base)
        base["zones"]["field_zones"]["mz"][0]["properly_summoned"] = False
        state_b = GameState.from_snapshot(base)
        self.assertNotEqual(state_hash(state_a), state_hash(state_b))

    def test_state_hash_distinguishes_from_extra(self):
        # Use Requiem (Link-1, from_extra=True) vs main deck monster
        state_a_snap = {
            "zones": {
                "field_zones": {
                    "mz": [{"cid": "20225"}, None, None, None, None],  # Requiem - from_extra=True
                    "emz": [None, None],
                }
            }
        }
        state_b_snap = {
            "zones": {
                "field_zones": {
                    "mz": [{"cid": "20196"}, None, None, None, None],  # Engraver - from_extra=False
                    "emz": [None, None],
                }
            }
        }
        state_a = GameState.from_snapshot(state_a_snap)
        state_b = GameState.from_snapshot(state_b_snap)
        self.assertNotEqual(state_hash(state_a), state_hash(state_b))

    def test_cardinstance_from_raw_normalizes_from_extra(self):
        # Requiem is Link-1, should have from_extra=True from CDB
        card = CardInstance.from_raw({"cid": "20225"})
        self.assertTrue(card.metadata.get("from_extra"))

    def test_lacrima_gy_ss_requires_properly_summoned(self):
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "20490"},  # Lacrima the Crimson Tears
                    {"cid": "20225"},  # Requiem (Link-1)
                ],
                "field_zones": {"mz": [None, None, None, None, None], "emz": [None, None]},
            },
            "events": [OPP_TURN_EVENT],
        }
        state = GameState.from_snapshot(snapshot)
        actions = [
            action
            for action in enumerate_effect_actions(state)
            if action.effect_id == "gy_shuffle_ss_fiendsmith_link"
        ]
        self.assertFalse(actions)


if __name__ == "__main__":
    unittest.main()
