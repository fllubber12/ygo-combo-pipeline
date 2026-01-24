import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from sim.effects.registry import apply_effect_action, enumerate_effect_actions  # noqa: E402
from sim.effects.types import EffectAction  # noqa: E402
from sim.errors import IllegalActionError, SimModelError  # noqa: E402
from sim.state import GameState  # noqa: E402


class TestSimEffectRegistry(unittest.TestCase):
    def test_enumeration_determinism(self):
        snapshot = {
            "zones": {
                "hand": [
                    {"cid": "DEMO_EXTENDER_001", "name": "Demo Extender"},
                    {"cid": "DEMO_EXTENDER_001", "name": "Demo Extender"},
                ],
                "field": [],
                "gy": [],
                "banished": [],
                "deck": [],
                "extra": [],
            }
        }
        state = GameState.from_snapshot(snapshot)
        first = enumerate_effect_actions(state)
        second = enumerate_effect_actions(state)
        self.assertEqual([action.sort_key for action in first], [action.sort_key for action in second])

    def test_unknown_cid_fails_closed(self):
        snapshot = {
            "zones": {
                "hand": [],
                "field": [],
                "gy": [],
                "banished": [],
                "deck": [],
                "extra": [],
            }
        }
        state = GameState.from_snapshot(snapshot)
        action = EffectAction(
            cid="UNKNOWN_CID",
            name="Unknown",
            effect_id="noop",
            params={},
            sort_key=("UNKNOWN_CID",),
        )
        with self.assertRaises((IllegalActionError, SimModelError)):
            apply_effect_action(state, action)


if __name__ == "__main__":
    unittest.main()
