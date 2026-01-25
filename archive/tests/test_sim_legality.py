import sys
import unittest
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root / "src"))

from sim.actions import apply_extra_deck_summon, apply_normal_summon, apply_special_summon  # noqa: E402
from sim.errors import IllegalActionError  # noqa: E402
from sim.state import GameState  # noqa: E402


def make_state(hand=None, field=None, extra=None, normal_used=False):
    """Create a test GameState with proper test CIDs."""
    # Convert simple strings to CID dicts
    def to_cid(item):
        if isinstance(item, str):
            return {"cid": f"INERT_MONSTER_LIGHT_FIEND_4"}
        return item

    snapshot = {
        "zones": {
            "hand": [to_cid(c) for c in (hand or [])],
            "field": [to_cid(c) for c in (field or [])],
            "gy": [],
            "banished": [],
            "deck": [],
            "extra": [to_cid(c) for c in (extra or [])],
        },
        "normal_summon_set_used": normal_used,
    }
    return GameState.from_snapshot(snapshot)


class TestSimLegality(unittest.TestCase):
    def test_normal_summon_budget(self):
        state = make_state(hand=[{"cid": "INERT_MONSTER_LIGHT_FIEND_4"}], field=[], normal_used=False)
        new_state = state.clone()
        apply_normal_summon(new_state, hand_index=0, mz_index=0)
        with self.assertRaises(IllegalActionError):
            apply_normal_summon(new_state, hand_index=0, mz_index=1)

    def test_zone_capacity(self):
        field_cards = [{"cid": f"INERT_MONSTER_LIGHT_FIEND_4"} for i in range(5)]
        state = make_state(hand=[{"cid": "INERT_MONSTER_LIGHT_FIEND_4"}], field=field_cards)
        with self.assertRaises(IllegalActionError):
            apply_special_summon(state, hand_index=0, mz_index=0)

    def test_link_summon_requires_emz(self):
        # Use real Sequence (Link-2) from CDB
        extra = [{"cid": "20238"}]  # Fiendsmith's Sequence
        snapshot = {
            "zones": {
                "hand": [],
                "field": [{"cid": "INERT_MONSTER_LIGHT_FIEND_4"}, {"cid": "INERT_MONSTER_LIGHT_FIEND_4"}],
                "emz": [{"cid": "INERT_MONSTER_LIGHT_FIEND_4"}, {"cid": "INERT_MONSTER_LIGHT_FIEND_4"}],
                "gy": [],
                "banished": [],
                "deck": [],
                "extra": extra,
            }
        }
        state = GameState.from_snapshot(snapshot)
        with self.assertRaises(IllegalActionError):
            apply_extra_deck_summon(
                state,
                extra_index=0,
                summon_type="link",
                materials=[("mz", 0), ("mz", 1)],
                link_rating=2,
                min_materials=2,
            )

    def test_link_material_counting(self):
        # Use real Agnumday (Link-3) from CDB
        extra = [{"cid": "20521"}]  # Fiendsmith's Agnumday
        snapshot = {
            "zones": {
                "hand": [],
                "field": [
                    {"cid": "20238"},  # Fiendsmith's Sequence (Link-2)
                    {"cid": "INERT_MONSTER_LIGHT_FIEND_4"},
                ],
                "emz": [None, None],
                "gy": [],
                "banished": [],
                "deck": [],
                "extra": extra,
            }
        }
        state = GameState.from_snapshot(snapshot)
        apply_extra_deck_summon(
            state,
            extra_index=0,
            summon_type="link",
            materials=[("mz", 0), ("mz", 1)],
            link_rating=3,
            min_materials=2,
        )
        self.assertEqual(state.field.emz[0].name, "Fiendsmith's Agnumday")


if __name__ == "__main__":
    unittest.main()
