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
        base = {
            "zones": {
                "field_zones": {
                    "mz": [{"cid": "X", "name": "X", "properly_summoned": True}, None, None, None, None],
                    "emz": [None, None],
                }
            }
        }
        state_a = GameState.from_snapshot(base)
        base["zones"]["field_zones"]["mz"][0]["properly_summoned"] = False
        state_b = GameState.from_snapshot(base)
        self.assertNotEqual(state_hash(state_a), state_hash(state_b))

    def test_state_hash_distinguishes_from_extra(self):
        base = {
            "zones": {
                "field_zones": {
                    "mz": [{"cid": "X", "name": "X", "metadata": {"link_rating": 1}}, None, None, None, None],
                    "emz": [None, None],
                }
            }
        }
        state_a = GameState.from_snapshot(base)
        base["zones"]["field_zones"]["mz"][0]["metadata"] = {}
        state_b = GameState.from_snapshot(base)
        self.assertNotEqual(state_hash(state_a), state_hash(state_b))

    def test_cardinstance_from_raw_normalizes_from_extra(self):
        card = CardInstance.from_raw({"cid": "X", "name": "X", "metadata": {"link_rating": 1}})
        self.assertTrue(card.metadata.get("from_extra"))

    def test_lacrima_gy_ss_requires_properly_summoned(self):
        snapshot = {
            "zones": {
                "gy": [
                    {"cid": "20490", "name": "Fiendsmith's Lacrima"},
                    {"cid": "20225", "name": "Fiendsmith's Requiem", "metadata": {"link_rating": 1}},
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
